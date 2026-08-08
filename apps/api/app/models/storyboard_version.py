"""分镜版本模型(Phase 3)。

分镜与脚本一样支持多版本,挂在 Project 下;记录基于哪版脚本生成,
以及画面比例/风格配置。shots_json 存分镜列表(供出图与回退)。
"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class StoryboardVersion(Base, TimestampMixin):
    __tablename__ = "storyboard_versions"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 基于哪版脚本生成(可空,兼容无脚本直接生成分镜)
    script_version_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("script_versions.id", ondelete="SET NULL"), nullable=True
    )
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    style: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    shots_json: Mapped[str] = mapped_column(Text, default="[]")
    shot_count: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
