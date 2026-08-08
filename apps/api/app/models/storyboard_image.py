"""分镜图片模型(Phase 4)。

每个分镜版本下,每个镜头对应一张图(可重绘,就地更新)。
status 跟踪后台生成进度;local_path 供本地静态服务(ARK URL 会过期)。
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class StoryboardImage(Base, TimestampMixin):
    __tablename__ = "storyboard_images"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    storyboard_version_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("storyboard_versions.id", ondelete="CASCADE"), index=True
    )
    shot_index: Mapped[int] = mapped_column(Integer, index=True)

    # pending | generating | done | error | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # text2image | img2image
    prompt: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ARK 远端 URL(可能过期)
    local_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # web 相对路径,如 /api/img/{sb_id}/shot_1.png
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
