"""视频成片模型(成片管线:静态分镜 + 音频 + 字幕 -> mp4)。

每个作品一条当前成片:旁白对齐(分镜 narration ↔ ATA 字幕)-> ffmpeg 合成 ->
本地 mp4(/api/video)。status 跟踪整条流水线;stage 标当前阶段(align/ffmpeg)。
"""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class VideoRender(Base, TimestampMixin):
    __tablename__ = "video_renders"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    audio_track_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("audio_tracks.id", ondelete="SET NULL"), nullable=True
    )
    storyboard_version_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("storyboard_versions.id", ondelete="SET NULL"), nullable=True
    )

    # pending | generating | done | error | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # align | ffmpeg(当前流水线阶段,供前端细粒度展示)
    stage: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    render_mode: Mapped[str] = mapped_column(String(16), default="image")  # image | video

    # 本地静态路径 /api/video/{id}.mp4
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
