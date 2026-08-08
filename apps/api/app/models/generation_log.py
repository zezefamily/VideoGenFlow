"""生成日志模型(Phase 5:Prompt/模型版本记录)。

每次脚本/分镜/图片生成调用都落一条,记录用的提示词模板名+版本、模型、参数、
耗时与产出 artifact,用于用量统计与可追溯。
"""

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class GenerationLog(Base, TimestampMixin):
    __tablename__ = "generation_logs"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    # 归属(可空:系统/迁移产生的调用)
    owner_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True, index=True)
    # script | storyboard | image | classify
    kind: Mapped[str] = mapped_column(String(32), index=True)
    # 提示词模板名 + 版本(见 prompts.PROMPT_REGISTRY)
    prompt_template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_template_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # 实际模型名
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 调用参数 JSON(temperature/size 等)
    params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 产出
    artifact_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | error
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # token 用量(图片生成时为空)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
