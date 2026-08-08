"""视频分析路由(抖音链接解析 / 做同款):取最新 / 取单条(前端轮询)。

Phase 5:按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import Conversation, User
from app.repositories import conversation_repo, video_analysis_repo
from app.schemas.video_analysis import (
    VideoAnalysisLatestOut,
    VideoAnalysisOut,
)
from app.services import video_analysis_service

router = APIRouter(prefix="/api/conversations", tags=["video-analysis"])


@router.get("/{conv_id}/video-analysis", response_model=VideoAnalysisLatestOut)
async def get_latest_analysis(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话最近一次视频分析(前端轮询用)。"""
    va = await video_analysis_repo.get_latest_by_conversation(s, conv.id)
    if va is None:
        return VideoAnalysisLatestOut(analysis=None, has_active=False)
    artifact = await video_analysis_service.to_artifact_dict(va.id)
    return VideoAnalysisLatestOut(
        analysis=VideoAnalysisOut(**artifact) if artifact else None,
        has_active=va.status in ("pending", "analyzing"),
    )


# 单条查询(单独挂在 /api/video-analyses 下,供持久化消息卡片按 artifact_id 拉取)
detail_router = APIRouter(prefix="/api/video-analyses", tags=["video-analysis"])


@detail_router.get("/{analysis_id}", response_model=VideoAnalysisOut)
async def get_analysis(
    analysis_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    va = await video_analysis_repo.get_analysis(s, analysis_id)
    if va is None:
        raise HTTPException(status_code=404, detail="分析不存在")
    # 校验归属:分析 -> 会话 -> owner
    conv = await conversation_repo.get_conversation(s, va.conversation_id)
    if conv is None or conv.owner_id != current.id:
        raise HTTPException(status_code=404, detail="分析不存在")
    artifact = await video_analysis_service.to_artifact_dict(analysis_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="分析不存在")
    return VideoAnalysisOut(**artifact)
