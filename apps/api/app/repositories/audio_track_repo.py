"""音频音轨仓库(成片管线:配音 + 字幕)。"""

import json
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AudioTrack


async def create_track(s: AsyncSession, **fields) -> AudioTrack:
    track = AudioTrack(**fields)
    s.add(track)
    await s.commit()
    await s.refresh(track)
    return track


async def get_track(s: AsyncSession, track_id: str) -> Optional[AudioTrack]:
    return await s.get(AudioTrack, track_id)


async def get_active_track(s: AsyncSession, project_id: str) -> Optional[AudioTrack]:
    """取作品当前音轨(最新一条)。"""
    q = (
        select(AudioTrack)
        .where(AudioTrack.project_id == project_id)
        .order_by(AudioTrack.created_at.desc())
        .limit(1)
    )
    return (await s.execute(q)).scalars().first()


async def list_tracks_by_conversation(
    s: AsyncSession, conversation_id: str
) -> list[AudioTrack]:
    """取会话全部音轨(取消用),排除已取消的旧记录。"""
    q = (
        select(AudioTrack)
        .where(
            AudioTrack.conversation_id == conversation_id,
            AudioTrack.status != "cancelled",
        )
        .order_by(AudioTrack.created_at.desc())
    )
    return list((await s.execute(q)).scalars().all())


async def update_track(
    s: AsyncSession, track_id: str, **fields
) -> Optional[AudioTrack]:
    track = await s.get(AudioTrack, track_id)
    if track is None:
        return None
    for k, v in fields.items():
        setattr(track, k, v)
    await s.commit()
    await s.refresh(track)
    return track


async def delete_tracks_by_project(s: AsyncSession, project_id: str) -> None:
    """物理删除该作品的全部音轨(整轨重新生成前清理,避免累积)。"""
    await s.execute(delete(AudioTrack).where(AudioTrack.project_id == project_id))
    await s.commit()


async def mark_generating_stale(s: AsyncSession) -> int:
    """启动清理:把上次中断的 generating/pending 标为 error(进程已重启)。"""
    result = await s.execute(
        update(AudioTrack)
        .where(AudioTrack.status.in_(["generating", "pending"]))
        .values(status="error", error="生成被中断(服务重启)")
    )
    await s.commit()
    return result.rowcount or 0


def _parse_subtitles(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def to_artifact_dict(track: AudioTrack) -> dict:
    return {
        "id": track.id,
        "conversation_id": track.conversation_id,
        "project_id": track.project_id,
        "script_version_id": track.script_version_id,
        "status": track.status,
        "stage": track.stage,
        "provider": track.provider,
        "voice_id": track.voice_id,
        "emotion": track.emotion,
        "language": track.language,
        "audio_speed": track.audio_speed,
        "audio_pitch": track.audio_pitch,
        "audio_volume": track.audio_volume,
        "file_format": track.file_format,
        "script_text": track.script_text,
        "tts_task_id": track.tts_task_id,
        "ata_task_id": track.ata_task_id,
        "audio_url": track.audio_url,
        "audio_duration_sec": track.audio_duration_sec,
        "subtitles": _parse_subtitles(track.subtitles_json),
        "error": track.error,
        "created_at": track.created_at.isoformat() if track.created_at else None,
        "updated_at": track.updated_at.isoformat() if track.updated_at else None,
    }
