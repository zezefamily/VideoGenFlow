"""视频成片 schema(成片管线:静态分镜 + 音频 + 字幕 -> mp4)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VideoRenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    project_id: Optional[str] = None
    audio_track_id: Optional[str] = None
    storyboard_version_id: Optional[str] = None
    status: str
    stage: Optional[str] = None
    aspect_ratio: str = "16:9"
    video_url: Optional[str] = None
    duration_sec: Optional[float] = None
    error: Optional[str] = None
    has_active: bool = False  # 是否有 pending/generating(前端据此决定是否轮询)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
