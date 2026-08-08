"""数据库引擎、会话工厂与建表。"""

from sqlalchemy import inspect, text, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models import Base  # noqa: F401  触发模型注册

engine = create_async_engine(settings.db_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# SQLite 默认不强制外键级联,这里开启(ondelete=CASCADE 才生效)。
# Postgres 原生强制,无需 pragma。
if settings.db_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def _ensure_columns(conn) -> None:
    """为已有表追加新列(create_all 只建表不加列)。

    与旧 storage.py 的做法一致:逐列 try/except,兼容老库。
    """
    insp = inspect(conn)

    def add_if_missing(table: str, col: str, ddl: str) -> None:
        existing = {c["name"] for c in insp.get_columns(table)}
        if col not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))

    # Phase 2 新增列
    add_if_missing("conversations", "active_project_id", "VARCHAR(36)")
    add_if_missing("script_versions", "project_id", "VARCHAR(36)")
    # Phase 5 多租户
    add_if_missing("conversations", "owner_id", "VARCHAR(36)")
    add_if_missing("audio_tracks", "provider", "VARCHAR(32) DEFAULT 'dubbingx'")


async def _seed_default_user() -> str:
    """首次启动创建开发默认用户,并把历史(无 owner)会话归给它。

    返回默认用户 id。便于本地"登录即用"。
    """
    from app.services import auth as auth_service

    async with AsyncSessionLocal() as s:
        user = await auth_service.get_user_by_email(s, settings.dev_user_email)
        if user is None:
            user = await auth_service.create_user(
                s, settings.dev_user_email, settings.dev_user_password, name="开发用户"
            )
        # 历史 owner_id 为空的会话归该用户
        await s.execute(
            text(
                "UPDATE conversations SET owner_id = :uid "
                "WHERE owner_id IS NULL OR owner_id = ''"
            ),
            {"uid": user.id},
        )
        await s.commit()
        return user.id


async def init_db() -> None:
    """开发期自动建表 + 追加新列(Phase 5 换 Alembic 迁移)。"""
    from app.repositories import audio_track_repo, image_repo, video_analysis_repo, video_render_repo

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_columns)
    # 启动清理:把上次中断的图片/视频分析/音轨/成片任务标为 error(进程已重启)
    async with AsyncSessionLocal() as s:
        await image_repo.mark_generating_stale(s)
        await video_analysis_repo.mark_analyzing_stale(s)
        await audio_track_repo.mark_generating_stale(s)
        await video_render_repo.mark_generating_stale(s)
    # Phase 5:确保默认用户存在,历史会话归它
    await _seed_default_user()


async def get_session():
    """FastAPI 依赖:提供一个异步会话。"""
    async with AsyncSessionLocal() as session:
        yield session
