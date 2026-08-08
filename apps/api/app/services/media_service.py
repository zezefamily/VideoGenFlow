"""视频媒体处理服务(从 viral_agent/media.py 改造)。

抖音等短视频链接的三级文案提取管线:
1. yt-dlp 下载字幕(最快最准)
2. yt-dlp 下载视频 -> ffmpeg 提取音频 -> faster-whisper 语音识别
3. 全部失败:返回 (None, "all methods failed", video_info),交由上层降级

改造点(相对原 viral_agent/media.py):
- yt_dlp / faster_whisper 懒加载(应用启动不依赖,缺失时仅影响本功能)
- whisper 模型档位由配置决定(settings.media_whisper_model)
- 浏览器 cookie 可配(settings.media_cookies_browser,留空则不用)
- cookie 失败兜底:带 cookie 全失败后,无 cookie 再试一遍(抖音常需 cookie,但也常不需要)
- 对外暴露 async extract_script(),内部用 asyncio.to_thread 跑同步管线
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

from app.config import DATA_DIR, settings


# ============================================================
# 工具:ffmpeg 可用性 + yt-dlp opts
# ============================================================

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

_whisper_model = None


def _cookie_opt() -> dict:
    """浏览器 cookie 选项(配置留空则不启用)。"""
    browser = settings.media_cookies_browser.strip()
    if browser:
        return {"cookiesfrombrowser": (browser,)}
    return {}


def _extract_video_info(info: dict) -> dict:
    text_for_tags = " ".join(
        filter(None, [info.get("title", ""), info.get("description", "")])
    )
    topics = re.findall(r"#([^\s#]+)", text_for_tags)
    return {
        "title": info.get("title", ""),
        "author": info.get("uploader", "")
        or info.get("channel", "")
        or info.get("uploader_id", ""),
        "duration": info.get("duration", 0),
        "like_count": info.get("like_count", 0),
        "view_count": info.get("view_count", 0),
        "comment_count": info.get("comment_count", 0),
        "video_url": info.get("url", ""),
        "description": info.get("description", ""),
        "tags": info.get("tags", []) or [],
        "topics": topics,
        "webpage_url": info.get("webpage_url", ""),
        "video_id": info.get("id", ""),
    }


# ============================================================
# Tier 1: 下载字幕
# ============================================================

def _parse_subtitle_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    if path.endswith(".json3"):
        try:
            data = json.loads(content)
            texts = []
            for event in data.get("events", []):
                segs = event.get("segs", [])
                line = "".join(s.get("utf8", "") for s in segs)
                if line.strip():
                    texts.append(line.strip())
            return " ".join(texts) if texts else None
        except Exception:
            pass

    if path.endswith(".json"):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                texts = [
                    item.get("text", "") or item.get("content", "")
                    for item in data
                    if isinstance(item, dict)
                ]
                return " ".join(t for t in texts if t.strip()) or None
            elif isinstance(data, dict):
                utterances = data.get("utterances", [])
                if utterances:
                    return " ".join(
                        u.get("text", "") for u in utterances if u.get("text")
                    )
        except Exception:
            pass

    lines = content.split("\n")
    texts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\d+$", line):
            continue
        if "-->" in line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            texts.append(clean.strip())
    return " ".join(texts) if texts else None


def _download_subtitles(url: str, output_dir: str, use_cookies: bool) -> Tuple[Optional[str], dict]:
    import yt_dlp

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh", "zh-Hans", "zh-CN", "zh-Hant"],
        "outtmpl": os.path.join(output_dir, "%(id)s"),
        "socket_timeout": 30,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
    }
    if use_cookies:
        ydl_opts.update(_cookie_opt())

    video_info = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_info = _extract_video_info(info)
            video_id = info.get("id", "unknown")
    except Exception:
        return None, video_info

    for ext in [
        ".zh-Hans.json3", ".zh-CN.json3", ".zh.json3",
        ".zh-Hans.vtt", ".zh-CN.vtt", ".zh.vtt",
        ".zh-Hans.srt", ".zh-CN.srt", ".zh.srt",
        ".json3", ".vtt", ".srt", ".json",
    ]:
        path = os.path.join(output_dir, f"{video_id}{ext}")
        if os.path.exists(path):
            text = _parse_subtitle_file(path)
            if text and len(text.strip()) > 10:
                return text.strip(), video_info
    return None, video_info


# ============================================================
# Tier 2: 下载视频 -> 提取音频 -> ASR
# ============================================================

def _download_video(url: str, output_dir: str, use_cookies: bool) -> Tuple[Optional[str], dict]:
    import yt_dlp

    output_path = os.path.join(output_dir, "video.%(ext)s")
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "socket_timeout": 30,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
    }
    if use_cookies:
        ydl_opts.update(_cookie_opt())

    video_info = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_info = _extract_video_info(info)
            ydl.download([url])
    except Exception:
        return None, video_info

    for fname in os.listdir(output_dir):
        if fname.startswith("video.") and fname != "video.%(ext)s":
            return os.path.join(output_dir, fname), video_info
    return None, video_info


def _extract_audio(video_path: str, output_dir: str) -> Optional[str]:
    if not _FFMPEG_AVAILABLE:
        return None
    audio_path = os.path.join(output_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-y", audio_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            return None
    except Exception:
        return None
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        return audio_path
    return None


def _get_whisper_model():
    """懒加载 faster-whisper 模型单例。

    优先加载本地 data/whisper-medium(免下载,离线可用);不存在则按
    media_whisper_model 从 HuggingFace 下载(已配 HF_ENDPOINT 镜像加速)。
    """
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        local = DATA_DIR / "whisper-medium"
        model_src = str(local) if local.exists() else (settings.media_whisper_model or "small")
        _whisper_model = WhisperModel(
            model_src,
            device="cpu",
            compute_type="int8",
        )
    return _whisper_model


def _transcribe_audio(audio_path: str) -> Optional[str]:
    try:
        model = _get_whisper_model()
        segments, _ = model.transcribe(
            audio_path, language="zh", beam_size=5, vad_filter=True
        )
        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts) if texts else None
    except Exception:
        return None


# ============================================================
# 同步主入口:编排三级管线(带 cookie 兜底)
# ============================================================

def _run_pipeline_once(share_link: str, use_cookies: bool) -> Tuple[Optional[str], str, dict]:
    with tempfile.TemporaryDirectory(prefix="douyin_dl_") as tmpdir:
        sub_text, video_info = _download_subtitles(share_link, tmpdir, use_cookies)
        if sub_text and len(sub_text.strip()) > 10:
            return sub_text.strip(), "subtitle", video_info

        video_path, dl_info = _download_video(share_link, tmpdir, use_cookies)
        video_info.update(dl_info)
        if video_path:
            audio_path = _extract_audio(video_path, tmpdir)
            if audio_path:
                transcript = _transcribe_audio(audio_path)
                if transcript and len(transcript.strip()) > 10:
                    return transcript.strip(), "asr", video_info
        return None, "all methods failed", video_info


def extract_script_from_video(share_link: str) -> Tuple[Optional[str], str, dict]:
    """从短视频链接提取口播文案。

    返回 (文案文本, 提取方式, video_info)
    提取方式: "subtitle" | "asr" | "all methods failed"
    """
    use_cookies = bool(settings.media_cookies_browser.strip())
    # 第一轮:按配置(默认带 cookie)
    transcript, method, video_info = _run_pipeline_once(share_link, use_cookies)
    if transcript:
        return transcript, method, video_info
    # 兜底:带 cookie 全失败时,无 cookie 再试(部分视频反而不需 cookie)
    if use_cookies:
        transcript, method, video_info2 = _run_pipeline_once(share_link, False)
        video_info.update(video_info2)
        if transcript:
            return transcript, method, video_info
    return None, method or "all methods failed", video_info


# ============================================================
# 对外 async 入口:在线程池跑同步管线(不阻塞事件循环)
# ============================================================

async def extract_script(share_link: str) -> Tuple[Optional[str], str, dict]:
    return await asyncio.to_thread(extract_script_from_video, share_link)


# ============================================================
# 链接识别:判断用户输入是否含短视频分享链接
# ============================================================

# 抖音 / 快手 / B站 等 yt-dlp 支持的短视频平台
_LINK_PATTERNS = [
    re.compile(r"https?://v\.douyin\.com/\S+"),
    re.compile(r"https?://(?:www\.)?douyin\.com/\S+"),
    re.compile(r"https?://(?:www\.)?iesdouyin\.com/\S+"),
    re.compile(r"https?://v\.kuaishou\.com/\S+"),
    re.compile(r"https?://(?:www\.)?kuaishou\.com/\S+"),
    re.compile(r"https?://b23\.tv/\S+"),
    re.compile(r"https?://(?:www\.)?bilibili\.com/\S+"),
]


def detect_share_link(text: str) -> Optional[str]:
    """从用户输入中抽取第一个短视频分享链接,无则返回 None。"""
    if not text:
        return None
    for pat in _LINK_PATTERNS:
        m = pat.search(text)
        if m:
            # 去掉尾部常见标点(分享文案常带换行/句号)
            return m.group(0).rstrip("。.,;；!！?？)）")
    return None
