"""TTS + 字幕打轴服务(成片管线第一环)。

整段脚本一次性 DubbingX 合成 -> 上传火山 TOS(临时,供 ATA 公网拉取)-> ffprobe 取时长 ->
火山 ATA 打轴得逐句/逐词时间戳 -> 删 TOS -> 音频转存本地(播放 + 后续合成)。
后台任务跑(DB 是真源),支持取消与整轨重生成。
镜像图片管线:pending|generating|done|error|cancelled 状态 + 进程内取消集合。
"""

import asyncio
import json
import os
import shutil
import tempfile
from typing import Optional

import httpx

from app.db import AsyncSessionLocal
from app.repositories import audio_track_repo
from app.services import storage as storage_service
from app.services import task_runner
from app.services import dubbingx_client as dubbingx
from app.services import volcengine_tts_client as volc_tts
from app.services import volcengine_ata_client as ata

# ffprobe 路径(取音频时长;DubbingX 无词级时间戳)
_FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

# 轮询上限(单阶段),2s 一次 -> 约 5 分钟
_POLL_INTERVAL = 2.0
_POLL_DEADLINE = 300.0

# 已取消的音轨 id(运行中任务每步前检查;进程内模式生效)
_cancelled: set[str] = set()


def _storage_key(track_id: str, fmt: str) -> str:
    return f"audio/{track_id}.{fmt or 'mp3'}"


