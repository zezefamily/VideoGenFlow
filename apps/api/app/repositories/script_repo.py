"""脚本版本仓库:多版本管理,新版本激活时旧版本置为非活跃;支持版本回退。"""

import json
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScriptVersion


async def _next_version(s: AsyncSession, project_id: str) -> int:
    cnt = await s.scalar(
        select(func.count()).where(ScriptVersion.project_id == project_id)
    )
    return (cnt or 0) + 1


async def create_script_version(
    s: AsyncSession,
    conversation_id: str,
    project_id: str,
    data: dict,
) -> ScriptVersion:
    """data 字段:title, keywords(list), duration_sec, content, golden_sentence,
    psychology_theory, interaction_guide。"""
    # 同项目旧版本全部置为非活跃
    await s.execute(
        update(ScriptVersion)
        .where(
            ScriptVersion.project_id == project_id,
            ScriptVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )
    sv = ScriptVersion(
        conversation_id=conversation_id,
        project_id=project_id,
        version=await _next_version(s, project_id),
        is_active=True,
        title=data.get("title", ""),
        keywords_json=json.dumps(data.get("keywords", []), ensure_ascii=False),
        duration_sec=data.get("duration_sec", 0),
        content=data.get("content", ""),
        golden_sentence=data.get("golden_sentence"),
        psychology_theory=data.get("psychology_theory"),
        interaction_guide=data.get("interaction_guide"),
    )
    s.add(sv)
    await s.commit()
    await s.refresh(sv)
    return sv


async def get_script(s: AsyncSession, script_id: str) -> Optional[ScriptVersion]:
    return await s.get(ScriptVersion, script_id)


async def get_active_script(
    s: AsyncSession, project_id: str
) -> Optional[ScriptVersion]:
    q = (
        select(ScriptVersion)
        .where(
            ScriptVersion.project_id == project_id,
            ScriptVersion.is_active.is_(True),
        )
        .order_by(ScriptVersion.version.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def list_versions(
    s: AsyncSession, project_id: str
) -> list[ScriptVersion]:
    """按版本号升序返回全部版本。"""
    q = (
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.version.asc())
    )
    return list((await s.execute(q)).scalars().all())


async def activate_version(
    s: AsyncSession, script_id: str
) -> Optional[ScriptVersion]:
    """激活指定版本(回退/确认):同项目其余版本置为非活跃。"""
    sv = await s.get(ScriptVersion, script_id)
    if sv is None or not sv.project_id:
        return None
    await s.execute(
        update(ScriptVersion)
        .where(
            ScriptVersion.project_id == sv.project_id,
            ScriptVersion.is_active.is_(True),
        )
        .values(is_active=False)
    )
    sv.is_active = True
    await s.commit()
    await s.refresh(sv)
    return sv


def to_artifact_dict(sv: ScriptVersion) -> dict:
    """把 ScriptVersion 转成前端 artifact 结构。"""
    try:
        keywords = json.loads(sv.keywords_json) if sv.keywords_json else []
    except (json.JSONDecodeError, TypeError):
        keywords = []
    return {
        "id": sv.id,
        "version": sv.version,
        "is_active": sv.is_active,
        "title": sv.title,
        "keywords": keywords,
        "duration_sec": sv.duration_sec,
        "content": sv.content,
        "golden_sentence": sv.golden_sentence,
        "psychology_theory": sv.psychology_theory,
        "interaction_guide": sv.interaction_guide,
    }
