"""会话模型。每个会话对应一个 LangGraph thread_id。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    title: Mapped[str] = mapped_column(String(200), default="新会话")
    # LangGraph Checkpoint 按 thread_id 隔离会话状态
    thread_id: Mapped[str] = mapped_column(ID_STR, default=gen_id, index=True)
    # 归属用户(Phase 5 多租户);历史数据迁移到默认用户
    owner_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True, index=True)
    # 软删除
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 当前激活的项目(Phase 2 作品化)
    active_project_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True)
