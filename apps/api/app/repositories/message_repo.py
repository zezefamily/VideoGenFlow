"""消息仓库。"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message


async def create_message(
    s: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    artifact_id: Optional[str] = None,
    status: str = "complete",
    metadata_json: Optional[str] = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_type=message_type,
        artifact_id=artifact_id,
        status=status,
        metadata_json=metadata_json,
    )
    s.add(msg)
    await s.commit()
    await s.refresh(msg)
    return msg


async def get_message(s: AsyncSession, msg_id: str) -> Optional[Message]:
    return await s.get(Message, msg_id)


async def list_messages(
    s: AsyncSession, conversation_id: str, limit: int = 200
) -> list[Message]:
    q = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list((await s.execute(q)).scalars().all())


async def get_last_message(
    s: AsyncSession, conversation_id: str
) -> Optional[Message]:
    q = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def finalize_message(
    s: AsyncSession,
    msg_id: str,
    content: str,
    status: str = "complete",
    message_type: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> Optional[Message]:
    """流式结束后回写最终内容。"""
    msg = await s.get(Message, msg_id)
    if msg is None:
        return None
    msg.content = content
    msg.status = status
    if message_type is not None:
        msg.message_type = message_type
    if artifact_id is not None:
        msg.artifact_id = artifact_id
    await s.commit()
    await s.refresh(msg)
    return msg
