"""作品(项目)与多版本 schema(Phase 2)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.message import ScriptArtifact


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(BaseModel):
    """作品详情:作品本身 + 全部版本 + 当前激活版本。"""

    project: Optional[ProjectOut] = None
    versions: list[ScriptArtifact] = []
    active: Optional[ScriptArtifact] = None
