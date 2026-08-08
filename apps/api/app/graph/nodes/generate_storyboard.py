"""生成分镜(Phase 3):基于当前激活脚本,拆成镜头,写入新版本。

需要已有激活脚本(由 classify_intent 前置条件保证)。比例/风格从用户消息识别。
Phase 5:记录生成日志(prompt/模型版本)。
"""

import time

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import project_repo, storyboard_repo
from app.services import genlog, storyboard_service


@tracked("generate_storyboard")
async def generate_storyboard(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    user_input = state.get("user_input", "")
    script = state.get("script")
    script_id = state.get("script_id")

    if not script or not script.get("content"):
        return {
            "final_text": "还没有脚本，没法拆分镜。先告诉我你想做什么主题的视频吧。",
            "message_type": "text",
            "artifact_id": None,
        }

    aspect_ratio = storyboard_service.detect_aspect_ratio(user_input)
    style = storyboard_service.detect_style(user_input)
    t0 = time.perf_counter()
    data = await storyboard_service.generate_storyboard(
        script_content=script.get("content", ""),
        aspect_ratio=aspect_ratio,
        style=style,
    )
    await genlog.log_generation(
        kind="storyboard",
        owner_id=owner_id,
        conversation_id=conv_id,
        prompt_name="storyboard_generate",
        prompt_version=prompt_version("storyboard_generate"),
        model=settings.deepseek_model,
        status="ok" if data.get("shots") else "error",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    if not data.get("shots"):
        return {
            "final_text": "分镜生成失败了，请稍后重试：" + data.get("error", "未知错误"),
            "message_type": "text",
            "artifact_id": None,
        }

    async with AsyncSessionLocal() as s:
        project = await project_repo.ensure_project(
            s, conv_id, title=script.get("title", "")
        )
        sv = await storyboard_repo.create_storyboard_version(
            s,
            conv_id,
            project.id,
            {
                "script_version_id": script_id,
                "aspect_ratio": aspect_ratio,
                "style": data.get("style", ""),
                "shots": data["shots"],
            },
        )
        artifact = storyboard_repo.to_artifact_dict(sv)

    return {
        "project_id": project.id,
        "storyboard": artifact,
        "storyboard_id": sv.id,
        "active_artifact": sv.id,
    }
