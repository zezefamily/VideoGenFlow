"""运行模型:记录一次 Agent 执行。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ID_STR, gen_id


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # running | completed | error | cancelled
    status: Mapped[str] = mapped_column(String(16), default="running")
    current_node: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    input_message_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
