"""音频音轨模型(成片管线:配音 + 字幕打轴)。

每个作品一条当前音轨:整段脚本一次性 TTS 合成 -> 上传 TOS ->
火山 ATA 打轴得逐句/逐词时间戳。subtitles_json 存字幕段(与分镜
shots_json 同模式)。status 跟踪整条 tts->ata 流水线;stage 标当前阶段。
"""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class AudioTrack(Base, TimestampMixin):
    __tablename__ = "audio_tracks"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 基于哪版脚本生成(可空兼容)
    script_version_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("script_versions.id", ondelete="SET NULL"), nullable=True
    )

    # pending | generating | done | error | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # tts | ata(当前流水线阶段,供前端细粒度展示)
    stage: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # 配音参数
    provider: Mapped[str] = mapped_column(String(32), default="dubbingx")
    voice_id: Mapped[str] = mapped_column(String(64), default="")
    emotion: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="zh")
    audio_speed: Mapped[float] = mapped_column(Float, default=1.0)
    audio_pitch: Mapped[float] = mapped_column(Float, default=1.0)
    audio_volume: Mapped[float] = mapped_column(Float, default=0.0)  # dB
    file_format: Mapped[str] = mapped_column(String(8), default="mp3")

    # 配音文本快照(= 生成时激活脚本 content)
    script_text: Mapped[str] = mapped_column(Text, default="")

    # DubbingX 任务 id + 火山 ATA 任务 id
    tts_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ata_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # TOS 公网 URL(DubbingX 签名 URL 会过期,故落地 TOS;供 ATA 拉取 + 前端播放)
    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ATA 逐句字幕:[{order,text,start_ms,end_ms,words:[{text,start_ms,end_ms}]}]
    subtitles_json: Mapped[str] = mapped_column(Text, default="[]")

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
