"""Run:SSE 流 + 取消。

Phase 5:校验 run 归属当前用户(SSE 走 ?token= 查询参数鉴权)。
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.deps import get_current_user, get_current_user_query
from app.models import User
from app.repositories import conversation_repo, run_repo
from app.schemas.events import SSEEvent
from app.services.run_manager import run_manager

router = APIRouter(prefix="/api/runs", tags=["runs"])


async def _assert_run_owned(s: AsyncSession, run_id: str, user: User) -> None:
    run = await run_repo.get_run(s, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    conv = await conversation_repo.get_conversation(s, run.conversation_id)
    if conv is None or conv.owner_id != user.id:
        raise HTTPException(status_code=404, detail="run 不存在")


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    current: User = Depends(get_current_user_query),
    s: AsyncSession = Depends(get_session),
):
    """以 SSE 推送一次运行的全部事件,直到 done/error。"""
    await _assert_run_owned(s, run_id, current)
    queue = run_manager.get(run_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="run 不存在或已结束")

    async def event_gen():
        try:
            while True:
                event: SSEEvent = await queue.get()
                if event is None:
                    break
                yield {"data": event.model_dump_json()}
                if event.type in ("done", "error"):
                    break
        except asyncio.CancelledError:
            # 客户端断开
            pass

    return EventSourceResponse(event_gen())


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    """取消运行(Phase 1 仅标记状态并关闭流;真正中止后台任务在 Phase 4)。"""
    await _assert_run_owned(s, run_id, current)
    run = await run_repo.get_run(s, run_id)
    if run.status in ("completed", "error", "cancelled"):
        return {"ok": True, "status": run.status}
    await run_repo.update_run(s, run_id, status="cancelled")
    # 通知 SSE 客户端关闭
    await run_manager.emit(
        run_id, SSEEvent(type="done", data={"cancelled": True})
    )
    return {"ok": True, "status": "cancelled"}
