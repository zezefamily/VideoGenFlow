"""视频分析仓库(抖音链接解析 / 做同款)。"""

import json
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoAnalysis


async def create_analysis(s: AsyncSession, **fields) -> VideoAnalysis:
    va = VideoAnalysis(**fields)
    s.add(va)
    await s.commit()
    await s.refresh(va)
    return va


async def get_analysis(s: AsyncSession, analysis_id: str) -> Optional[VideoAnalysis]:
    return await s.get(VideoAnalysis, analysis_id)


async def get_latest_by_conversation(
    s: AsyncSession, conversation_id: str
) -> Optional[VideoAnalysis]:
    """会话最近一次视频分析(前端轮询 / 流式卡片用)。"""
    q = (
        select(VideoAnalysis)
        .where(VideoAnalysis.conversation_id == conversation_id)
        .order_by(VideoAnalysis.created_at.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def update_analysis(
    s: AsyncSession, analysis_id: str, **fields
) -> Optional[VideoAnalysis]:
    va = await s.get(VideoAnalysis, analysis_id)
    if va is None:
        return None
    for k, v in fields.items():
        setattr(va, k, v)
    await s.commit()
    await s.refresh(va)
    return va


async def mark_analyzing_stale(s: AsyncSession) -> int:
    """启动清理:把上次中断的 pending/analyzing 标为 error(进程已重启)。"""
    result = await s.execute(
        update(VideoAnalysis)
        .where(VideoAnalysis.status.in_(["pending", "analyzing"]))
        .values(status="error", error="分析被中断(服务重启)")
    )
    await s.commit()
    return result.rowcount or 0


def to_artifact_dict(va: VideoAnalysis, script: Optional[dict] = None) -> dict:
    """转前端 artifact。script 为关联仿写脚本的 artifact dict(已由调用方取出)。"""
    try:
        video_info = json.loads(va.video_info_json) if va.video_info_json else None
    except (json.JSONDecodeError, TypeError):
        video_info = None
    try:
        analysis = json.loads(va.analysis_json) if va.analysis_json else None
    except (json.JSONDecodeError, TypeError):
        analysis = None
    return {
        "id": va.id,
        "conversation_id": va.conversation_id,
        "project_id": va.project_id,
        "share_link": va.share_link,
        "status": va.status,
        "method": va.method,
        "video_info": video_info,
        "transcript": va.transcript,
        "analysis": analysis,
        "script_version_id": va.script_version_id,
        "script": script,
        "error": va.error,
        "created_at": va.created_at.isoformat() if va.created_at else None,
        "updated_at": va.updated_at.isoformat() if va.updated_at else None,
    }
