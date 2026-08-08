"""视频媒体处理模块：下载抖音视频、提取音频、语音识别转文字

三级提取管线：
1. yt-dlp 下载字幕（最快最准）
2. yt-dlp 下载视频 -> ffmpeg 提取音频 -> faster-whisper 语音识别
3. 返回 (None, 错误信息) 交由上层降级到 HTML 抓取
"""

import os
import re
import json
import shutil
import tempfile
import subprocess
from typing import Optional, Tuple

import yt_dlp


# ============================================================
# ffmpeg 可用性检查
# ============================================================

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


# ============================================================
# Whisper 模型单例
# ============================================================

_whisper_model = None


def _get_whisper_model():
    """懒加载 faster-whisper 模型单例（首次加载约 488MB，后续复用）"""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )
    return _whisper_model


# ============================================================
# Tier 1: 下载字幕
# ============================================================

def _extract_video_info(info: dict) -> dict:
    """从 yt-dlp info dict 中提取关键元信息"""
    # 从 title/description 中提取 #话题标签
    text_for_tags = " ".join(filter(None, [info.get("title", ""), info.get("description", "")]))
    topics = re.findall(r'#([^\s#]+)', text_for_tags)

    return {
        "title": info.get("title", ""),
        "author": info.get("uploader", "") or info.get("channel", "") or info.get("uploader_id", ""),
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


def _download_subtitles(url: str, output_dir: str) -> Tuple[Optional[str], dict]:
    """用 yt-dlp 下载抖音字幕，返回 (纯文本, video_info) 或 (None, video_info)"""
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
        "cookiesfrombrowser": ("chrome",),
    }

    video_info = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_info = _extract_video_info(info)
            video_id = info.get("id", "unknown")
    except Exception:
        return None, video_info

    # 查找下载的字幕文件
    for ext in [".zh-Hans.json3", ".zh-CN.json3", ".zh.json3",
                ".zh-Hans.vtt", ".zh-CN.vtt", ".zh.vtt",
                ".zh-Hans.srt", ".zh-CN.srt", ".zh.srt",
                ".json3", ".vtt", ".srt", ".json"]:
        path = os.path.join(output_dir, f"{video_id}{ext}")
        if os.path.exists(path):
            text = _parse_subtitle_file(path)
            if text and len(text.strip()) > 10:
                return text.strip(), video_info

    return None, video_info


def _parse_subtitle_file(path: str) -> Optional[str]:
    """解析字幕文件（JSON3 / VTT / SRT / Douyin JSON）"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    # JSON3 格式
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

    # Douyin 原生 JSON
    if path.endswith(".json"):
        try:
            data = json.loads(content)
            # 尝试多种可能的结构
            if isinstance(data, list):
                texts = [item.get("text", "") or item.get("content", "")
                         for item in data if isinstance(item, dict)]
                return " ".join(t for t in texts if t.strip()) or None
            elif isinstance(data, dict):
                utterances = data.get("utterances", [])
                if utterances:
                    return " ".join(u.get("text", "") for u in utterances if u.get("text"))
        except Exception:
            pass

    # VTT / SRT：去掉时间戳和序号
    lines = content.split("\n")
    texts = []
    for line in lines:
        line = line.strip()
        # 跳过空行、序号、时间戳行、WEBVTT 头部
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
        # 去掉 HTML 标签
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            texts.append(clean.strip())

    return " ".join(texts) if texts else None


# ============================================================
# Tier 2a: 下载视频
# ============================================================

def _download_video(url: str, output_dir: str) -> Tuple[Optional[str], dict]:
    """用 yt-dlp 下载抖音视频，返回 (.mp4 文件路径, video_info) 或 (None, video_info)"""
    output_path = os.path.join(output_dir, "video.%(ext)s")
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "socket_timeout": 30,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "cookiesfrombrowser": ("chrome",),
    }

    video_info = {}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_info = _extract_video_info(info)
            ydl.download([url])
    except Exception:
        return None, video_info

    # 查找下载的视频文件
    for fname in os.listdir(output_dir):
        if fname.startswith("video.") and fname != "video.%(ext)s":
            return os.path.join(output_dir, fname), video_info

    return None, video_info


# ============================================================
# Tier 2b: 提取音频
# ============================================================

def _extract_audio(video_path: str, output_dir: str) -> Optional[str]:
    """用 ffmpeg 从视频中提取 16kHz 单声道 WAV"""
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
        result = subprocess.run(
            cmd, capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            return None
    except Exception:
        return None

    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        return audio_path

    return None


# ============================================================
# Tier 2c: 语音识别
# ============================================================

def _transcribe_audio(audio_path: str) -> Optional[str]:
    """用 faster-whisper 将音频转写为文字"""
    try:
        model = _get_whisper_model()
        segments, _ = model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
            vad_filter=True,
        )
        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts) if texts else None
    except Exception:
        return None


# ============================================================
# 主入口：编排三级管线
# ============================================================

def extract_script_from_video(share_link: str) -> Tuple[Optional[str], str, dict]:
    """从抖音链接提取视频口播文案

    返回 (文案文本, 提取方式, video_info)
    提取方式: "subtitle" | "asr" | "page_desc"
    video_info: 视频元信息 dict（title, author, duration, like_count, video_url, tags, topics, ...）
    """
    with tempfile.TemporaryDirectory(prefix="douyin_dl_") as tmpdir:
        # Tier 1: 尝试下载字幕
        sub_text, video_info = _download_subtitles(share_link, tmpdir)
        if sub_text and len(sub_text.strip()) > 10:
            return sub_text.strip(), "subtitle", video_info

        # Tier 2: 下载视频 -> 提取音频 -> ASR
        video_path, dl_info = _download_video(share_link, tmpdir)
        # 合并 video_info（_download_video 可能拿到更完整的信息）
        video_info.update(dl_info)
        if video_path:
            audio_path = _extract_audio(video_path, tmpdir)
            if audio_path:
                transcript = _transcribe_audio(audio_path)
                if transcript and len(transcript.strip()) > 10:
                    return transcript.strip(), "asr", video_info

        # 全部失败
        return None, "all methods failed", video_info
