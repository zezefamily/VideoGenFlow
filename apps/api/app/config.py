"""应用配置:从环境变量读取所有配置(Phase 5 扩展为可切换双模式)。

双模式原则(方案第60/263行):
- 数据库:开发 SQLite,生产 PostgreSQL(置 DATABASE_URL 即切)
- 对象存储:开发本地盘,生产 S3 兼容(置 S3_* 即切)
- 后台任务:开发进程内 asyncio,生产 Redis+Arq(置 REDIS_URL 即切)
开发默认保持 Phase 1-4 已验证的流程不破。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录 .env
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")

DATA_DIR = _PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Settings:
    """全局配置。Phase 5 起支持生产基建切换。"""

    # ---- DeepSeek(OpenAI 兼容)----
    deepseek_api_key: str = _get("DEEPSEEK_API_KEY", "")
    deepseek_model: str = _get("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_base_url: str = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ---- 火山引擎 ARK(图片生成)----
    ark_api_key: str = _get("ARK_API_KEY", "")
    ark_image_model: str = _get("ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    ark_video_model: str = _get("ARK_VIDEO_MODEL", "doubao-seedance-2-0-mini-260615")
    ark_video_resolution: str = _get("ARK_VIDEO_RESOLUTION", "480p")
    # Seedance 按生成视频时长计费；仅用于提交前预算展示，不参与方舟实际扣费。
    ark_video_cost_per_second: float = float(_get("ARK_VIDEO_COST_PER_SECOND", "0.25"))
    ark_base_url: str = _get(
        "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
    )

    # ---- DubbingX TTS(成片管线:配音)----
    # 异步 TTS:整段脚本一次性合成一条音频。
    dubbingx_api_key: str = _get("DUBBINGX_API_KEY", "")
    dubbingx_base_url: str = _get("DUBBINGX_BASE_URL", "https://tts-api.dubbingx.com")
    dubbingx_default_voice_id: str = _get("DUBBINGX_DEFAULT_VOICE_ID", "")
    # 全情绪音色可留空(自动识别);单情绪可不传
    dubbingx_default_emotion: str = _get("DUBBINGX_DEFAULT_EMOTION", "")
    dubbingx_default_language: str = _get("DUBBINGX_DEFAULT_LANGUAGE", "zh")
    dubbingx_default_speed: float = float(_get("DUBBINGX_DEFAULT_SPEED", "1.0"))
    dubbingx_default_pitch: float = float(_get("DUBBINGX_DEFAULT_PITCH", "1.0"))
    dubbingx_default_volume: float = float(_get("DUBBINGX_DEFAULT_VOLUME", "0"))  # dB,-12~+12
    dubbingx_default_format: str = _get("DUBBINGX_DEFAULT_FORMAT", "mp3")

    # ---- 豆包 / 火山引擎语音合成 HTTP API ----
    tts_provider: str = _get("TTS_PROVIDER", "dubbingx")  # dubbingx | volcengine
    volc_tts_appid: str = _get("VOLC_TTS_APPID", "")
    volc_tts_access_token: str = _get("VOLC_TTS_ACCESS_TOKEN", "")
    volc_tts_cluster: str = _get("VOLC_TTS_CLUSTER", "volcano_tts")
    volc_tts_voice_type: str = _get("VOLC_TTS_VOICE_TYPE", "zh_female_shuangkuaisisi_emo_v2_mars_bigtts")
    volc_tts_api_url: str = _get("VOLC_TTS_API_URL", "https://openspeech.bytedance.com/api/v1/tts")

    # ---- 火山引擎 ATA 字幕打轴(成片管线:字幕时间轴)----
    # 文本对齐:传音频URL+脚本文本,返回该文本逐句/逐词时间戳。
    volc_ata_appid: str = _get("VOLC_ATA_APPID", "")
    volc_ata_token: str = _get("VOLC_ATA_TOKEN", "")
    volc_ata_base_url: str = _get("VOLC_ATA_BASE_URL", "https://openspeech.bytedance.com")

    # ---- 火山引擎 TOS 对象存储(存 TTS 音频供 ATA 拉取 + 前端播放)----
    # S3 兼容;DubbingX 签名 URL 会过期,故音频落地 TOS 取持久公网 URL。
    # 音频存储独立于图片存储(STORAGE_BACKEND),TTS 专用。
    tos_access_key: str = _get("TOS_ACCESS_KEY", "")
    tos_secret_key: str = _get("TOS_SECRET_KEY", "")
    tos_bucket: str = _get("TOS_BUCKET", "")
    tos_endpoint: str = _get("TOS_ENDPOINT", "")  # 如 tos-s3-cn-beijing.volces.com
    tos_region: str = _get("TOS_REGION", "cn-beijing")
    tos_public_base: str = _get("TOS_PUBLIC_BASE", "")  # 如 https://bucket.tos-cn-beijing.volces.com

    # ---- 数据库(双模式)----
    # 置 DATABASE_URL 即切到生产库;支持 postgresql+asyncpg:// 或 sqlite+aiosqlite:///
    database_url: str = _get("DATABASE_URL", "")
    # 业务库 SQLAlchemy URL
    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{DATA_DIR / 'app.sqlite'}"

    @property
    def is_postgres(self) -> bool:
        return self.db_url.startswith("postgresql")

    # LangGraph Checkpoint:Postgres 用 psycopg(plain postgresql://),SQLite 用文件路径
    checkpoint_path: Path = DATA_DIR / "checkpoints.sqlite"

    @property
    def checkpoint_pg_url(self) -> str:
        """LangGraph AsyncPostgresSaver 用的 psycopg 连接串。"""
        # postgresql+asyncpg://... -> postgresql://...
        return self.db_url.replace("postgresql+asyncpg://", "postgresql://")

    # ---- 对象存储(双模式)----
    storage_backend: str = _get("STORAGE_BACKEND", "local")  # local | s3
    images_dir: Path = DATA_DIR / "images"
    audio_dir: Path = DATA_DIR / "audio"
    video_dir: Path = DATA_DIR / "videos"
    shot_video_dir: Path = DATA_DIR / "shot_videos"
    # 本地背景音乐库:合成时自动选择按文件名排序后的第一首，未放音乐则仅保留口播。
    bg_music_dir: Path = _PROJECT_ROOT / "bg_music"
    s3_endpoint: str = _get("S3_ENDPOINT", "")
    s3_bucket: str = _get("S3_BUCKET", "")
    s3_access_key: str = _get("S3_ACCESS_KEY", "")
    s3_secret_key: str = _get("S3_SECRET_KEY", "")
    s3_region: str = _get("S3_REGION", "")
    # 对象公共访问前缀(本地无;S3 为 https://bucket.endpoint 或 CDN)
    s3_public_base: str = _get("S3_PUBLIC_BASE", "")

    # ---- 后台任务(双模式)----
    task_runner: str = _get("TASK_RUNNER", "inprocess")  # inprocess | arq
    redis_url: str = _get("REDIS_URL", "")

    # ---- 用户认证(JWT)----
    jwt_secret: str = _get("JWT_SECRET", "dev-insecure-secret-change-me")
    jwt_algorithm: str = _get("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(_get("JWT_EXPIRE_MINUTES", "10080"))  # 默认 7 天
    # 开发默认用户(首次启动自动创建,便于本地"登录即用")
    dev_user_email: str = _get("DEV_USER_EMAIL", "dev@videogenflow.local")
    dev_user_password: str = _get("DEV_USER_PASSWORD", "devpassword")

    # ---- 限流 ----
    # 格式 "<n>/<period>",如 "60/minute";留空则不限流
    rate_limit: str = _get("RATE_LIMIT", "60/minute")

    # ---- 监控/错误追踪 ----
    sentry_dsn: str = _get("SENTRY_DSN", "")

    # ---- 媒体分析(抖音链接解析)----
    # 抖音等平台常需 cookie 才能下载;留空则不使用浏览器 cookie。
    # 默认 chrome(与原 viral_agent/media.py 一致);macOS 上通常可用。
    media_cookies_browser: str = _get("MEDIA_COOKIES_BROWSER", "chrome")
    # faster-whisper 模型档位(tiny|base|small|medium|large-v3);首次加载约 488MB(small)
    media_whisper_model: str = _get("MEDIA_WHISPER_MODEL", "small")

    # ---- 前端来源 ----
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]


settings = Settings()
