"""SQLAlchemy 2.0 声明式基类与公共 mixin。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


class TimestampMixin:
    """created_at / updated_at 自动维护。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


def gen_id() -> str:
    """生成字符串 UUID 作为主键。"""
    return str(uuid.uuid4())


# 统一的 ID 列类型,便于复用
ID_STR = String(36)
