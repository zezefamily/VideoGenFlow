"""分镜图片 schema(Phase 4)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StoryboardImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    storyboard_version_id: str
    shot_index: int
    status: str
    method: Optional[str] = None
    prompt: str = ""
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImageListOut(BaseModel):
    images: list[StoryboardImageOut]
    has_active: bool  # 是否有 pending/generating(前端据此决定是否轮询)
