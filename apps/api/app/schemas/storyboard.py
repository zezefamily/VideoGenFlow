"""分镜 artifact schema(Phase 3)。"""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class StoryboardShot(BaseModel):
    index: int
    title: str = ""
    visual: str = ""
    video_prompt: str = ""
    narration: str = ""
    duration_sec: int = 0
    camera: str = ""
    notes: str = ""


class StoryboardArtifact(BaseModel):
    """分镜卡片 artifact。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    is_active: bool = True
    script_version_id: Optional[str] = None
    aspect_ratio: str = "16:9"
    style: Optional[str] = None
    shots: list[StoryboardShot] = []
    shot_count: int = 0
    total_duration_sec: int = 0
    actions: list[str] = ["edit", "regenerate", "generate_images"]


class StoryboardDetail(BaseModel):
    """分镜详情:全部版本 + 当前激活版本(Phase 3)。"""

    versions: list[StoryboardArtifact] = []
    active: Optional[StoryboardArtifact] = None


class StyleOut(BaseModel):
    """画风选项(供前端生图选择)。"""

    name: str
    description: str
