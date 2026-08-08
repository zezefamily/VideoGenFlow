"""分镜图片路由(Phase 4):列表/批量生成/单张重绘/取消。

Phase 5:按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import Conversation, User
from app.repositories import conversation_repo, image_repo, project_repo, storyboard_repo
from app.schemas.image import ImageListOut, StoryboardImageOut
from app.services import image_service

router = APIRouter(prefix="/api/conversations", tags=["images"])


def _has_active(images) -> bool:
    return any(i.status in ("pending", "generating") for i in images)


@router.get("/{conv_id}/images", response_model=ImageListOut)
async def list_images(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话当前分镜的图片(前端轮询用)。"""
    images = await image_repo.list_images_by_conversation(s, conv.id)
    return ImageListOut(
        images=[StoryboardImageOut(**image_repo.to_artifact_dict(i)) for i in images],
        has_active=_has_active(images),
    )


@router.post("/{conv_id}/images/generate", response_model=list[StoryboardImageOut])
async def generate_images(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """显式批量生成(按当前激活分镜)。聊天里说"生成图片"也走同一条服务路径。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        raise HTTPException(status_code=400, detail="当前没有作品,请先创作脚本与分镜")
    sb = await storyboard_repo.get_active_storyboard(s, project.id)
    if sb is None:
        raise HTTPException(status_code=400, detail="当前没有分镜,请先生成分镜")
    artifact = storyboard_repo.to_artifact_dict(sb)
    images = await image_service.start_generation(
        storyboard_artifact=artifact,
        conversation_id=conv.id,
        project_id=project.id,
        storyboard_version_id=sb.id,
    )
    return [StoryboardImageOut(**i) for i in images]


@router.post("/{conv_id}/images/cancel")
async def cancel_images(conv: Conversation = Depends(get_owned_conversation)):
    """取消会话当前进行中的图片生成。"""
    return await image_service.cancel_generation(conv.id)


# 单张重绘(单独挂在 /api/images 下,不带 conversation 前缀)
regen_router = APIRouter(prefix="/api/images", tags=["images"])


@regen_router.post("/{image_id}/regenerate", response_model=StoryboardImageOut)
async def regenerate_image(
    image_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    img = await image_repo.get_image(s, image_id)
    if img is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    # 校验归属:图片 -> 会话 -> owner
    conv = await conversation_repo.get_conversation(s, img.conversation_id)
    if conv is None or conv.owner_id != current.id:
        raise HTTPException(status_code=404, detail="图片不存在")
    result = await image_service.regenerate_single(image_id)
    if result is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return StoryboardImageOut(**result)
