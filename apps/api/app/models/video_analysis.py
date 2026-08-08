"""视频分析模型(抖音链接解析 / 做同款)。

记录一次"分析爆款链接"的完整产物:
- 下载 + ASR 提取出的口播文案(transcript)与视频元信息(video_info)
- LLM 对爆款内容/话题/结构 的结构化分析(analysis)
- 据此仿写出的原创脚本(挂在 script_version_id,作为作品激活脚本)

status 跟踪后台分析进度,与分镜图片同样的后台任务模式。
"""

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ID_STR, gen_id


class VideoAnalysis(Base, TimestampMixin):
    __tablename__ = "video_analyses"

    id: Mapped[str] = mapped_column(ID_STR, primary_key=True, default=gen_id)
    conversation_id: Mapped[str] = mapped_column(
        ID_STR, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_id: Mapped[Optional[str]] = mapped_column(ID_STR, nullable=True, index=True)

    share_link: Mapped[str] = mapped_column(Text, default="")

    # pending | analyzing | done | error
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # subtitle | asr | failed(文案提取方式)
    method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    video_info_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 仿写脚本:落到 ScriptVersion,这里仅引用(可空,提取失败则无)
    script_version_id: Mapped[Optional[str]] = mapped_column(
        ID_STR, ForeignKey("script_versions.id", ondelete="SET NULL"), nullable=True
    )

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
