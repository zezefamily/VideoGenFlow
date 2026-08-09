"""从对话直接触发成片重新合成。"""

from app.graph.tracking import tracked
from app.services import video_render_service


@tracked("render_video")
async def render_video(state):
    project_id = state.get("project_id")
    if not project_id:
        return {"final_text": "当前没有可合成的作品。", "message_type": "text"}
    instruction = (state.get("instruction") or state.get("user_input") or "")
    existing_mode = (state.get("video") or {}).get("render_mode")
    if "图片成片" in instruction or "静态成片" in instruction:
        render_mode = "image"
    elif "视频成片" in instruction or "动态成片" in instruction:
        render_mode = "video"
    elif existing_mode and "重新" in instruction:
        render_mode = existing_mode
    else:
        return {
            "final_text": "素材已经齐备。请选择“图片成片”或“视频成片”；视频成片还可以选择智能生成、全部生成或自定义镜头，并会在产生费用前展示预算。",
            "message_type": "text",
        }
    try:
        allow_stale = any(
            phrase in instruction
            for phrase in ("不需要重新生成分镜", "不用重新生成分镜", "复用旧画面", "直接重新合成", "直接合成")
        )
        video = await video_render_service.start_render(
            conversation_id=state["conversation_id"],
            project_id=project_id,
            allow_stale_storyboard=allow_stale,
            render_mode=render_mode,
        )
    except ValueError as exc:
        return {"final_text": f"暂时无法合成成片：{exc}", "message_type": "text"}
    note = video.get("planning_note") or "已检查当前分镜、配音和字幕，素材完整"
    return {
        "video": video,
        "final_text": f"{note}。已开始重新合成成片。",
        "message_type": "text",
    }
