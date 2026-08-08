"""运行管理器:Phase 1 内存版,按 run_id 维护事件队列。

Phase 4 替换为 Redis + Celery/Arq,以支持服务重启后任务继续。
"""

import asyncio
from typing import Optional

from app.schemas.events import SSEEvent


class RunManager:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def register(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[run_id] = q
        return q

    def get(self, run_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(run_id)

    async def emit(self, run_id: str, event: SSEEvent) -> None:
        q = self._queues.get(run_id)
        if q is not None:
            await q.put(event)

    def unregister(self, run_id: str) -> None:
        self._queues.pop(run_id, None)


run_manager = RunManager()
