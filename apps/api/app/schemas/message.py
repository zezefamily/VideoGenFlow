"""消息与脚本卡片 schema(方案第七节:消息 + Artifact 卡片)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.storyboard import StoryboardArtifact


class ScriptArtifact(BaseModel):
    """脚本卡片 artifact。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    is_active: bool = True
    title: str
    keywords: list[str] = []
    duration_sec: int = 0
    content: str
    golden_sentence: Optional[str] = None
    psychology_theory: Optional[str] = None
    interaction_guide: Optional[str] = None
    # 前端可执行动作(Phase 1 仅展示,Phase 2 接局部修改)
    actions: list[str] = ["edit", "regenerate", "generate_storyboard"]


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    message_type: str
    artifact_id: Optional[str] = None
    status: str
    metadata_json: Optional[str] = None
    created_at: datetime
    # message_type=script_card 时展开
    artifact: Optional[ScriptArtifact] = None
    # message_type=storyboard_card 时展开(Phase 3)
    storyboard: Optional[StoryboardArtifact] = None


class MessageCreate(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    """发送消息后立即返回,真正的回复走 SSE 流。"""

    run_id: str
    message_id: str
