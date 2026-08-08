"""组织回复:脚本/分镜卡片走模板简介;闲聊走 LLM(token 由 stream_mode=messages 流出)。"""

from langchain_core.messages import SystemMessage

from app.graph.tracking import tracked
from app.prompts import CHAT_SYSTEM_PROMPT
from app.services.llm import get_llm


@tracked("respond")
async def respond(state):
    script = state.get("script")
    storyboard = state.get("storyboard")
    intent = state.get("intent", "chat")

    # 图片画廊:generate_images 节点已组装好 intro + images,直接透传不覆盖
    if intent == "generate_images":
        return {}

    # 视频分析卡片:analyze_video 节点已组装好 intro + artifact,直接透传不覆盖
    if intent == "analyze_video":
        return {}

    if intent in ("generate_tts", "render_video"):
        return {}

    # 分镜卡片
    if intent in ("generate_storyboard", "revise_storyboard") and storyboard and storyboard.get("shots"):
        verb = "修改" if intent == "revise_storyboard" else "生成"
        intro = (
            f"分镜已{verb}（第 {storyboard.get('version', 1)} 版，"
            f"{storyboard.get('shot_count', 0)} 镜，"
            f"约 {storyboard.get('total_duration_sec', 0)} 秒，"
            f"{storyboard.get('aspect_ratio', '16:9')}）。"
            "你想先调整镜头，还是继续生成分镜图？"
        )
        return {
            "final_text": intro,
            "message_type": "storyboard_card",
            "artifact_id": storyboard.get("id"),
            "storyboard_id": storyboard.get("id"),
        }

    # 脚本卡片
    if intent in ("create_script", "revise_script") and script and script.get("content"):
        verb = "修改" if intent == "revise_script" else "生成"
        scope_hint = "（仅改动局部）" if intent == "revise_script" else ""
        intro = (
            f"脚本已{verb}（第 {script.get('version', 1)} 版，"
            f"约 {script.get('duration_sec', 0)} 秒）{scope_hint}。"
            "你想先修改文案，还是继续生成分镜？"
        )
        return {
            "final_text": intro,
            "message_type": "script_card",
            "artifact_id": script.get("id"),
            "script_id": script.get("id"),
        }

    # 普通闲聊:用历史消息 + 系统提示调用 LLM
    history = state.get("history", [])
    llm = get_llm(temperature=0.7, thinking="disabled")  # 闲聊无需深思,关思考快速回复
    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)] + list(history)
    ai = await llm.ainvoke(messages)
    return {"final_text": ai.content, "message_type": "text", "artifact_id": None}
