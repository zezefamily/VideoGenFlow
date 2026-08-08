"""脚本/分镜版本操作路由:激活指定版本(回退/确认)。

按 id 自动识别脚本或分镜(Phase 3 起分镜也走同一接口)。
Phase 5:按当前用户归属隔离(经版本的 conversation_id 校验)。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.repositories import conversation_repo, script_repo, storyboard_repo
from app.schemas.message import ScriptArtifact
from app.schemas.storyboard import StoryboardArtifact

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


async def _assert_owned(s: AsyncSession, artifact_id: str, user: User) -> None:
    """版本经其 conversation_id 校验归属;不存在或不属于用户 -> 404。"""
    sv = await script_repo.get_script(s, artifact_id)
    if sv is not None:
        conv = await conversation_repo.get_conversation(s, sv.conversation_id)
        if conv is None or conv.owner_id != user.id:
            raise HTTPException(status_code=404, detail="版本不存在")
        return
    sb = await storyboard_repo.get_storyboard(s, artifact_id)
    if sb is not None:
        conv = await conversation_repo.get_conversation(s, sb.conversation_id)
        if conv is None or conv.owner_id != user.id:
            raise HTTPException(status_code=404, detail="版本不存在")
        return
    raise HTTPException(status_code=404, detail="版本不存在")


@router.post("/{artifact_id}/activate")
async def activate_artifact(
    artifact_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    """激活(回退/确认)某个版本。返回 {"type": "script"|"storyboard", ...}。"""
    await _assert_owned(s, artifact_id, current)
    # 先按脚本查
    sv = await script_repo.get_script(s, artifact_id)
    if sv is not None:
        activated = await script_repo.activate_version(s, artifact_id)
        if activated is None:
            raise HTTPException(status_code=404, detail="版本不存在")
        return {
            "type": "script",
            "script": ScriptArtifact(
                **script_repo.to_artifact_dict(activated)
            ).model_dump(),
        }
    # 再按分镜查
    sb = await storyboard_repo.get_storyboard(s, artifact_id)
    if sb is not None:
        activated = await storyboard_repo.activate_version(s, artifact_id)
        if activated is None:
            raise HTTPException(status_code=404, detail="版本不存在")
        return {
            "type": "storyboard",
            "storyboard": StoryboardArtifact(
                **storyboard_repo.to_artifact_dict(activated)
            ).model_dump(),
        }
    raise HTTPException(status_code=404, detail="版本不存在")
