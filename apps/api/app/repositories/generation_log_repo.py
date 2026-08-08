"""生成日志仓库(Phase 5:Prompt/模型版本记录 + 用量统计)。"""

import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GenerationLog


async def create_log(
    s: AsyncSession,
    *,
    kind: str,
    owner_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    prompt_template_name: Optional[str] = None,
    prompt_template_version: Optional[str] = None,
    model: Optional[str] = None,
    params: Optional[dict] = None,
    artifact_id: Optional[str] = None,
    status: str = "ok",
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
) -> GenerationLog:
    log = GenerationLog(
        kind=kind,
        owner_id=owner_id,
        conversation_id=conversation_id,
        prompt_template_name=prompt_template_name,
        prompt_template_version=prompt_template_version,
        model=model,
        params_json=json.dumps(params, ensure_ascii=False) if params else None,
        artifact_id=artifact_id,
        status=status,
        error=error,
        duration_ms=duration_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    s.add(log)
    await s.commit()
    return log


async def usage_summary(s: AsyncSession, owner_id: str) -> dict:
    """按 kind 汇总当前用户的生成次数(用于用量统计)。"""
    q = (
        select(GenerationLog.kind, func.count(GenerationLog.id))
        .where(GenerationLog.owner_id == owner_id)
        .group_by(GenerationLog.kind)
    )
    rows = (await s.execute(q)).all()
    by_kind = {kind: count for kind, count in rows}
    total = sum(by_kind.values())
    return {"total": total, "by_kind": by_kind}


async def list_logs(
    s: AsyncSession, owner_id: str, limit: int = 50
) -> list[GenerationLog]:
    q = (
        select(GenerationLog)
        .where(GenerationLog.owner_id == owner_id)
        .order_by(GenerationLog.created_at.desc())
        .limit(limit)
    )
    return list((await s.execute(q)).scalars().all())
