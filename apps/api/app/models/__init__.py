"""ORM 模型聚合导入,确保 Base.metadata 能发现所有表。"""

from app.models.base import Base, TimestampMixin, gen_id
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.project import Project
from app.models.run import Run
from app.models.script_version import ScriptVersion
from app.models.storyboard_version import StoryboardVersion
from app.models.storyboard_image import StoryboardImage
from app.models.video_analysis import VideoAnalysis
from app.models.audio_track import AudioTrack
from app.models.video_render import VideoRender
from app.models.generation_log import GenerationLog

__all__ = [
    "Base",
    "TimestampMixin",
    "gen_id",
    "User",
    "Conversation",
    "Message",
    "Project",
    "Run",
    "ScriptVersion",
    "StoryboardVersion",
    "StoryboardImage",
    "VideoAnalysis",
    "AudioTrack",
    "VideoRender",
    "GenerationLog",
]
