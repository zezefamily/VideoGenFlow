"""DubbingX 异步 TTS 客户端(成片管线:配音)。

整段脚本一次性合成一条音频。流程:addTtsTask 提交 -> getTtsTaskInfo 轮询 ->
fileUrl(签名,会过期)下载。无词级时间戳,故字幕另走火山 ATA 打轴。
文档:https://doc.dubbingx.com/guide/TTSAsync.html
"""

from typing import Optional

import httpx

from app.config import settings

_BASE = settings.dubbingx_base_url.rstrip("/")


class DubbingXError(RuntimeError):
    pass


def _headers() -> dict:
    if not settings.dubbingx_api_key:
        raise DubbingXError("DUBBINGX_API_KEY 未配置")
    return {
        "Authorization": f"Bearer {settings.dubbingx_api_key}",
        "Content-Type": "application/json",
    }


async def _request(
    client: Optional[httpx.AsyncClient],
    method: str,
    path: str,
    *,
    json_body=None,
    timeout: float = 60,
) -> dict:
    url = f"{_BASE}{path}"
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        resp = await client.request(method, url, headers=_headers(), json=json_body, timeout=timeout)
        if resp.status_code != 200:
            raise DubbingXError(f"DubbingX {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success", True) and data.get("code", 200) != 200:
            raise DubbingXError(f"DubbingX 失败: {data.get('msg') or data}")
        return data
    finally:
        if own:
            await client.aclose()


# ---- 音色 / 情绪(前端选择用)----

async def list_voices(
    *,
    page_index: int = 1,
    page_size: int = 100,
    grade: Optional[str] = None,
    gender: Optional[int] = None,
    age_group: Optional[str] = None,
    keyword: Optional[str] = None,
    is_my_model: Optional[bool] = None,
) -> dict:
    """返回 {total, list:[...]}。grade: premium/ordinary/custom。gender: 0女/1男。"""
    body: dict = {"pageIndex": page_index, "pageSize": page_size}
    if grade:
        body["grade"] = grade
    if gender is not None:
        body["gender"] = gender
    if age_group:
        body["ageGroup"] = age_group
    if keyword:
        body["keyword"] = keyword
    if is_my_model is not None:
        body["isMyModel"] = is_my_model
    data = await _request(None, "POST", "/v2/getTTSTimbreList", json_body=body)
    return data.get("data") or {"total": 0, "list": []}


async def list_emotions(timbre_id: str) -> list:
    """返回 [{type:{zh}, aura:[{zh}]}, ...]。"""
    data = await _request(None, "POST", f"/v1/getEmotionList/{timbre_id}")
    return data.get("data") or []


# ---- 文本处理(可选,提升表现力)----

async def analyze_emotion(client: Optional[httpx.AsyncClient], text: str) -> str:
    """分析文本情绪,返回全情绪格式字符串(类型-风格-档位,默认三档)。"""
    data = await _request(client, "POST", "/v2/analyzeEmotion", json_body={"text": text})
    return data.get("data") or ""


async def auto_pause(client: Optional[httpx.AsyncClient], text: str) -> str:
    """给文本自动插入 <break time='x'/> 停顿标签,让断句更自然。返回处理后的文本。"""
    data = await _request(client, "POST", "/v2/autoPause", json_body={"text": text})
    return data.get("data") or text


# ---- TTS 任务(整段脚本)----

async def submit_task(
    client: httpx.AsyncClient,
    *,
    voice_id: str,
    text: str,
    emotion: Optional[str] = None,
    language: str = "zh",
    audio_speed: float = 1.0,
    audio_pitch: float = 1.0,
    audio_volume: float = 0.0,
    file_format: str = "mp3",
) -> str:
    """提交合成任务,返回 taskId。全情绪音色 emotion 可空(自动识别)。"""
    body = {
        "voiceId": voice_id,
        "text": text,
        "language": language,
        "audioSpeed": audio_speed,
        "audioPitch": audio_pitch,
        "audioVolume": audio_volume,
        "fileFormat": file_format,
    }
    if emotion:
        body["emotion"] = emotion
    data = await _request(client, "POST", "/v1/addTtsTask", json_body=body)
    payload = data.get("data")
    # 防御性解析:addTtsTask 应答未在文档示例,兼容 data 为 str / {id} / {taskId}
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return str(payload.get("id") or payload.get("taskId") or "")
    raise DubbingXError(f"DubbingX addTtsTask 未返回 taskId: {data}")


async def get_task_info(
    client: httpx.AsyncClient, task_id: str
) -> dict:
    """返回 {status, file_url}。status: Ready/Generating/Completed/Failed。"""
    data = await _request(client, "POST", f"/v1/getTtsTaskInfo/{task_id}")
    d = data.get("data") or {}
    return {"status": d.get("status", ""), "file_url": d.get("fileUrl") or ""}
