"""用量统计路由(Phase 5):当前用户的生成用量 + 最近生成日志。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.repositories import generation_log_repo

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage(
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    summary = await generation_log_repo.usage_summary(s, current.id)
    logs = await generation_log_repo.list_logs(s, current.id, limit=50)
    return {
        "user": {"id": current.id, "email": current.email},
        "usage": summary,
        "recent": [
            {
                "id": log.id,
                "kind": log.kind,
                "prompt_template_name": log.prompt_template_name,
                "prompt_template_version": log.prompt_template_version,
                "model": log.model,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "conversation_id": log.conversation_id,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
