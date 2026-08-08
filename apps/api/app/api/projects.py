"""作品(项目)路由:取会话当前作品及其全部版本(Phase 2)。

Phase 5:按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_owned_conversation
from app.models import Conversation
from app.repositories import project_repo, script_repo
from app.schemas.project import ProjectDetail, ProjectOut

router = APIRouter(prefix="/api/conversations", tags=["projects"])


@router.get("/{conv_id}/project", response_model=ProjectDetail)
async def get_conversation_project(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话当前激活作品 + 全部版本(按版本升序)+ 当前激活版本。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        return ProjectDetail(project=None, versions=[], active=None)

    versions = await script_repo.list_versions(s, project.id)
    version_dicts = [script_repo.to_artifact_dict(v) for v in versions]
    active = next((v for v in version_dicts if v.get("is_active")), None)
    return ProjectDetail(
        project=ProjectOut.model_validate(project),
        versions=version_dicts,
        active=active,
    )
