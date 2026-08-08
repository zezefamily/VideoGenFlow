"""豆包/火山引擎语音合成 HTTP API 客户端。"""

import base64
import uuid

import httpx

from app.config import settings


class VolcengineTTSError(RuntimeError):
    pass


async def synthesize(*, text: str, voice_type: str, emotion: str | None, speed: float, pitch: float, volume: float, fmt: str) -> tuple[bytes, str]:
    if not settings.volc_tts_appid or not settings.volc_tts_access_token:
        raise VolcengineTTSError("VOLC_TTS_APPID 或 VOLC_TTS_ACCESS_TOKEN 未配置")
    reqid = uuid.uuid4().hex
    audio = {"voice_type": voice_type, "encoding": fmt, "speed_ratio": speed, "pitch_ratio": pitch, "volume_ratio": max(0.1, 1 + volume / 10)}
    if emotion:
        audio["emotion"] = emotion
    body = {
        "app": {"appid": settings.volc_tts_appid, "token": settings.volc_tts_access_token, "cluster": settings.volc_tts_cluster},
        "user": {"uid": "videogenflow"},
        "audio": audio,
        "request": {"reqid": reqid, "text": text, "text_type": "plain", "operation": "query"},
    }
    headers = {"Authorization": f"Bearer;{settings.volc_tts_access_token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(settings.volc_tts_api_url, headers=headers, json=body, timeout=120)
    if response.status_code != 200:
        raise VolcengineTTSError(f"豆包 TTS HTTP {response.status_code}: {response.text[:200]}")
    payload = response.json()
    # 经典 HTTP TTS 接口成功业务码为 3000；部分兼容网关会返回 0。
    if payload.get("code") not in (0, "0", 3000, "3000"):
        raise VolcengineTTSError(f"豆包 TTS 失败: {payload.get('message') or payload}")
    data = payload.get("data") or ""
    if not data:
        raise VolcengineTTSError("豆包 TTS 返回成功，但没有音频数据")
    try:
        return base64.b64decode(data), reqid
    except Exception as exc:
        raise VolcengineTTSError("豆包 TTS 未返回有效音频数据") from exc
