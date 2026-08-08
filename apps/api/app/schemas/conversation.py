"""会话相关 schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    thread_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None


class ConversationSummary(BaseModel):
    """会话列表项(含最后一条消息预览)。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None
