"""会话仓库。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    Message,
    Project,
    Run,
    ScriptVersion,
    StoryboardImage,
    StoryboardVersion,
    VideoAnalysis,
)


async def create_conversation(
    s: AsyncSession, title: Optional[str], owner_id: str
) -> Conversation:
    conv = Conversation(title=title or "新会话", owner_id=owner_id)
    s.add(conv)
    await s.commit()
    await s.refresh(conv)
    return conv


async def get_conversation(s: AsyncSession, conv_id: str) -> Optional[Conversation]:
    return await s.get(Conversation, conv_id)


async def list_conversations(
    s: AsyncSession, owner_id: str, include_archived: bool = False
) -> list[Conversation]:
    q = select(Conversation).where(Conversation.owner_id == owner_id).order_by(Conversation.updated_at.desc())
    if not include_archived:
        q = q.where(Conversation.archived_at.is_(None))
    return list((await s.execute(q)).scalars().all())


async def rename_conversation(
    s: AsyncSession, conv_id: str, title: str
) -> Optional[Conversation]:
    conv = await s.get(Conversation, conv_id)
    if conv is None:
        return None
    conv.title = title
    await s.commit()
    await s.refresh(conv)
    return conv


async def archive_conversation(s: AsyncSession, conv_id: str) -> bool:
    conv = await s.get(Conversation, conv_id)
    if conv is None:
        return False
    conv.archived_at = datetime.utcnow()
    await s.commit()
    return True


async def hard_delete_conversation(s: AsyncSession, conv_id: str) -> list[str]:
    """硬删除会话及其全部子数据,返回需要清理的图片本地路径(local_path)。

    显式按依赖顺序删除(跨 SQLite/Postgres 一致,且能收集文件路径)。
    """
    # 先收集图片本地路径(供调用方删盘/删对象)
    img_q = select(StoryboardImage.local_path).where(
        StoryboardImage.conversation_id == conv_id,
        StoryboardImage.local_path.is_not(None),
    )
    local_paths = [r for r in (await s.execute(img_q)).scalars().all() if r]

    # 依赖顺序删除子表
    await s.execute(delete(StoryboardImage).where(StoryboardImage.conversation_id == conv_id))
    await s.execute(delete(StoryboardVersion).where(StoryboardVersion.conversation_id == conv_id))
    await s.execute(delete(ScriptVersion).where(ScriptVersion.conversation_id == conv_id))
    await s.execute(delete(VideoAnalysis).where(VideoAnalysis.conversation_id == conv_id))
    await s.execute(delete(Project).where(Project.conversation_id == conv_id))
    await s.execute(delete(Message).where(Message.conversation_id == conv_id))
    await s.execute(delete(Run).where(Run.conversation_id == conv_id))
    await s.execute(delete(Conversation).where(Conversation.id == conv_id))
    await s.commit()
    return local_paths


async def touch(s: AsyncSession, conv_id: str) -> None:
    """更新 updated_at,用于会话排序。"""
    conv = await s.get(Conversation, conv_id)
    if conv is not None:
        conv.updated_at = datetime.utcnow()
        await s.commit()
