"""视频成片仓库(成片管线:静态分镜合成)。"""

from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoRender


async def create_render(s: AsyncSession, **fields) -> VideoRender:
    render = VideoRender(**fields)
    s.add(render)
    await s.commit()
    await s.refresh(render)
    return render


async def get_render(s: AsyncSession, render_id: str) -> Optional[VideoRender]:
    return await s.get(VideoRender, render_id)


async def get_active_render(s: AsyncSession, project_id: str) -> Optional[VideoRender]:
    """取作品当前成片(最新一条)。"""
    q = (
        select(VideoRender)
        .where(VideoRender.project_id == project_id)
        .order_by(VideoRender.created_at.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def list_renders_by_conversation(
    s: AsyncSession, conversation_id: str
) -> list[VideoRender]:
    q = (
        select(VideoRender)
        .where(
            VideoRender.conversation_id == conversation_id,
            VideoRender.status != "cancelled",
        )
        .order_by(VideoRender.created_at.desc())
    )
    return list((await s.execute(q)).scalars().all())


async def update_render(
    s: AsyncSession, render_id: str, **fields
) -> Optional[VideoRender]:
    render = await s.get(VideoRender, render_id)
    if render is None:
        return None
    for k, v in fields.items():
        setattr(render, k, v)
    await s.commit()
    await s.refresh(render)
    return render


async def delete_renders_by_project(s: AsyncSession, project_id: str) -> None:
    """物理删除该作品的全部成片(重新生成前清理,避免累积)。"""
    await s.execute(delete(VideoRender).where(VideoRender.project_id == project_id))
    await s.commit()


async def mark_generating_stale(s: AsyncSession) -> int:
    """启动清理:把上次中断的 generating/pending 标为 error(进程已重启)。"""
    result = await s.execute(
        update(VideoRender)
        .where(VideoRender.status.in_(["generating", "pending"]))
        .values(status="error", error="合成被中断(服务重启)")
    )
    await s.commit()
    return result.rowcount or 0


def to_artifact_dict(render: VideoRender) -> dict:
    return {
        "id": render.id,
        "conversation_id": render.conversation_id,
        "project_id": render.project_id,
        "audio_track_id": render.audio_track_id,
        "storyboard_version_id": render.storyboard_version_id,
        "status": render.status,
        "stage": render.stage,
        "aspect_ratio": render.aspect_ratio,
        "video_url": render.video_url,
        "duration_sec": render.duration_sec,
        "error": render.error,
        "created_at": render.created_at.isoformat() if render.created_at else None,
        "updated_at": render.updated_at.isoformat() if render.updated_at else None,
    }
