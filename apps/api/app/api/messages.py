"""消息:列表 + 发送(发消息后由后台运行图,SSE 推送回复)。

Phase 5:按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import Conversation, User
from app.repositories import conversation_repo, message_repo, script_repo, storyboard_repo
from app.schemas.message import (
    MessageCreate,
    MessageOut,
    ScriptArtifact,
    SendMessageResponse,
)
from app.schemas.storyboard import StoryboardArtifact
from app.services.run_executor import launch_run
from app.services.run_manager import run_manager

router = APIRouter(
    prefix="/api/conversations/{conv_id}/messages", tags=["messages"]
)


async def _to_out(msg, s: AsyncSession) -> MessageOut:
    artifact = None
    storyboard = None
    if msg.message_type == "script_card" and msg.artifact_id:
        sv = await script_repo.get_script(s, msg.artifact_id)
        if sv is not None:
            artifact = ScriptArtifact(**script_repo.to_artifact_dict(sv))
    elif msg.message_type == "storyboard_card" and msg.artifact_id:
        sb = await storyboard_repo.get_storyboard(s, msg.artifact_id)
        if sb is not None:
            storyboard = StoryboardArtifact(**storyboard_repo.to_artifact_dict(sb))
    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        message_type=msg.message_type,
        artifact_id=msg.artifact_id,
        status=msg.status,
        metadata_json=msg.metadata_json,
        created_at=msg.created_at,
        artifact=artifact,
        storyboard=storyboard,
    )


@router.get("", response_model=list[MessageOut])
async def list_messages(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    msgs = await message_repo.list_messages(s, conv.id)
    return [await _to_out(m, s) for m in msgs]


@router.post("", response_model=SendMessageResponse)
async def send_message(
    payload: MessageCreate,
    request: Request,
    current: User = Depends(get_current_user),
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """发送用户消息:落库 + 建 run + 后台跑图,立即返回 run_id。

    真正的回复通过 GET /api/runs/{run_id}/stream 以 SSE 推送。
    """
    user_msg = await message_repo.create_message(s, conv.id, "user", payload.content)
    from app.repositories import run_repo

    run = await run_repo.create_run(s, conv.id, user_msg.id)
    await conversation_repo.touch(s, conv.id)

    run_manager.register(run.id)

    graph = request.app.state.graph
    launch_run(
        graph,
        conversation_id=conv.id,
        run_id=run.id,
        user_message_id=user_msg.id,
        thread_id=conv.thread_id,
        user_input=payload.content,
        owner_id=current.id,
    )

    return SendMessageResponse(run_id=run.id, message_id=user_msg.id)
