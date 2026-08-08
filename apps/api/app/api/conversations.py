"""会话 CRUD:新建/列表/详情/重命名/删除(软删除+硬删除级联)。

Phase 5:所有操作按当前用户归属隔离。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import User
from app.repositories import conversation_repo, message_repo, run_repo
from app.schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationSummary,
    ConversationUpdate,
)
from app.services import storage as storage_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    conv = await conversation_repo.create_conversation(s, payload.title, current.id)
    # 空会话也应有一个可行动的起点，而不是让用户面对空白聊天页。
    await message_repo.create_message(
        s,
        conv.id,
        "assistant",
        "你好，我是你的短视频创作搭档。发一条抖音链接让我拆解做同款，给我一个话题从零创作，或直接贴一段口播文案，我会陪你一步步做成视频。",
        message_type="agent_welcome",
    )
    return conv


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    convs = await conversation_repo.list_conversations(s, current.id)
    result = []
    for c in convs:
        last = await message_repo.get_last_message(s, c.id)
        preview = None
        if last is not None:
            preview = (last.content or "")[:60]
        result.append(
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message_preview=preview,
            )
        )
    return result


@router.get("/{conv_id}", response_model=ConversationOut)
async def get_conversation(conv=Depends(get_owned_conversation)):
    return conv


@router.get("/{conv_id}/active-run")
async def get_active_run(
    conv=Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """返回会话正在执行的 Agent Run，供用户切回会话后恢复进度。"""
    run = await run_repo.get_active_run_for_conversation(s, conv.id)
    if run is None:
        return {"run": None}
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "current_node": run.current_node,
            "started_at": run.started_at.isoformat() if run.started_at else None,
        }
    }


@router.patch("/{conv_id}", response_model=ConversationOut)
async def update_conversation(
    payload: ConversationUpdate,
    conv=Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    renamed = await conversation_repo.rename_conversation(s, conv.id, payload.title or "")
    return renamed


@router.delete("/{conv_id}")
async def delete_conversation(
    conv=Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
    hard: bool = True,
):
    """删除会话。hard=True(默认)级联硬删除全部子数据并清理图片文件;
    hard=False 仅软归档(保留可恢复)。"""
    if hard:
        local_paths = await conversation_repo.hard_delete_conversation(s, conv.id)
        for p in local_paths:
            await storage_service.delete_by_web_path(p)
        return {"ok": True, "hard": True}
    await conversation_repo.archive_conversation(s, conv.id)
    return {"ok": True, "hard": False}


@router.get("/{conv_id}/export")
async def export_conversation(
    conv=Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """导出会话全部数据为 JSON(消息/作品/脚本版本/分镜版本/图片元数据)。

    Phase 5 数据导出:满足可移植与合规留存。
    """
    from app.repositories import (
        image_repo,
        message_repo,
        project_repo,
        script_repo,
        storyboard_repo,
    )

    messages = await message_repo.list_messages(s, conv.id)
    projects = await project_repo.list_projects_by_conversation(s, conv.id)
    projects_out = []
    for p in projects:
        scripts = await script_repo.list_versions(s, p.id)
        storyboards = await storyboard_repo.list_storyboard_versions(s, p.id)
        projects_out.append(
            {
                "id": p.id,
                "title": p.title,
                "created_at": p.created_at,
                "script_versions": [script_repo.to_artifact_dict(v) for v in scripts],
                "storyboard_versions": [
                    storyboard_repo.to_artifact_dict(v) for v in storyboards
                ],
            }
        )
    images = await image_repo.list_images_by_conversation(s, conv.id)
    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "artifact_id": m.artifact_id,
                "status": m.status,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "projects": projects_out,
        "images": [image_repo.to_artifact_dict(i) for i in images],
    }
