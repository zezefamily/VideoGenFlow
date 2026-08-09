from typing import Literal
from pydantic import BaseModel


class ShotVideoPlanIn(BaseModel):
    strategy: Literal["smart", "all", "custom"] = "smart"
    shot_indices: list[int] = []


class ShotVideoGenerateIn(ShotVideoPlanIn):
    confirmed: bool = False


class ShotVideoAssetOut(BaseModel):
    id: str
    storyboard_version_id: str
    storyboard_image_id: str
    shot_index: int
    status: str
    strategy: str
    video_prompt: str
    model: str
    resolution: str
    duration_sec: int
    estimated_cost: float
    task_id: str | None = None
    video_url: str | None = None
    local_path: str | None = None
    error: str | None = None


class ShotVideoListOut(BaseModel):
    strategy: str | None = None
    selected_shots: list[int] = []
    estimated_cost: float = 0
    assets: list[ShotVideoAssetOut] = []
    has_active: bool = False
