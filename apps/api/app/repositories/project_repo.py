"""项目仓库。"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


async def create_project(
    s: AsyncSession, conversation_id: str, title: str = ""
) -> Project:
    proj = Project(conversation_id=conversation_id, title=title)
    s.add(proj)
    await s.commit()
    await s.refresh(proj)
    return proj


async def get_project(s: AsyncSession, project_id: str) -> Optional[Project]:
    return await s.get(Project, project_id)


async def get_conversation_project(
    s: AsyncSession, conversation_id: str
) -> Optional[Project]:
    """取会话的当前激活项目(可能为空)。"""
    from app.models import Conversation

    conv = await s.get(Conversation, conversation_id)
    if conv is None or not conv.active_project_id:
        return None
    return await s.get(Project, conv.active_project_id)


async def list_projects_by_conversation(
    s: AsyncSession, conversation_id: str
) -> list[Project]:
    """会话下的全部项目(导出用)。"""
    q = (
        select(Project)
        .where(Project.conversation_id == conversation_id)
        .order_by(Project.created_at.asc())
    )
    return list((await s.execute(q)).scalars().all())


async def ensure_project(
    s: AsyncSession, conversation_id: str, title: str = ""
) -> Project:
    """确保会话有激活项目,没有则创建并设为激活。"""
    from app.models import Conversation

    proj = await get_conversation_project(s, conversation_id)
    if proj is not None:
        return proj
    proj = await create_project(s, conversation_id, title)
    conv = await s.get(Conversation, conversation_id)
    if conv is not None:
        conv.active_project_id = proj.id
        await s.commit()
    return proj
