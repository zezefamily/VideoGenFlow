"""生成日志辅助(Phase 5):开自己的 session 落一条日志,不影响调用方事务。

用法:在节点里包住 service 调用,记录 kind/prompt 名+版本/模型/耗时/状态。
失败不抛(日志不能影响主流程)。
"""

import time
from contextlib import asynccontextmanager
from typing import Optional

from app.db import AsyncSessionLocal
from app.repositories import generation_log_repo


@asynccontextmanager
async def timed():
    """计时上下文,yield (开始时间戳);退出时算 duration_ms。"""
    start = time.perf_counter()
    yield start
    # duration 在调用方按需用 perf_counter() - start 计算


async def log_generation(
    *,
    kind: str,
    owner_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    prompt_name: Optional[str] = None,
    prompt_version: Optional[str] = None,
    model: Optional[str] = None,
    params: Optional[dict] = None,
    artifact_id: Optional[str] = None,
    status: str = "ok",
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
) -> None:
    try:
        async with AsyncSessionLocal() as s:
            await generation_log_repo.create_log(
                s,
                kind=kind,
                owner_id=owner_id,
                conversation_id=conversation_id,
                prompt_template_name=prompt_name,
                prompt_template_version=prompt_version,
                model=model,
                params=params,
                artifact_id=artifact_id,
                status=status,
                error=error,
                duration_ms=duration_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
    except Exception:
        # 日志失败不影响主流程
        pass
