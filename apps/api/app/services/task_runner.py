"""后台任务运行器抽象(Phase 5):进程内 asyncio / Redis+Arq 双模式。

- inprocess(默认):asyncio.create_task,同进程跑(Phase 1-4 已验证的方式)。
- arq:置 TASK_RUNNER=arq + REDIS_URL,提交到 Redis,由独立 arq worker 进程执行
  (服务重启后任务仍可继续)。需另起 `arq app.worker.WorkerSettings`。

任务以 (name, **kwargs) 提交;实际任务函数在 registry 注册,两边共用同一函数。
"""

import asyncio
from typing import Awaitable, Callable

from app.config import settings

# 任务名 -> 协程函数 的注册表
_tasks: dict[str, Callable[..., Awaitable]] = {}


def register_task(name: str, fn: Callable[..., Awaitable]) -> None:
    _tasks[name] = fn


class TaskRunner:
    async def submit(self, name: str, **kwargs) -> None:
        raise NotImplementedError


# 进程内任务引用,防 GC
_bg_tasks: set = set()


class InProcessRunner(TaskRunner):
    async def submit(self, name: str, **kwargs) -> None:
        fn = _tasks.get(name)
        if fn is None:
            raise RuntimeError(f"未注册的任务: {name}")
        task = asyncio.create_task(fn(**kwargs))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)


class ArqRunner(TaskRunner):
    """Redis + Arq。arq 懒加载:开发默认 inprocess 时无需安装 arq。"""

    def __init__(self) -> None:
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            from arq import create_pool  # 懒加载
            from arq.connections import RedisSettings

            self._pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        return self._pool

    async def submit(self, name: str, **kwargs) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job(name, **kwargs)


_runner: TaskRunner | None = None


def get_runner() -> TaskRunner:
    global _runner
    if _runner is None:
        if settings.task_runner == "arq" and settings.redis_url:
            _runner = ArqRunner()
        else:
            _runner = InProcessRunner()
    return _runner


async def submit(name: str, **kwargs) -> None:
    await get_runner().submit(name, **kwargs)
