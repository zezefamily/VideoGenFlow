"""脚本版本模型。脚本必须支持多版本,而非直接覆盖(方案第三节)。"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class ScriptVersion(Base, TimestampMixin):
    __tablename__ = "script_versions"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    # Phase 1 挂在会话上;Phase 2 改挂项目(保留 conversation_id 兼容旧数据)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    keywords_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    golden_sentence: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    psychology_theory: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    interaction_guide: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
