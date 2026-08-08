"""音频音轨 + 字幕 schema(成片管线:配音 + 字幕打轴)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---- 字幕 ----

class SubtitleWordOut(BaseModel):
    text: str
    start_ms: int
    end_ms: int


class SubtitleSegmentOut(BaseModel):
    order: Optional[int] = None
    text: str
    start_ms: int
    end_ms: int
    words: list[SubtitleWordOut] = []


# ---- 音轨 ----

class TTSGenerateRequest(BaseModel):
    provider: Optional[str] = None
    voice_id: Optional[str] = None
    emotion: Optional[str] = None
    language: Optional[str] = None
    audio_speed: Optional[float] = None
    audio_pitch: Optional[float] = None
    audio_volume: Optional[float] = None
    file_format: Optional[str] = None


class AudioTrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    project_id: Optional[str] = None
    script_version_id: Optional[str] = None
    status: str
    stage: Optional[str] = None
    provider: str = "dubbingx"
    voice_id: str = ""
    emotion: Optional[str] = None
    language: str = "zh"
    audio_speed: float = 1.0
    audio_pitch: float = 1.0
    audio_volume: float = 0.0
    file_format: str = "mp3"
    script_text: str = ""
    tts_task_id: Optional[str] = None
    ata_task_id: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_sec: Optional[float] = None
    subtitles: list[SubtitleSegmentOut] = []
    error: Optional[str] = None
    has_active: bool = False  # 是否有 pending/generating(前端据此决定是否轮询)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---- 音色 / 情绪(前端选择用)----

class VoiceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    grade: Optional[str] = None
    gender: Optional[int] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    voice_url: Optional[str] = Field(None, alias="voiceUrl")
    version: Optional[str] = None
    is_official: Optional[bool] = Field(None, alias="isOfficial")


class VoiceListOut(BaseModel):
    total: int
    list: list[VoiceOut]


class EmotionOut(BaseModel):
    type: str
    auras: list[str] = []


class EmotionListOut(BaseModel):
    list: list[EmotionOut]


# ---- 调试台(临时,不落库)----

class DebugTTSRequest(BaseModel):
    text: str
    voice_id: str
    emotion: Optional[str] = None  # 完整 "类型-风格-档位";空=DubbingX 自动识别
    language: str = "zh"
    audio_speed: float = 1.0
    audio_pitch: float = 1.0
    audio_volume: float = 0.0
    file_format: str = "mp3"
    auto_pause: bool = False  # 提交前调 /v2/autoPause 插停顿
    align: bool = False  # 是否跑 ATA 字幕打轴


class DebugTTSResponse(BaseModel):
    audio_url: str
    duration: Optional[float] = None
    subtitles: list[SubtitleSegmentOut] = []
    emotion_used: Optional[str] = None
    text_used: str
    task_id: str
