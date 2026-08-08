"""分镜图片仓库(Phase 4)。"""

from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryboardImage


async def create_image(s: AsyncSession, **fields) -> StoryboardImage:
    img = StoryboardImage(**fields)
    s.add(img)
    await s.commit()
    await s.refresh(img)
    return img


async def get_image(s: AsyncSession, image_id: str) -> Optional[StoryboardImage]:
    return await s.get(StoryboardImage, image_id)


async def list_images_by_storyboard(
    s: AsyncSession,
    storyboard_version_id: str,
    *,
    statuses: Optional[list[str]] = None,
) -> list[StoryboardImage]:
    q = select(StoryboardImage).where(
        StoryboardImage.storyboard_version_id == storyboard_version_id
    )
    if statuses:
        q = q.where(StoryboardImage.status.in_(statuses))
    q = q.order_by(StoryboardImage.shot_index.asc())
    return list((await s.execute(q)).scalars().all())


async def list_images_by_conversation(
    s: AsyncSession, conversation_id: str
) -> list[StoryboardImage]:
    """取会话当前激活分镜的图片(按 shot_index 升序),排除已取消的旧记录。"""
    q = (
        select(StoryboardImage)
        .where(
            StoryboardImage.conversation_id == conversation_id,
            StoryboardImage.status != "cancelled",
        )
        .order_by(
            StoryboardImage.storyboard_version_id.desc(),
            StoryboardImage.shot_index.asc(),
        )
    )
    return list((await s.execute(q)).scalars().all())


async def update_image(
    s: AsyncSession, image_id: str, **fields
) -> Optional[StoryboardImage]:
    img = await s.get(StoryboardImage, image_id)
    if img is None:
        return None
    for k, v in fields.items():
        setattr(img, k, v)
    await s.commit()
    await s.refresh(img)
    return img


async def delete_images_by_storyboard(
    s: AsyncSession, storyboard_version_id: str
) -> None:
    """物理删除该分镜版本的全部图片记录(整批重新生成前清理,避免累积)。"""
    await s.execute(
        delete(StoryboardImage).where(
            StoryboardImage.storyboard_version_id == storyboard_version_id
        )
    )
    await s.commit()


async def mark_generating_stale(s: AsyncSession) -> int:
    """启动清理:把上次中断的 generating/pending 标为 error(进程已重启)。"""
    result = await s.execute(
        update(StoryboardImage)
        .where(StoryboardImage.status.in_(["generating", "pending"]))
        .values(status="error", error="生成被中断(服务重启)")
    )
    await s.commit()
    return result.rowcount or 0


def to_artifact_dict(img: StoryboardImage) -> dict:
    return {
        "id": img.id,
        "storyboard_version_id": img.storyboard_version_id,
        "shot_index": img.shot_index,
        "status": img.status,
        "method": img.method,
        "prompt": img.prompt,
        "image_url": img.image_url,
        "local_path": img.local_path,
        "error": img.error,
        "created_at": img.created_at.isoformat() if img.created_at else None,
        "updated_at": img.updated_at.isoformat() if img.updated_at else None,
    }
