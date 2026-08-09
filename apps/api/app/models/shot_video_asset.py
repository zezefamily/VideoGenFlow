"""分镜图生视频资产：每个被选中的镜头对应一段无声视频。"""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class ShotVideoAsset(Base, TimestampMixin):
    __tablename__ = "shot_video_assets"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    storyboard_version_id: Mapped[str] = mapped_column(ID_STR, ForeignKey("storyboard_versions.id", ondelete="CASCADE"), index=True)
    storyboard_image_id: Mapped[str] = mapped_column(ID_STR, ForeignKey("storyboard_images.id", ondelete="CASCADE"), index=True)
    shot_index: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    strategy: Mapped[str] = mapped_column(String(16), default="smart")
    video_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(100))
    resolution: Mapped[str] = mapped_column(String(16), default="480p")
    duration_sec: Mapped[int] = mapped_column(Integer, default=5)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
