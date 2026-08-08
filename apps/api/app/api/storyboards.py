"""分镜路由:取会话当前作品的分镜版本(Phase 3)。

Phase 5:按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_owned_conversation
from app.models import Conversation
from app.repositories import project_repo, storyboard_repo
from app.schemas.storyboard import StoryboardDetail

router = APIRouter(prefix="/api/conversations", tags=["storyboards"])


@router.get("/{conv_id}/storyboard", response_model=StoryboardDetail)
async def get_conversation_storyboard(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话当前作品的分镜版本(升序)+ 当前激活版本。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        return StoryboardDetail(versions=[], active=None)

    versions = await storyboard_repo.list_storyboard_versions(s, project.id)
    version_dicts = [storyboard_repo.to_artifact_dict(v) for v in versions]
    active = next((v for v in version_dicts if v.get("is_active")), None)
    return StoryboardDetail(versions=version_dicts, active=active)