async def _ffprobe_duration(data: bytes, fmt: str = "mp3") -> Optional[float]:
    """对音频字节跑 ffprobe 取时长(秒)。写临时文件,失败返回 None。"""
    if not _FFPROBE:
        return None
    fd, path = tempfile.mkstemp(suffix=f".{fmt or 'mp3'}")
    try:
        os.write(fd, data)
        os.close(fd)
        proc = await asyncio.create_subprocess_exec(
            _FFPROBE, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        out = out.decode(errors="ignore").strip()
        return float(out) if out else None
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _resolve_voice(
    provider: Optional[str],
    voice_id: Optional[str],
    emotion: Optional[str],
    language: Optional[str],
    audio_speed: Optional[float],
    audio_pitch: Optional[float],
    audio_volume: Optional[float],
    file_format: Optional[str],
) -> dict:
    """合并请求参数与 config 默认值。voice_id 必须有(默认或请求传入)。"""
    from app.config import settings

    selected_provider = (provider or settings.tts_provider).lower()
    if selected_provider not in {"dubbingx", "volcengine"}:
        raise ValueError("不支持的 TTS 供应商，仅支持 dubbingx 或 volcengine")
    vid = voice_id or (settings.volc_tts_voice_type if selected_provider == "volcengine" else settings.dubbingx_default_voice_id)
    if not vid:
        raise ValueError("未指定音色:请在请求传入 voice_id 或配置 DUBBINGX_DEFAULT_VOICE_ID")
    return {
        "provider": selected_provider,
        "voice_id": vid,
        "emotion": emotion if emotion is not None else settings.dubbingx_default_emotion or None,
        "language": language or settings.dubbingx_default_language,
        "audio_speed": audio_speed if audio_speed is not None else settings.dubbingx_default_speed,
        "audio_pitch": audio_pitch if audio_pitch is not None else settings.dubbingx_default_pitch,
        "audio_volume": audio_volume if audio_volume is not None else settings.dubbingx_default_volume,
        "file_format": file_format or settings.dubbingx_default_format,
    }


async def start_generation(
    *,
    conversation_id: str,
    project_id: str,
    script_version_id: Optional[str],
    script_text: str,
    provider: Optional[str] = None,
    voice_id: Optional[str] = None,
    emotion: Optional[str] = None,
    language: Optional[str] = None,
    audio_speed: Optional[float] = None,
    audio_pitch: Optional[float] = None,
    audio_volume: Optional[float] = None,
    file_format: Optional[str] = None,
) -> dict:
    """为作品创建 pending 音轨(替换旧轨),启动后台 TTS+ATA 流水线。"""
    if not (script_text or "").strip():
        raise ValueError("脚本内容为空,无法配音")

    voice = _resolve_voice(provider, voice_id, emotion, language, audio_speed, audio_pitch, audio_volume, file_format)

    async with AsyncSessionLocal() as s:
        # 整轨重新生成:物理删除旧音轨(含历史 error/cancelled),避免累积
        await audio_track_repo.delete_tracks_by_project(s, project_id)
        track = await audio_track_repo.create_track(
            s,
            conversation_id=conversation_id,
            project_id=project_id,
            script_version_id=script_version_id,
            status="pending",
            script_text=script_text,
            **voice,
        )

    _cancelled.discard(track.id)
    await task_runner.submit("tts_generation", track_id=track.id)
    return audio_track_repo.to_artifact_dict(track)


async def _mark(track_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        await audio_track_repo.update_track(s, track_id, **fields)


async def run_tts_task(track_id: str) -> None:
    """后台流水线:tts 合成 -> TOS 临时落地(供 ATA 拉取)-> ffprobe 时长 ->
    ATA 打轴 -> 删 TOS -> 音频转存本地(播放/合成)-> 字幕。

    作为可注册任务(进程内 asyncio / Arq 共用)。
    """
    async with AsyncSessionLocal() as s:
        track = await audio_track_repo.get_track(s, track_id)
    if track is None:
        return
    if track.status not in ("pending", "generating"):
        return  # 已 done/cancelled/error,不重复处理
    if track_id in _cancelled:
        await _mark(track_id, status="cancelled", error="用户取消")
        return

    try:
        # ---- 阶段一:TTS ----
        await _mark(track_id, status="generating", stage="tts", error=None)
        if track.provider == "volcengine":
            audio_bytes, tts_task_id = await volc_tts.synthesize(
                text=track.script_text, voice_type=track.voice_id, emotion=track.emotion, speed=track.audio_speed,
                pitch=track.audio_pitch, volume=track.audio_volume, fmt=track.file_format,
            )
            await _mark(track_id, tts_task_id=tts_task_id)
        else:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                tts_task_id = await dubbingx.submit_task(
                client,
                voice_id=track.voice_id,
                text=track.script_text,
                emotion=track.emotion,
                language=track.language,
                audio_speed=track.audio_speed,
                audio_pitch=track.audio_pitch,
                audio_volume=track.audio_volume,
                file_format=track.file_format,
            )
                await _mark(track_id, tts_task_id=tts_task_id)
                file_url = await _poll_tts(client, track_id, tts_task_id)
                if file_url is None: return
                r = await client.get(file_url, timeout=120)
                if r.status_code != 200: raise dubbingx.DubbingXError(f"下载音频失败 {r.status_code}")
                audio_bytes = r.content

        # 落地 TOS(ATA 打轴需公网拉取,临时中转)+ 取时长
        tos_key = _storage_key(track_id, track.file_format)
        tos_url = await storage_service.save_audio(tos_key, audio_bytes)
        duration = await _ffprobe_duration(audio_bytes, track.file_format)
        await _mark(track_id, audio_url=tos_url, audio_duration_sec=duration)

        if track_id in _cancelled:
            await _safe_delete_audio(tos_url)
            await _mark(track_id, status="cancelled", error="用户取消")
            return

        # ---- 阶段二:火山 ATA 字幕打轴 ----
        await _mark(track_id, stage="ata")
        utterances: Optional[list] = None
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                ata_task_id = await ata.submit(
                    client, audio_url=tos_url, audio_text=track.script_text
                )
                await _mark(track_id, ata_task_id=ata_task_id)
                utterances = await _poll_ata(client, track_id, ata_task_id)
        finally:
            # ATA 完成(无论成败/取消)即删 TOS 临时音频;持久副本改存本地。
            await _safe_delete_audio(tos_url)

        if utterances is None:
            return  # 已取消或已标记 error(TOS 已在 finally 删除)

        # 音频转存本地(播放 + 后续合成用),audio_url 指向本地持久路径
        local_url = await storage_service.save_audio_local(
            f"{track_id}.{track.file_format}", audio_bytes
        )
        await _mark(track_id, audio_url=local_url)

        subtitles = [{**u, "order": idx} for idx, u in enumerate(utterances)]
        await _mark(
            track_id,
            status="done",
            stage=None,
            subtitles_json=json.dumps(subtitles, ensure_ascii=False),
            error=None,
        )
    except Exception as e:  # noqa: BLE001 - 后台任务兜底
        await _mark(track_id, status="error", error=f"{type(e).__name__}: {e}"[:500])


async def _safe_delete_audio(web_path: str) -> None:
    """删除 TOS 临时音频,忽略错误(清理失败不阻塞主流程)。"""
    try:
        await storage_service.delete_audio_by_web_path(web_path)
    except Exception:
        pass


async def _poll_tts(client: httpx.AsyncClient, track_id: str, tts_task_id: str) -> Optional[str]:
    """轮询 DubbingX 任务至终态,返回 file_url(取消/失败返回 None 并已标记)。"""
    import time

    deadline = time.monotonic() + _POLL_DEADLINE
    while time.monotonic() < deadline:
        if track_id in _cancelled:
            await _mark(track_id, status="cancelled", error="用户取消")
            return None
        info = await dubbingx.get_task_info(client, tts_task_id)
        st = info.get("status", "")
        if st == "Completed":
            url = info.get("file_url")
            if not url:
                await _mark(track_id, status="error", error="DubbingX 完成但未返回 fileUrl")
                return None
            return url
        if st == "Failed":
            await _mark(track_id, status="error", error="DubbingX 合成失败")
            return None
        await asyncio.sleep(_POLL_INTERVAL)
    await _mark(track_id, status="error", error="DubbingX 轮询超时")
    return None


async def _poll_ata(client: httpx.AsyncClient, track_id: str, ata_task_id: str) -> Optional[list]:
    """轮询 ATA 任务至终态,返回 utterances(取消/失败返回 None 并已标记)。"""
    import time

    deadline = time.monotonic() + _POLL_DEADLINE
    while time.monotonic() < deadline:
        if track_id in _cancelled:
            await _mark(track_id, status="cancelled", error="用户取消")
            return None
        q = await ata.query(client, ata_task_id, blocking=0)
        code = q.get("code", "")
        if code == "0":
            return q.get("utterances") or []
        if code != "2000":
            await _mark(track_id, status="error", error=f"ATA 打轴失败: {q.get('message') or code}")
            return None
        await asyncio.sleep(_POLL_INTERVAL)
    await _mark(track_id, status="error", error="ATA 轮询超时")
    return None


async def cancel_generation(conversation_id: str) -> dict:
    """取消会话当前进行中的音轨生成。"""
    async with AsyncSessionLocal() as s:
        tracks = await audio_track_repo.list_tracks_by_conversation(s, conversation_id)
        ids = [t.id for t in tracks]
        for tid in ids:
            _cancelled.add(tid)
        for t in tracks:
            if t.status in ("pending", "generating"):
                await audio_track_repo.update_track(
                    s, t.id, status="cancelled", error="用户取消"
                )
    return {"cancelled": len(ids), "tracks": ids}


async def regenerate(track_id: str) -> Optional[dict]:
    """整轨重生成:复用原音色参数与脚本文本,重置为 pending 再跑。"""
    async with AsyncSessionLocal() as s:
        track = await audio_track_repo.get_track(s, track_id)
        if track is None:
            return None
        await audio_track_repo.update_track(
            s,
            track_id,
            status="pending",
            stage=None,
            tts_task_id=None,
            ata_task_id=None,
            audio_url=None,
            audio_duration_sec=None,
            subtitles_json="[]",
            error=None,
        )
    _cancelled.discard(track_id)
    await task_runner.submit("tts_generation", track_id=track_id)
    async with AsyncSessionLocal() as s:
        t = await audio_track_repo.get_track(s, track_id)
        return audio_track_repo.to_artifact_dict(t) if t else None


# ---- 调试台(临时,不落库;直接合成+可选停顿+可选打轴,返回音频URL+字幕)----

async def debug_synthesize(
    *,
    text: str,
    voice_id: str,
    emotion: Optional[str],
    language: str,
    audio_speed: float,
    audio_pitch: float,
    audio_volume: float,
    file_format: str,
    auto_pause: bool,
    align: bool,
) -> dict:
    """调试用:不落库,直接 DubbingX 合成(+可选 autoPause +可选 ATA 打轴),返回音频URL+字幕。

    供 /api/tts/debug-synthesize 调用;同步等待(轮询),调试场景可接受。
    """
    import time
    import uuid

    if not (text or "").strip():
        raise ValueError("文本为空")

    text_used = text
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 可选:自动停顿
        if auto_pause:
            paused = await dubbingx.auto_pause(client, text)
            if paused:
                text_used = paused

        # DubbingX 合成
        tts_task_id = await dubbingx.submit_task(
            client,
            voice_id=voice_id,
            text=text_used,
            emotion=emotion or None,
            language=language,
            audio_speed=audio_speed,
            audio_pitch=audio_pitch,
            audio_volume=audio_volume,
            file_format=file_format,
        )
        file_url: Optional[str] = None
        deadline = time.monotonic() + _POLL_DEADLINE
        while time.monotonic() < deadline:
            info = await dubbingx.get_task_info(client, tts_task_id)
            st = info.get("status", "")
            if st == "Completed":
                file_url = info.get("file_url")
                break
            if st == "Failed":
                raise dubbingx.DubbingXError("DubbingX 合成失败")
            await asyncio.sleep(_POLL_INTERVAL)
        if not file_url:
            raise dubbingx.DubbingXError("DubbingX 轮询超时")

        r = await client.get(file_url, timeout=120)
        if r.status_code != 200:
            raise dubbingx.DubbingXError(f"下载音频失败 {r.status_code}")
        audio_bytes = r.content

    duration = await _ffprobe_duration(audio_bytes, file_format)

    # 持久化到本地(供前端播放)
    key = f"debug/{uuid.uuid4().hex}.{file_format or 'mp3'}"
    local_url = await storage_service.save_audio_local(key, audio_bytes)

    subtitles: list = []
    if align:
        # TOS 临时中转 -> ATA 打轴 -> 删 TOS
        tos_key = f"debug/{uuid.uuid4().hex}.{file_format or 'mp3'}"
        tos_url = await storage_service.save_audio(tos_key, audio_bytes)
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                ata_task_id = await ata.submit(client, audio_url=tos_url, audio_text=text)
                utterances: Optional[list] = None
                deadline = time.monotonic() + _POLL_DEADLINE
                while time.monotonic() < deadline:
                    q = await ata.query(client, ata_task_id, blocking=0)
                    if q.get("code") == "0":
                        utterances = q.get("utterances") or []
                        break
                    if q.get("code") != "2000":
                        raise RuntimeError(f"ATA 打轴失败: {q.get('message') or q.get('code')}")
                    await asyncio.sleep(_POLL_INTERVAL)
                if utterances is None:
                    raise RuntimeError("ATA 打轴超时")
                subtitles = [{**u, "order": idx} for idx, u in enumerate(utterances)]
        finally:
            await _safe_delete_audio(tos_url)

    return {
        "audio_url": local_url,
        "duration": duration,
        "subtitles": subtitles,
        "emotion_used": emotion or "(自动识别)",
        "text_used": text_used,
        "task_id": tts_task_id,
    }


# 注册为后台任务(供 task_runner 调度)
task_runner.register_task("tts_generation", run_tts_task)
