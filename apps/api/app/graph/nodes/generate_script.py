"""生成脚本:全新生成,写入新版本(Phase 2 作品化,按 project 隔离)。

局部修改走独立的 revise_script 节点,不进这里。
Phase 5:记录生成日志(prompt/模型版本)。
"""

import time

from app.config import settings
from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.prompts import prompt_version
from app.repositories import conversation_repo, project_repo, script_repo
from app.services import genlog, script_service


@tracked("generate_script")
async def generate_script(state):
    conv_id = state["conversation_id"]
    owner_id = state.get("user_id") or None
    user_input = state.get("user_input", "")

    t0 = time.perf_counter()
    # 全新生成:统一提示词(与做同款同源),用户输入即创作主题
    data = await script_service.generate_script(topic=user_input)
    await genlog.log_generation(
        kind="script",
        owner_id=owner_id,
        conversation_id=conv_id,
        prompt_name="script_generation",
        prompt_version=prompt_version("script_generation"),
        model=settings.deepseek_model,
        status="ok" if data.get("title") != "生成失败" else "error",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    async with AsyncSessionLocal() as s:
        project = await project_repo.ensure_project(s, conv_id, title=data.get("title", ""))
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
