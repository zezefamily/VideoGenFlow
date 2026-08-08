"""分镜版本仓库:多版本管理,与 script_repo 同构(Phase 3)。"""

import json
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryboardVersion


async def _next_version(s: AsyncSession, project_id: str) -> int:
    cnt = await s.scalar(
        select(func.count()).where(StoryboardVersion.project_id == project_id)
    )
    return (cnt or 0) + 1


async def create_storyboard_version(
    s: AsyncSession,
    conversation_id: str,
    project_id: str,
    data: dict,
) -> StoryboardVersion:
    """data 字段:script_version_id, aspect_ratio, style, shots(list)。
    shots 元素:{index,title,visual,narration,duration_sec,camera,notes}
    """
    await s.execute(
        update(StoryboardVersion)
        .where(
            StoryboardVersion.project_id == project_id,
            StoryboardVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )
    shots = data.get("shots", []) or []
    total = sum(int(sh.get("duration_sec", 0) or 0) for sh in shots)
    sv = StoryboardVersion(
        conversation_id=conversation_id,
        project_id=project_id,
        version=await _next_version(s, project_id),
        is_active=True,
        script_version_id=data.get("script_version_id"),
        aspect_ratio=data.get("aspect_ratio", "16:9"),
        style=data.get("style"),
        shots_json=json.dumps(shots, ensure_ascii=False),
        shot_count=len(shots),
        total_duration_sec=total,
    )
    s.add(sv)
    await s.commit()
    await s.refresh(sv)
    return sv


async def get_storyboard(
    s: AsyncSession, storyboard_id: str
) -> Optional[StoryboardVersion]:
    return await s.get(StoryboardVersion, storyboard_id)


async def get_active_storyboard(
    s: AsyncSession, project_id: str
) -> Optional[StoryboardVersion]:
    q = (
        select(StoryboardVersion)
        .where(
            StoryboardVersion.project_id == project_id,
            StoryboardVersion.is_active.is_(True),
        )
        .order_by(StoryboardVersion.version.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def list_storyboard_versions(
    s: AsyncSession, project_id: str
) -> list[StoryboardVersion]:
    q = (
        select(StoryboardVersion)
        .where(StoryboardVersion.project_id == project_id)
        .order_by(StoryboardVersion.version.asc())
    )
    return list((await s.execute(q)).scalars().all())


async def activate_version(
    s: AsyncSession, storyboard_id: str
) -> Optional[StoryboardVersion]:
    """激活指定分镜版本(回退/确认):同项目其余版本置为非活跃。"""
    sv = await s.get(StoryboardVersion, storyboard_id)
    if sv is None or not sv.project_id:
        return None
    await s.execute(
        update(StoryboardVersion)
        .where(
            StoryboardVersion.project_id == sv.project_id,
            StoryboardVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )
    sv.is_active = True
    await s.commit()
    await s.refresh(sv)
    return sv


def to_artifact_dict(sv: StoryboardVersion) -> dict:
    """把 StoryboardVersion 转成前端 artifact 结构。"""
    try:
        shots = json.loads(sv.shots_json) if sv.shots_json else []
    except (json.JSONDecodeError, TypeError):
        shots = []
    return {
        "id": sv.id,
        "version": sv.version,
        "is_active": sv.is_active,
        "script_version_id": sv.script_version_id,
        "aspect_ratio": sv.aspect_ratio,
        "style": sv.style,
        "shots": shots,
        "shot_count": sv.shot_count,
        "total_duration_sec": sv.total_duration_sec,
    }
