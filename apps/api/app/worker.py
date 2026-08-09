"""Arq worker 配置(Phase 5 后台任务生产路径)。

仅当 TASK_RUNNER=arq + REDIS_URL 配置时使用。独立进程运行:

    cd apps/api && arq app.worker.WorkerSettings

与进程内模式共用同一任务函数 image_service.run_generation_task。
"""

from arq import func
from arq.connections import RedisSettings

from app.config import settings
from app.services.image_service import run_generation_task
from app.services.video_analysis_service import run_analysis_task
from app.services.tts_service import run_tts_task
from app.services.video_render_service import run_render_task
from app.services.shot_video_service import run_generation as run_shot_video_generation


class WorkerSettings:
    functions = [
        func(run_generation_task, name="image_generation"),
        func(run_analysis_task, name="video_analysis"),
        func(run_tts_task, name="tts_generation"),
        func(run_render_task, name="video_render"),
        func(run_shot_video_generation, name="shot_video_generation"),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
