"""分析爆款视频(抖音链接解析 / 做同款)。

用户贴一个短视频分享链接 -> 解析爆款内容与话题 -> 仿写原创脚本。
节点只建 pending 记录 + 启动后台任务后立即返回;真正的提取/分析/仿写在后台跑,前端轮询。
与 generate_images 同样的后台任务模式(DB 是真源,跨会话存活)。
Phase 5:记录生成日志(prompt/模型版本)。
"""

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import project_repo
from app.services import genlog, media_service, video_analysis_service


@tracked("analyze_video")
async def analyze_video(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    user_input = state.get("user_input", "")

    # 从用户输入中抽取分享链接(classify_intent 已判定为 analyze_video,这里兜底再取一次)
    share_link = media_service.detect_share_link(user_input)
    if not share_link:
        return {
            "final_text": "没看到视频链接。把抖音/快手/B站的分享链接发给我，我来分析爆款并做同款。",
            "message_type": "text",
            "artifact_id": None,
        }

    async with AsyncSessionLocal() as s:
        project = await project_repo.ensure_project(s, conv_id)

    artifact = await video_analysis_service.start_analysis(
        conversation_id=conv_id,
        project_id=project.id,
        share_link=share_link,
        owner_id=owner_id,
    )
    await genlog.log_generation(
        kind="video_analysis",
        owner_id=owner_id,
        conversation_id=conv_id,
        artifact_id=artifact["id"],
        prompt_name="video_analyze",
        prompt_version=prompt_version("video_analyze"),
        model=settings.deepseek_model,
        params={"share_link": share_link},
        status="ok",
    )

    intro = (
        "正在解析这个爆款链接：下载视频、提取口播文案、拆解话题与爆款手法，"
        "然后仿写一段同款原创脚本。稍等片刻，可以继续做别的，回来能看到结果。"
    )
    return {
        "project_id": project.id,
        "video_analysis": artifact,
        "final_text": intro,
        "message_type": "video_analysis_card",
        "artifact_id": artifact["id"],
    }
