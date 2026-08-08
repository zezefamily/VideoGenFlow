"""火山引擎 ATA 字幕打轴客户端(成片管线:字幕时间轴)。

文本对齐:传入音频公网 URL + 脚本文本,返回该文本逐句/逐词时间戳。
与自由转写不同--文本由我方提供,故字幕文本=原脚本,无识别误差。
流程:submit 提交 -> query 轮询(code 2000=处理中,0=完成)。
文档见用户提供的 ATA 自动字幕打轴说明。
"""

from typing import Optional

import httpx

from app.config import settings

_BASE = settings.volc_ata_base_url.rstrip("/")


class AtaError(RuntimeError):
    pass


def _check_config() -> None:
    if not settings.volc_ata_appid or not settings.volc_ata_token:
        raise AtaError("VOLC_ATA_APPID / VOLC_ATA_TOKEN 未配置")


def _auth_header() -> dict:
    # 文档示例为 `Authorization: Bearer; {token}`(分号较特殊,按文档原样;首次调用核实)
    return {
        "Authorization": f"Bearer; {settings.volc_ata_token}",
    }


async def submit(
    client: Optional[httpx.AsyncClient],
    *,
    audio_url: str,
    audio_text: str,
    caption_type: str = "speech",
    sta_punc_mode: int = 3,  # 3=保留原文本完整标点(字幕文本与脚本一致)
) -> str:
    """提交打轴任务,返回任务 id。audio_url 需公网可访问(TOS)。"""
    _check_config()
    params = {
        "appid": settings.volc_ata_appid,
        "caption_type": caption_type,
        "caption_category": 2,  # 固定传入值
        "cluster": "ata_cluster",  # 固定传入值
        "sta_punc_mode": sta_punc_mode,
    }
    body = {"url": audio_url, "audio_text": audio_text}
    url = f"{_BASE}/api/v1/vc/ata/submit"
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        resp = await client.post(url, params=params, headers=_auth_header(), json=body, timeout=60)
        if resp.status_code != 200:
            raise AtaError(f"ATA submit {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        # code 为字符串或整型;0=成功
        code = data.get("code")
        if str(code) != "0":
            raise AtaError(f"ATA submit 失败: {data.get('message') or data}")
        task_id = data.get("id")
        if not task_id:
            raise AtaError(f"ATA submit 未返回 id: {data}")
        return str(task_id)
    finally:
        if own:
            await client.aclose()


async def query(
    client: Optional[httpx.AsyncClient],
    task_id: str,
    *,
    blocking: int = 0,
) -> dict:
    """查询结果。返回 {code, message, duration, utterances}。

    code: 0=成功(终态), 2000=处理中, 其他=失败。
    utterances: [{text, start_ms, end_ms, words:[{text,start_ms,end_ms}]}]
    """
    _check_config()
    params = {
        "appid": settings.volc_ata_appid,
        "id": task_id,
        "blocking": blocking,
    }
    url = f"{_BASE}/api/v1/vc/ata/query"
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        resp = await client.get(url, params=params, headers=_auth_header(), timeout=60)
        if resp.status_code != 200:
            raise AtaError(f"ATA query {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        code = str(data.get("code"))
        utterances = []
        for u in data.get("utterances") or []:
            utterances.append(
                {
                    "text": u.get("text", ""),
                    "start_ms": u.get("start_time", 0),
                    "end_ms": u.get("end_time", 0),
                    "words": [
                        {
                            "text": w.get("text", ""),
                            "start_ms": w.get("start_time", 0),
                            "end_ms": w.get("end_time", 0),
                        }
                        for w in (u.get("words") or [])
                    ],
                }
            )
        return {
            "code": code,
            "message": data.get("message", ""),
            "duration": data.get("duration"),
            "utterances": utterances,
        }
    finally:
        if own:
            await client.aclose()
