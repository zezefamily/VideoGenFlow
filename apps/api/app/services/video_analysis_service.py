"""视频分析服务(抖音链接解析 / 做同款)。

后台任务模式(与分镜图片一致):
- start_analysis:建 pending 记录 + 启动后台任务,立即返回(节点不阻塞)
- run_analysis_task:提取文案 -> LLM 拆解爆款 -> LLM 仿写原创脚本 -> 落库

仿写脚本会作为作品激活脚本(ScriptVersion)落库,前端可接着生成分镜/出图。
"""

import json
import re
import time
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.db import AsyncSessionLocal
from app.prompts import VIDEO_ANALYZE_PROMPT, VIDEO_REWRITE_PROMPT, prompt_version
from app.repositories import conversation_repo, script_repo, video_analysis_repo
from app.services import genlog, media_service, task_runner
from app.services.llm import get_llm
from app.utils import parse_llm_json


# ============================================================
# JSON 解析容错(同 script_service 风格)
# ============================================================

def _parse_json(result_text: str) -> Optional[dict]:
    return parse_llm_json(result_text)


# ============================================================
# LLM:爆款拆解
# ============================================================

async def _analyze_transcript(transcript: str, video_info: dict) -> Optional[dict]:
    try:
        llm = get_llm(response_format={"type": "json_object"}, temperature=0.3)
        prompt = ChatPromptTemplate.from_messages(
            [("system", VIDEO_ANALYZE_PROMPT), ("human", "请开始拆解。")]
        )
        chain = prompt | llm
        topics = video_info.get("topics", []) or []
        resp = await chain.ainvoke(
            {
                "title": video_info.get("title", ""),
                "author": video_info.get("author", ""),
                "duration": video_info.get("duration", 0),
                "like_count": video_info.get("like_count", 0),
                "topics": " ".join(f"#{t}" for t in topics) if topics else "无",
                "transcript": transcript or "（无文案）",
            }
        )
        return _parse_json(resp.content.strip())
    except Exception:
        return None


# ============================================================
# LLM:仿写口播文案(做同款,仅依赖原版文案+示例1,模型自行拆解句式与文风)
# ============================================================

async def _rewrite_script(transcript: str) -> Optional[dict]:
    try:
        llm = get_llm(
            response_format={"type": "json_object"},
            temperature=0.8,
            thinking="enabled",
            reasoning_effort="max",  # 仿写口播文案质量优先,拉满思考强度
        )
        prompt = ChatPromptTemplate.from_messages(
            [("system", VIDEO_REWRITE_PROMPT), ("human", "请开始创作。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke(
            {
                "topic": "",  # 做同款:主题由模型参考示例1与原版文案自拟
                "transcript": transcript or "",
            }
        )
        data = _parse_json(resp.content.strip())
        if isinstance(data, dict):
            data["content"] = data.get("content", "") or ""
            return data
        return None
    except Exception:
        return None


# ============================================================
# 启动分析(节点调用)
# ============================================================

async def start_analysis(
    conversation_id: str,
    project_id: str,
    share_link: str,
    owner_id: Optional[str] = None,
) -> dict:
    """建 pending 记录并启动后台分析,返回初始 artifact(pending)供立即回显。"""
    async with AsyncSessionLocal() as s:
        va = await video_analysis_repo.create_analysis(
            s,
            conversation_id=conversation_id,
            project_id=project_id,
            owner_id=owner_id,
            share_link=share_link,
            status="pending",
        )

    await task_runner.submit(
        "video_analysis",
        conversation_id=conversation_id,
        analysis_id=va.id,
        project_id=project_id,
        share_link=share_link,
        owner_id=owner_id or "",
    )
    return video_analysis_repo.to_artifact_dict(va)


# ============================================================
# 后台任务:提取 -> 拆解 -> 仿写 -> 落库
# ============================================================

async def run_analysis_task(
    conversation_id: str,
    analysis_id: str,
    project_id: str,
    share_link: str,
    owner_id: str = "",
) -> None:
    """后台执行:作为可注册任务(进程内 asyncio / Arq 共用)。"""
    t0 = time.perf_counter()

    # 1. 标记 analyzing
    async with AsyncSessionLocal() as s:
        await video_analysis_repo.update_analysis(s, analysis_id, status="analyzing")

    # 2. 提取文案 + 视频信息(同步管线在线程池跑)
    transcript, method, video_info = await media_service.extract_script(share_link)

    if not transcript:
        # 提取失败:落 video_info 与错误,结束
        async with AsyncSessionLocal() as s:
            await video_analysis_repo.update_analysis(
                s,
                analysis_id,
                status="error",
                method="failed",
                video_info_json=json.dumps(video_info, ensure_ascii=False),
                error=f"无法提取视频文案（{method}）。可能是链接失效、需要登录 cookie 或平台限制。",
            )
        await genlog.log_generation(
            kind="video_analysis",
            owner_id=owner_id or None,
            conversation_id=conversation_id,
            artifact_id=analysis_id,
            prompt_name="video_analyze",
            prompt_version=prompt_version("video_analyze"),
            model=settings.deepseek_model,
            params={"share_link": share_link, "method": method},
            status="error",
            error="extract failed",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return

    # 3. LLM 拆解爆款
    analysis = await _analyze_transcript(transcript, video_info)
    analysis_json = (
        json.dumps(analysis, ensure_ascii=False) if analysis else None
    )

    # 4. LLM 仿写原创脚本
    script_data = None
    if analysis:
        script_data = await _rewrite_script(transcript)

    # 5. 仿写脚本落为作品激活脚本(ScriptVersion),并关联到分析记录
    script_version_id = None
    if script_data and script_data.get("content"):
        async with AsyncSessionLocal() as s:
            sv = await script_repo.create_script_version(
                s, conversation_id, project_id, script_data
            )
            if script_data.get("title"):
                await conversation_repo.rename_conversation(
                    s, conversation_id, script_data["title"].strip()
                )
            script_version_id = sv.id

    # 6. 更新分析记录为 done
    async with AsyncSessionLocal() as s:
        await video_analysis_repo.update_analysis(
            s,
            analysis_id,
            status="done",
            method=method,
            video_info_json=json.dumps(video_info, ensure_ascii=False),
            transcript=transcript,
            analysis_json=analysis_json,
            script_version_id=script_version_id,
            error=None,
        )

    await genlog.log_generation(
        kind="video_analysis",
        owner_id=owner_id or None,
        conversation_id=conversation_id,
        artifact_id=analysis_id,
        prompt_name="video_analyze",
        prompt_version=prompt_version("video_analyze"),
        model=settings.deepseek_model,
        params={
            "share_link": share_link,
            "method": method,
            "has_analysis": analysis is not None,
            "has_script": script_version_id is not None,
        },
        status="ok",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


# 注册为后台任务(供 task_runner 调度;Arq worker 也引用同一函数)
task_runner.register_task("video_analysis", run_analysis_task)


# ============================================================
# artifact 组装(带仿写脚本)
# ============================================================

async def to_artifact_dict(analysis_id: str) -> Optional[dict]:
    """取分析记录并附带仿写脚本 artifact(供 API / 节点回显)。"""
    async with AsyncSessionLocal() as s:
        va = await video_analysis_repo.get_analysis(s, analysis_id)
        if va is None:
            return None
        script = None
        if va.script_version_id:
            sv = await script_repo.get_script(s, va.script_version_id)
            if sv is not None:
                script = script_repo.to_artifact_dict(sv)
        return video_analysis_repo.to_artifact_dict(va, script=script)
