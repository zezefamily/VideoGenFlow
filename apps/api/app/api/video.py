"""视频成片路由(成片管线):静态分镜 + 音频 + 字幕合成 mp4。

按当前用户归属隔离(同 TTS 路由)。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import Conversation, User
from app.repositories import conversation_repo, project_repo, video_render_repo
from app.schemas.video import VideoRenderOut
from app.services import video_render_service

router = APIRouter(prefix="/api/conversations", tags=["video"])
regen_router = APIRouter(prefix="/api/video-renders", tags=["video"])


@router.post("/{conv_id}/video/render", response_model=VideoRenderOut)
async def render_video(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """静态分镜 + 当前配音音频 + 字幕 -> mp4(后台合成,前端轮询)。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        raise HTTPException(status_code=400, detail="当前没有作品,请先创作脚本")
    try:
        artifact = await video_render_service.start_render(
            conversation_id=conv.id, project_id=project.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return VideoRenderOut(**artifact)


@router.get("/{conv_id}/video", response_model=Optional[VideoRenderOut])
async def get_video(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话当前成片(前端轮询用);无成片返回 null。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        return None
    artifact = await video_render_service.get_render_for_conversation(conv.id, project.id)
    return VideoRenderOut(**artifact) if artifact else None


@router.post("/{conv_id}/video/cancel")
async def cancel_video(conv: Conversation = Depends(get_owned_conversation)):
    """取消会话当前进行中的成片合成。"""
    return await video_render_service.cancel_render(conv.id)


@regen_router.post("/{render_id}/regenerate", response_model=VideoRenderOut)
async def regenerate_video(
    render_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    render = await video_render_repo.get_render(s, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="成片不存在")
    # 校验归属:成片 -> 会话 -> owner
    conv = await conversation_repo.get_conversation(s, render.conversation_id)
    if conv is None or conv.owner_id != current.id:
        raise HTTPException(status_code=404, detail="成片不存在")
    result = await video_render_service.regenerate(render_id)
    if result is None:
        raise HTTPException(status_code=404, detail="成片不存在")
    return VideoRenderOut(**result)
