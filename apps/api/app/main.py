"""FastAPI 应用入口。

启动:
    cd apps/api && uvicorn app.main:app --reload --port 8000

Phase 5:支持 PostgreSQL 检查点(置 DATABASE_URL)、Sentry、限流、结构化日志。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.graph.builder import build_graph
from app.middleware import RateLimitMiddleware, RequestLogMiddleware
from app.api import auth as auth_router
from app.api import conversations as conversations_router
from app.api import messages as messages_router
from app.api import runs as runs_router
from app.api import projects as projects_router
from app.api import artifacts as artifacts_router
from app.api import storyboards as storyboards_router
from app.api import images as images_router
from app.api import usage as usage_router
from app.api import video_analysis as video_analysis_router
from app.api import styles as styles_router
from app.api import tts as tts_router
from app.api import video as video_router
from app.api import shot_videos as shot_videos_router
from app.services import shot_video_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表,并构建带 Checkpointer 的 LangGraph。"""
    await init_db()

    # Sentry(可选;未配 DSN 时为 no-op)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
        )

    # 恢复因开发热重载或服务重启而中断的 Seedance 轮询任务。
    await shot_video_service.resume_active()

    # 检查点 saver:Postgres 或 SQLite(双模式)
    if settings.is_postgres:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            settings.checkpoint_pg_url
        ) as saver:
            await saver.setup()
            app.state.graph = build_graph(saver)
            yield
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(
            str(settings.checkpoint_path)
        ) as saver:
            app.state.graph = build_graph(saver)
            yield


app = FastAPI(title="VideoGenFlow API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "VideoGenFlow API"}


app.include_router(auth_router.router)
app.include_router(conversations_router.router)
app.include_router(messages_router.router)
app.include_router(runs_router.router)
app.include_router(projects_router.router)
app.include_router(artifacts_router.router)
app.include_router(storyboards_router.router)
app.include_router(images_router.router)
app.include_router(images_router.regen_router)
app.include_router(tts_router.router)
app.include_router(tts_router.voices_router)
app.include_router(tts_router.regen_router)
app.include_router(video_router.router)
app.include_router(video_router.regen_router)
app.include_router(shot_videos_router.router)
app.include_router(video_analysis_router.router)
app.include_router(video_analysis_router.detail_router)
app.include_router(usage_router.router)
app.include_router(styles_router.router)

# 静态服务本地图片(Phase 4):/api/img/{storyboard_id}/shot_N.png
# S3 模式下图片走对象存储 URL,此挂载仅服务本地模式。
app.mount("/api/img", StaticFiles(directory=str(settings.images_dir)), name="images")

# 静态服务本地音频(成片管线):/api/audio/{track_id}.mp3
# TTS 音频本地持久化(播放 + 后续合成);TOS 仅作 ATA 打轴临时中转,打轴后即删。
settings.audio_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/audio", StaticFiles(directory=str(settings.audio_dir)), name="audio")

# 静态服务本地成片视频(成片管线):/api/video/{render_id}.mp4
# ffmpeg 合成产物落地本地盘,经此静态服务播放/下载。
settings.video_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/video", StaticFiles(directory=str(settings.video_dir)), name="video")

settings.shot_video_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/shot-video", StaticFiles(directory=str(settings.shot_video_dir)), name="shot-video")
