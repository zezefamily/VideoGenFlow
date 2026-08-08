"""生成图片(Phase 4):基于当前激活分镜,启动后台批量出图。

需要已有激活分镜(由 classify_intent 前置条件保证)。
节点只建记录 + 启动后台任务后立即返回;真正的出图在后台跑,前端轮询。
Phase 5:记录生成日志(prompt/模型版本)。
"""

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import project_repo
from app.services import genlog, image_service, storyboard_service


@tracked("generate_images")
async def generate_images(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    storyboard = state.get("storyboard")
    storyboard_id = state.get("storyboard_id")

    if not storyboard or not storyboard.get("shots"):
        return {
            "final_text": "还没有分镜，没法出图。先让我生成分镜吧。",
            "message_type": "text",
            "artifact_id": None,
        }

    # 用户生图时可指定画风覆盖分镜原画风(前端选画风 -> "用XX画风生成分镜图")
    chosen_style = storyboard_service.detect_style_explicit(state.get("user_input", ""))
    if chosen_style:
        storyboard = {**storyboard, "style": storyboard_service._resolve_style(chosen_style)}

    async with AsyncSessionLocal() as s:
        project = await project_repo.ensure_project(s, conv_id)

    images = await image_service.start_generation(
        storyboard_artifact=storyboard,
        conversation_id=conv_id,
        project_id=project.id,
        storyboard_version_id=storyboard_id,
    )
    await genlog.log_generation(
        kind="image",
        owner_id=owner_id,
        conversation_id=conv_id,
        artifact_id=storyboard_id,
        prompt_name="image_generation",
        prompt_version=prompt_version("image_generation"),
        model=settings.ark_image_model,
        params={"shot_count": len(images), "aspect_ratio": storyboard.get("aspect_ratio", "16:9")},
        status="ok",
    )

    intro = (
        f"开始生成 {len(images)} 张分镜图，逐张出图中（第 1 镜文生图，"
        "后续以上一镜为参考保持一致）。可以继续做别的，回来能看到结果。"
    )
    return {
        "project_id": project.id,
        "images": images,
        "final_text": intro,
        "message_type": "image_gallery",
        "artifact_id": storyboard_id,
    }
