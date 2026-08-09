"""分镜视频资产数据访问。"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShotVideoAsset


async def create(s: AsyncSession, **fields) -> ShotVideoAsset:
    row = ShotVideoAsset(**fields)
    s.add(row); await s.commit(); await s.refresh(row); return row


async def get(s: AsyncSession, asset_id: str):
    return await s.get(ShotVideoAsset, asset_id)


async def list_by_storyboard(s: AsyncSession, storyboard_id: str):
    q = select(ShotVideoAsset).where(ShotVideoAsset.storyboard_version_id == storyboard_id).order_by(ShotVideoAsset.shot_index)
    return list((await s.execute(q)).scalars().all())


async def list_active(s: AsyncSession):
    q = select(ShotVideoAsset).where(ShotVideoAsset.status.in_(["pending", "generating"]))
    return list((await s.execute(q)).scalars().all())


async def clear_unfinished(s: AsyncSession, storyboard_id: str):
    await s.execute(delete(ShotVideoAsset).where(ShotVideoAsset.storyboard_version_id == storyboard_id, ShotVideoAsset.status != "done")); await s.commit()


async def update(s: AsyncSession, asset_id: str, **fields):
    row = await s.get(ShotVideoAsset, asset_id)
    if not row: return None
    for key, value in fields.items(): setattr(row, key, value)
    await s.commit(); await s.refresh(row); return row


def to_dict(row: ShotVideoAsset) -> dict:
    return {key: getattr(row, key) for key in (
        "id", "conversation_id", "project_id", "storyboard_version_id", "storyboard_image_id",
        "shot_index", "status", "strategy", "video_prompt", "model", "resolution",
        "duration_sec", "estimated_cost", "task_id", "video_url", "local_path", "error"
    )} | {"created_at": row.created_at, "updated_at": row.updated_at}
