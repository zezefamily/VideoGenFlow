"""局部修改分镜(Phase 3):只改点名镜头,存为新版本。

走 scoped regenerate:旧分镜全文 + instruction -> 只改相关镜头。
依赖的图片失效留待 Phase 4。
Phase 5:记录生成日志(prompt/模型版本)。
"""

import time

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import project_repo, storyboard_repo
from app.services import genlog, storyboard_service


@tracked("revise_storyboard")
async def revise_storyboard(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    prev = state.get("storyboard")
    instruction = state.get("instruction", "")

    if not prev or not prev.get("shots"):
        return {
            "final_text": "当前还没有分镜，无法修改。先让我生成分镜吧。",
            "message_type": "text",
            "artifact_id": None,
        }

    t0 = time.perf_counter()
    data = await storyboard_service.revise_storyboard(
        previous_shots=prev.get("shots", []),
        instruction=instruction,
    )
    await genlog.log_generation(
        kind="storyboard",
        owner_id=owner_id,
        conversation_id=conv_id,
        prompt_name="storyboard_revise",
        prompt_version=prompt_version("storyboard_revise"),
        model=settings.deepseek_model,
        status="ok" if data.get("shots") else "error",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    if not data.get("shots"):
        return {
            "final_text": "分镜修改失败，请稍后重试：" + data.get("error", "未知错误"),
            "message_type": "text",
            "artifact_id": None,
        }

    async with AsyncSessionLocal() as s:
        project = await project_repo.ensure_project(s, conv_id)
        sv = await storyboard_repo.create_storyboard_version(
            s,
            conv_id,
            project.id,
            {
                "script_version_id": prev.get("script_version_id"),
                "aspect_ratio": prev.get("aspect_ratio", "16:9"),
                "style": prev.get("style", ""),
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
