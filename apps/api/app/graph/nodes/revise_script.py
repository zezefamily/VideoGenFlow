"""局部修改脚本(Phase 2 核心能力):只改 scope 范围,存为新版本。

走 script_service.revise_script(旧脚本全文 + 范围 + 修改要求) -> 返回只改了局部的新脚本。
新版本归入同一 project,旧版本自动失活,支持回退。
Phase 5:记录生成日志(prompt/模型版本)。
"""

import time

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import conversation_repo, project_repo, script_repo
from app.services import genlog, script_service


@tracked("revise_script")
async def revise_script(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    prev_script = state.get("script")
    scope = state.get("scope", "whole")
    instruction = state.get("instruction", "")

    if not prev_script:
        # 没有旧脚本无法修改:回退提示(理论上 classify 已挡住)
        return {
            "final_text": "当前还没有脚本，无法修改。请先告诉我你想创作什么主题。",
            "message_type": "text",
            "artifact_id": None,
        }

    t0 = time.perf_counter()
    data = await script_service.revise_script(
        previous_script=prev_script,
        instruction=instruction,
        scope=scope,
    )
    await genlog.log_generation(
        kind="script",
        owner_id=owner_id,
        conversation_id=conv_id,
        prompt_name="revise_script",
        prompt_version=prompt_version("revise_script"),
        model=settings.deepseek_model,
        status="ok",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    async with AsyncSessionLocal() as s:
        # revise 一定已有 project;保险起见 ensure 一次
        project = await project_repo.ensure_project(
            s, conv_id, title=data.get("title", "")
        )
        sv = await script_repo.create_script_version(s, conv_id, project.id, data)
        if data.get("title"):
            await conversation_repo.rename_conversation(s, conv_id, data["title"].strip())
        artifact = script_repo.to_artifact_dict(sv)

    return {
        "project_id": project.id,
        "script": artifact,
        "script_id": sv.id,
        "active_artifact": sv.id,
    }
