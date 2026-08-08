"""从对话直接触发配音生成/重新生成。"""

from app.config import settings
from app.graph.tracking import tracked
from app.services import tts_service


@tracked("generate_tts")
async def generate_tts(state):
    script = state.get("script")
    project_id = state.get("project_id")
    if not script or not project_id:
        return {"final_text": "当前没有可配音的脚本，请先完成口播脚本。", "message_type": "text"}
    instruction = (state.get("instruction") or state.get("user_input") or "").lower()
    if "豆包" in instruction or "火山" in instruction or "volc" in instruction:
        provider = "volcengine"
    elif "dubbingx" in instruction:
        provider = "dubbingx"
    else:
        provider = settings.tts_provider.lower()
    kwargs = {}
    if provider == "volcengine":
        kwargs = {
            "voice_id": settings.volc_tts_voice_type,
            "emotion": "coldness",
            # 官方体验页“语速 20”映射为 HTTP API 的 speed_ratio=1.2。
            "audio_speed": 1.2,
            "audio_pitch": -1,
            "audio_volume": 0,
        }
    audio = await tts_service.start_generation(
        conversation_id=state["conversation_id"], project_id=project_id,
        script_version_id=script.get("id"), script_text=script.get("content", ""),
        provider=provider, **kwargs,
    )
    provider_name = "豆包" if provider == "volcengine" else "DubbingX"
    return {
        "audio": audio,
        "final_text": f"已开始使用{provider_name}重新生成配音。你可以看到实时状态，完成后我会引导你重新合成成片。",
        "message_type": "text",
    }
