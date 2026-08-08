"""消息模型。message_type 区分纯文本与结构化卡片。"""

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    # text | script_card | tool_status | error(方案第七节)
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    # 关联的 artifact(script_versions.id 等),无则为空
    artifact_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True)
    # complete | streaming | error
    status: Mapped[str] = mapped_column(String(16), default="complete")
    # 附加结构化信息(JSON 字符串)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
