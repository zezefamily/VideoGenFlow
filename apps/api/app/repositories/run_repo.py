"""运行仓库。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Run


async def create_run(
    s: AsyncSession, conversation_id: str, input_message_id: str
) -> Run:
    run = Run(conversation_id=conversation_id, input_message_id=input_message_id)
    s.add(run)
    await s.commit()
    await s.refresh(run)
    return run


async def get_run(s: AsyncSession, run_id: str) -> Optional[Run]:
    return await s.get(Run, run_id)


async def get_active_run_for_conversation(
    s: AsyncSession, conversation_id: str
) -> Optional[Run]:
    q = (
        select(Run)
        .where(Run.conversation_id == conversation_id, Run.status == "running")
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalar_one_or_none()


async def update_run(
    s: AsyncSession,
    run_id: str,
    *,
    status: Optional[str] = None,
    current_node: Optional[str] = None,
    error_json: Optional[str] = None,
    usage_json: Optional[str] = None,
) -> Optional[Run]:
    run = await s.get(Run, run_id)
    if run is None:
        return None
    if status is not None:
        run.status = status
    if current_node is not None:
        run.current_node = current_node
    if error_json is not None:
        run.error_json = error_json
    if usage_json is not None:
        run.usage_json = usage_json
    if status in ("completed", "error", "cancelled"):
        run.finished_at = datetime.utcnow()
    await s.commit()
    return run
