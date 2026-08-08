"""视频分析 schema(抖音链接解析 / 做同款)。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class VideoAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    project_id: Optional[str] = None
    share_link: str = ""
    status: str
    method: Optional[str] = None
    video_info: Optional[dict[str, Any]] = None
    transcript: Optional[str] = None
    analysis: Optional[dict[str, Any]] = None
    script_version_id: Optional[str] = None
    script: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VideoAnalysisLatestOut(BaseModel):
    """会话最近一次分析(前端轮询用)。"""

    analysis: Optional[VideoAnalysisOut] = None
    has_active: bool  # 是否有 pending/analyzing(前端据此决定是否轮询)
