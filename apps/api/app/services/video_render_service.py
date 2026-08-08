"""视频成片服务(成片管线第三环:静态分镜 + 音频 + 字幕 -> mp4)。

不含图生视频:每镜用静态分镜图按对齐时长持续展示,拼成无声视频,再叠音频 +
硬烧字幕。音频是主时钟:分镜旁白(narration)与 ATA 字幕做归一化字符对齐,
把每镜映射到字幕时间轴,得到每镜起止毫秒;无法对齐则均分回退。

后台任务跑(DB 是真源),支持取消与整片重生成。镜像 TTS/图片管线:
pending|generating|done|error|cancelled + 进程内取消集合。
"""

import asyncio
import difflib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings
from app.db import AsyncSessionLocal
from app.repositories import (
    audio_track_repo,
    image_repo,
    storyboard_repo,
    video_render_repo,
)
from app.services import task_runner

_FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

# 进程内已取消的成片 id(每步前检查)
_cancelled: set[str] = set()

# 字幕归一化:只保留中文/字母/数字,去标点空白(对齐用)
_KEEP = re.compile(r"[^一-龥A-Za-z0-9]")
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
_CAPTION_PUNCTUATION = re.compile(r"[，。、“”‘’、；：…,.\"']+")


def _background_music_path() -> Optional[Path]:
    """返回可用背景音乐；音乐库为空或文件不受支持时保持纯口播合成。"""
    music_dir = settings.bg_music_dir
    if not music_dir.is_dir():
        return None
    tracks = sorted(
        (p for p in music_dir.iterdir() if p.is_file() and p.suffix.lower() in _AUDIO_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )
    return tracks[0] if tracks else None


def _norm(text: str) -> str:
    return _KEEP.sub("", text or "")


# ---------------------------------------------------------------- 对齐

def align_shots(shots: list[dict], subtitles: list[dict], total_ms: int) -> list[dict]:
    """把每镜旁白对齐到字幕时间轴,返回每镜 {start_ms, end_ms}。

    思路:norm(旁白拼接) == norm(字幕拼接),故可在归一化字符空间建立
    字幕<->时间映射,再按每镜旁白累计字符区间投影出起止时间。
    字符数不等时按比例缩放;字幕缺失时均分回退。
    """
    n = len(shots)
    if n == 0:
        return []
    avg = total_ms / n if total_ms > 0 else 0
    fallback = [
        {"start_ms": int(i * avg), "end_ms": int((i + 1) * avg)} for i in range(n)
    ]
    if not subtitles or total_ms <= 0:
        return fallback

    # 字幕归一化累计字符数
    sub_norms = [len(_norm(s.get("text", ""))) for s in subtitles]
    sub_cum: list[int] = []
    acc = 0
    for sn in sub_norms:
        acc += sn
        sub_cum.append(acc)
    total_sub = acc
    if total_sub == 0:
        return fallback

    # 分镜旁白归一化累计字符数
    shot_norms = [len(_norm(sh.get("narration", ""))) for sh in shots]
    shot_cum: list[int] = []
    acc2 = 0
    for snn in shot_norms:
        acc2 += snn
        shot_cum.append(acc2)
    total_shot = acc2
    if total_shot == 0:
        return fallback

    # 历史分镜复用时，分镜旁白与当前口播可能有增删改。不能只按总字数缩放，
    # 否则一次局部删除会让后续所有镜头持续偏移。用 SequenceMatcher 找到两份
    # 文本中的稳定锚点，再在相邻锚点之间局部插值，得到单调的字符坐标映射。
    shot_text = "".join(_norm(sh.get("narration", "")) for sh in shots)
    sub_text = "".join(_norm(s.get("text", "")) for s in subtitles)
    matcher = difflib.SequenceMatcher(None, shot_text, sub_text, autojunk=False)
    anchors: list[tuple[int, int]] = [(0, 0)]
    for block in matcher.get_matching_blocks():
        if block.size:
            anchors.append((block.a, block.b))
            anchors.append((block.a + block.size, block.b + block.size))
    anchors.append((total_shot, total_sub))
    # 去重并强制目标坐标单调，避免重复短语产生回跳。
    compact: list[tuple[int, int]] = []
    for source_pos, target_pos in sorted(anchors):
        target_pos = max(target_pos, compact[-1][1] if compact else 0)
        if compact and source_pos == compact[-1][0]:
            compact[-1] = (source_pos, max(compact[-1][1], target_pos))
        else:
            compact.append((source_pos, target_pos))

    def shot_char_to_sub_char(position: int) -> float:
        if position <= 0:
            return 0
        if position >= total_shot:
            return total_sub
        for idx in range(1, len(compact)):
            left, right = compact[idx - 1], compact[idx]
            if position <= right[0]:
                span = right[0] - left[0]
                if span <= 0:
                    return float(right[1])
                ratio = (position - left[0]) / span
                return left[1] + (right[1] - left[1]) * ratio
        return float(total_sub)
    sub_times = [(int(s["start_ms"]), int(s["end_ms"])) for s in subtitles]

    def char_to_time(p_sub: float) -> int:
        if p_sub <= 0:
            return sub_times[0][0]
        if p_sub >= total_sub:
            return sub_times[-1][1]
        for j, ce in enumerate(sub_cum):
            cs = sub_cum[j - 1] if j > 0 else 0
            if p_sub <= ce:
                span = ce - cs
                if span <= 0:
                    return sub_times[j][0]
                local = (p_sub - cs) / span
                ts, te = sub_times[j]
                return int(ts + (te - ts) * local)
        return sub_times[-1][1]

    timings: list[dict] = []
    prev_end = 0
    for i in range(n):
        s_char = shot_char_to_sub_char(shot_cum[i - 1] if i > 0 else 0)
        e_char = shot_char_to_sub_char(shot_cum[i])
        start = char_to_time(s_char)
        end = char_to_time(e_char)
        start = max(start, prev_end)  # 连续性
        if end <= start:
            end = start + 1
        if i == n - 1:
            end = total_ms  # 最后一镜收尾对齐音频
        timings.append({"start_ms": start, "end_ms": end})
        prev_end = end
    # 首镜从 0 起:覆盖首句字幕前的开头静音留白。否则拼接视频比音频短一个
    # 首句 start_ms,导致 -shortest 裁掉音频末尾、且所有镜头画面相对音频整体前移。
    # 画面先出现、旁白随后开始,本就是自然观感;末镜已收尾到 total_ms,故视频时长=音频。
    if timings:
        timings[0]["start_ms"] = 0
    return timings


# ---------------------------------------------------------------- SRT

def _ms_to_srt(ms: int) -> str:
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(subtitles: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(subtitles):
        lines.append(str(i + 1))
        lines.append(
            f"{_ms_to_srt(seg.get('start_ms', 0))} --> {_ms_to_srt(seg.get('end_ms', 0))}"
        )
        lines.append(str(seg.get("text", "")).strip())
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- 字幕渲染(PIL -> PNG -> ffmpeg overlay)
# 本机 ffmpeg 是精简构建(无 libass/freetype),subtitles/drawtext 滤镜均不可用;
# 故用 PIL 把每句字幕渲染成透明 PNG,再用 ffmpeg overlay(核心滤镜)按时段叠加。

_SUBTITLE_FONT = next(
    (
        p
        for p in [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
        if os.path.exists(p)
    ),
    None,
)


def _sub_layout(width: int) -> tuple[int, int]:
    """按视频宽度给字幕字号 / 最大行宽。"""
    if width >= 1200:
        return 44, width - 180
    return 34, width - 120


def _wrap_text(text: str, font, max_width: float) -> list[str]:
    """中文逐字断行(中文无词边界,按字符宽度累计)。"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if font.getlength(cur + ch) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or [""]


def _caption_text(text: str) -> str:
    """短视频烧录字幕省略停顿标点，避免全角标点在字体字框中显得上下居中。"""
    return _CAPTION_PUNCTUATION.sub("", (text or "").replace("\n", ""))


def _render_sub_png(
    text: str, font_path: str, font_size: int, out_path: str, max_width: int
) -> None:
    """PIL 渲染单句字幕:短视频常用亮黄字 + 粗黑描边。"""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, font_size)
    lines = _wrap_text(_caption_text(text), font, max_width)
    line_h = font_size + 10
    widths = [font.getlength(l) for l in lines]
    w = int(max(widths) + 40) if widths else 40
    h = int(line_h * len(lines) + 16)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 8
    for line in lines:
        x = (w - font.getlength(line)) / 2
        for dx, dy in [(-3, -3), (-3, 0), (-3, 3), (0, -3), (0, 3), (3, -3), (3, 0), (3, 3)]:
            d.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        d.text((x, y), line, font=font, fill=(255, 231, 0, 255))
        y += line_h
    img.save(out_path)


# ---------------------------------------------------------------- 路径解析

def _image_local_path(web_path: str) -> Optional[str]:
    """分镜图 web 路径 -> 本地文件路径(local 模式);公网 URL 返回 None(需下载)。"""
    if web_path and web_path.startswith("/api/img/"):
        return str(settings.images_dir / web_path[len("/api/img/"):])
    if web_path and web_path.startswith("http"):
        return None
    return web_path or None


def _audio_local_path(web_path: str) -> Optional[str]:
    if web_path and web_path.startswith("/api/audio/"):
        return str(settings.audio_dir / web_path[len("/api/audio/"):])
    if web_path and web_path.startswith("http"):
        return None
    return web_path or None


async def _download(url: str, dest: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get(url, timeout=120)
        r.raise_for_status()
        Path(dest).write_bytes(r.content)
    return dest


def _resolution(aspect_ratio: str) -> tuple[int, int]:
    return {
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "1:1": (1080, 1080),
    }.get(aspect_ratio, (1280, 720))


def _escape_srt_path(p: str) -> str:
    """ffmpeg subtitles filter 路径转义(: , ' \)。"""
    return (
        p.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
    )


# ---------------------------------------------------------------- ffmpeg

class _Cancelled(Exception):
    pass


async def _run_ff(args: list[str], render_id: str, label: str) -> None:
    if render_id in _cancelled:
        raise _Cancelled
    proc = await asyncio.create_subprocess_exec(
        _FFMPEG,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg {label} 失败(rc={proc.returncode}): "
            f"{err.decode(errors='ignore')[-800:]}"
        )


async def _compose(
    render_id: str,
    images: list,
    timings: list[dict],
    subtitles: list[dict],
    audio_web_path: str,
    aspect_ratio: str,
) -> str:
    """合成 mp4:每镜静态段 -> concat -> 口播/低音量 BGM 混音 + 烧字幕。

    返回 web 路径 /api/video/{render_id}.mp4。
    """
    tmp = tempfile.mkdtemp(prefix="vgf_render_")
    try:
        W, H = _resolution(aspect_ratio)

        # 1. 图片本地路径(http 的下载到临时目录)
        img_paths: list[str] = []
        for i, img in enumerate(images):
            p = _image_local_path(img.local_path)
            if p is None:  # 公网 URL(S3 模式)
                p = os.path.join(tmp, f"src_{i:03d}.png")
                await _download(img.local_path, p)
            img_paths.append(p)
            if render_id in _cancelled:
                raise _Cancelled

        # 2. 每镜:静态图 + 对齐时长 -> 段视频(统一分辨率/SAR,便于 concat)
        seg_files: list[str] = []
        for i, (img_p, t) in enumerate(zip(img_paths, timings)):
            if render_id in _cancelled:
                raise _Cancelled
            dur = max((t["end_ms"] - t["start_ms"]) / 1000.0, 0.1)
            seg = os.path.join(tmp, f"seg_{i:03d}.mp4")
            vf = (
                f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
            )
            await _run_ff(
                [
                    "-loop", "1", "-i", img_p,
                    "-t", f"{dur:.3f}",
                    "-r", "30",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-vf", vf,
                    "-preset", "fast",
                    seg,
                ],
                render_id,
                f"seg{i}",
            )
            seg_files.append(seg)

        if render_id in _cancelled:
            raise _Cancelled

        # 3. concat 段视频(编码一致 -> stream copy)
        list_path = os.path.join(tmp, "list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for seg in seg_files:
                # concat demuxer 路径需单引号;相对 tmp 写文件名即可
                f.write(f"file '{os.path.basename(seg)}'\n")
        video_only = os.path.join(tmp, "video_only.mp4")
        await _run_ff(
            ["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", video_only],
            render_id,
            "concat",
        )

        # 4. 字幕:每句 PIL 渲染 PNG(本机 ffmpeg 无 libass,用 overlay 叠加)
        if not _SUBTITLE_FONT:
            raise RuntimeError("未找到中文字体,无法渲染字幕")
        font_size, max_w = _sub_layout(W)
        sub_pngs: list[str] = []
        for i, seg in enumerate(subtitles):
            png = os.path.join(tmp, f"sub_{i:03d}.png")
            _render_sub_png(
                str(seg.get("text", "")).strip(), _SUBTITLE_FONT, font_size, png, max_w
            )
            sub_pngs.append(png)
            if render_id in _cancelled:
                raise _Cancelled

        # 5. 叠口播、低音量背景音乐与字幕。BGM 自动循环，amix 以口播长度为准。
        audio_p = _audio_local_path(audio_web_path)
        if audio_p is None:  # 公网 URL
            audio_p = os.path.join(tmp, "audio.mp3")
            await _download(audio_web_path, audio_p)

        final_tmp = os.path.join(tmp, "final.mp4")
        bg_music = _background_music_path()
        ff_args: list[str] = ["-i", video_only, "-i", audio_p]
        png_input_offset = 2
        if bg_music is not None:
            # -stream_loop 放在该输入前，保证短音乐能覆盖整段口播。
            ff_args += ["-stream_loop", "-1", "-i", str(bg_music)]
            png_input_offset = 3
        for png in sub_pngs:
            ff_args += ["-i", png]
        # 字幕输入索引在有 BGM 时后移一位。
        fc_parts: list[str] = []
        prev = "[0:v]"
        n = len(sub_pngs)
        for i, _png in enumerate(sub_pngs):
            inp = f"[{i + png_input_offset}:v]"
            out = "[vout]" if i == n - 1 else f"[v{i}]"
            s = subtitles[i]["start_ms"] / 1000.0
            e = subtitles[i]["end_ms"] / 1000.0
            fc_parts.append(
                f"{prev}{inp}overlay=x=(W-w)/2:y=H-h-70:"
                f"enable='between(t,{s},{e})'{out}"
            )
            prev = out
        filter_complex = ";".join(fc_parts)
        if bg_music is not None:
            # 0.18 约等于 -15 dB，提供可感知氛围但不抢口播。
            filter_complex = ";".join(
                [
                    filter_complex,
                    "[1:a]aresample=48000[voice]",
                    "[2:a]volume=0.18,aresample=48000[bgm]",
                    "[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]",
                ]
            )
            audio_map = "[aout]"
        else:
            audio_map = "1:a"
        ff_args += [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", audio_map,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            final_tmp,
        ]
        await _run_ff(ff_args, render_id, "final")

        # 6. 落地 video_dir
        settings.video_dir.mkdir(parents=True, exist_ok=True)
        final_path = settings.video_dir / f"{render_id}.mp4"
        shutil.move(final_tmp, str(final_path))
        return f"/api/video/{render_id}.mp4"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 任务流

async def _mark(render_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        await video_render_repo.update_render(s, render_id, **fields)


async def run_render_task(render_id: str) -> None:
    """后台流水线:对齐(旁白↔字幕)-> ffmpeg 合成 -> 落地本地 mp4。"""
    async with AsyncSessionLocal() as s:
        render = await video_render_repo.get_render(s, render_id)
    if render is None:
        return
    if render.status not in ("pending", "generating"):
        return
    if render_id in _cancelled:
        await _mark(render_id, status="cancelled", error="用户取消")
        return

    try:
        await _mark(render_id, status="generating", stage="align", error=None)

        # 取素材快照(按 render 记录的引用,保证合成的是生成时的素材)
        async with AsyncSessionLocal() as s:
            audio = await audio_track_repo.get_track(s, render.audio_track_id) \
                if render.audio_track_id else None
            sb = await storyboard_repo.get_storyboard(s, render.storyboard_version_id) \
                if render.storyboard_version_id else None
            images = (
                await image_repo.list_images_by_storyboard(
                    s, render.storyboard_version_id, statuses=["done"]
                )
                if render.storyboard_version_id
                else []
            )

        if audio is None or not audio.audio_url:
            raise ValueError("找不到已完成的配音音频,请先生成配音")
        if sb is None:
            raise ValueError("找不到分镜,请先生成分镜")
        shots = json.loads(sb.shots_json or "[]")
        subtitles = json.loads(audio.subtitles_json or "[]")
        if not shots:
            raise ValueError("分镜为空")
        if not subtitles:
            raise ValueError("音频缺少字幕时间轴,无法对齐")
        if len(images) < len(shots):
            raise ValueError(
                f"分镜图片不全(已有 {len(images)}/{len(shots)}),请先补全图片"
            )

        total_ms = int((audio.audio_duration_sec or 0) * 1000)
        if total_ms <= 0:
            raise ValueError("音频时长未知,无法对齐")

        timings = align_shots(shots, subtitles, total_ms)
        if render_id in _cancelled:
            raise _Cancelled

        await _mark(render_id, stage="ffmpeg")
        video_url = await _compose(
            render_id,
            images,
            timings,
            subtitles,
            audio.audio_url,
            render.aspect_ratio,
        )

        duration_sec = sum(t["end_ms"] - t["start_ms"] for t in timings) / 1000.0
        await _mark(
            render_id,
            status="done",
            stage=None,
            video_url=video_url,
            duration_sec=duration_sec,
            error=None,
        )
    except _Cancelled:
        await _mark(render_id, status="cancelled", error="用户取消")
    except Exception as e:  # noqa: BLE001 - 后台任务兜底
        await _mark(render_id, status="error", error=f"{type(e).__name__}: {e}"[:500])


# ---------------------------------------------------------------- 对外入口

async def _out_dict(render) -> dict:
    d = video_render_repo.to_artifact_dict(render)
    d["has_active"] = render.status in ("pending", "generating")
    return d


async def start_render(*, conversation_id: str, project_id: str, allow_stale_storyboard: bool = False) -> dict:
    """为作品创建 pending 成片(替换旧成片),启动后台合成流水线。

    预检:配音音频已完成、分镜已激活、分镜图片齐全。缺失则即时报错给前端。
    """
    async with AsyncSessionLocal() as s:
        audio = await audio_track_repo.get_active_track(s, project_id)
        if not audio or audio.status != "done" or not audio.audio_url:
            raise ValueError("请先生成并完成配音音频")
        active_sb = await storyboard_repo.get_active_storyboard(s, project_id)
        if not active_sb:
            raise ValueError("请先生成分镜")

        # 执行前素材规划：当前分镜不完整时，不立即要求用户重做；先从历史版本
        # 中按“新 -> 旧”寻找镜头与图片都完整的版本，复用既有画面。
        versions = await storyboard_repo.list_storyboard_versions(s, project_id)
        candidates = [active_sb] + [sb for sb in reversed(versions) if sb.id != active_sb.id]
        selected = None
        selected_shots: list[dict] = []
        active_done = 0
        active_total = 0
        for candidate in candidates:
            shots = json.loads(candidate.shots_json or "[]")
            images = await image_repo.list_images_by_storyboard(
                s, candidate.id, statuses=["done"]
            )
            if candidate.id == active_sb.id:
                active_done, active_total = len(images), len(shots)
            if shots and len(images) >= len(shots):
                selected, selected_shots = candidate, shots
                break
        if selected is None:
            raise ValueError(
                f"没有找到图片完整的分镜版本（当前已有 {active_done}/{active_total}），请先补全图片"
            )

        reused_history = selected.id != active_sb.id
        storyboard_text = "".join(
            _norm(shot.get("narration", "")) for shot in selected_shots
        )
        audio_text = _norm(audio.script_text or "")
        compatibility = difflib.SequenceMatcher(
            None, storyboard_text, audio_text, autojunk=False
        ).ratio() if storyboard_text and audio_text else 0.0
        based_on_current_script = selected.script_version_id == audio.script_version_id
        if not based_on_current_script and compatibility < 0.45:
            raise ValueError(
                f"历史画面与当前口播差异过大（匹配度 {compatibility:.0%}），无法保证音画对应，请重新生成分镜"
            )
        if not based_on_current_script and compatibility < 0.80 and not allow_stale_storyboard:
            raise ValueError(
                f"历史画面与当前口播仅有 {compatibility:.0%} 匹配度。若接受复用旧画面，请明确说“复用旧画面直接合成”；否则请重新生成分镜"
            )
        if reused_history:
            # 让会话当前素材与本次成片引用保持一致，切换会话后也能恢复正确状态。
            selected = await storyboard_repo.activate_version(s, selected.id) or selected

        aspect = selected.aspect_ratio or "16:9"
        # 整片重新生成:物理删除旧成片,避免累积
        await video_render_repo.delete_renders_by_project(s, project_id)
        render = await video_render_repo.create_render(
            s,
            conversation_id=conversation_id,
            project_id=project_id,
            audio_track_id=audio.id,
            storyboard_version_id=selected.id,
            aspect_ratio=aspect,
            status="pending",
        )

    _cancelled.discard(render.id)
    await task_runner.submit("video_render", render_id=render.id)
    result = await _out_dict(render)
    result["planning_note"] = (
        f"当前分镜图片不完整，已复用图片完整的分镜第 {selected.version} 版（{len(selected_shots)} 镜，口播匹配度 {compatibility:.0%}），并按新配音时间轴重新对齐"
        if reused_history
        else f"已检查素材：当前分镜第 {selected.version} 版图片完整（{len(selected_shots)} 镜，口播匹配度 {compatibility:.0%}）"
    )
    return result


async def get_render_for_conversation(conversation_id: str, project_id: str) -> Optional[dict]:
    """取会话当前成片(最新一条),无则 None。"""
    async with AsyncSessionLocal() as s:
        render = await video_render_repo.get_active_render(s, project_id)
        if render is None or render.conversation_id != conversation_id:
            # 兜底:按会话取一条
            renders = await video_render_repo.list_renders_by_conversation(s, conversation_id)
            render = renders[0] if renders else None
        return await _out_dict(render) if render else None


async def cancel_render(conversation_id: str) -> dict:
    """取消会话当前进行中的成片合成。"""
    async with AsyncSessionLocal() as s:
        renders = await video_render_repo.list_renders_by_conversation(s, conversation_id)
        ids = [r.id for r in renders]
        for rid in ids:
            _cancelled.add(rid)
        for r in renders:
            if r.status in ("pending", "generating"):
                await video_render_repo.update_render(
                    s, r.id, status="cancelled", error="用户取消"
                )
    return {"cancelled": len(ids), "renders": ids}


async def regenerate(render_id: str) -> Optional[dict]:
    """整片重生成:复用原素材引用,重置为 pending 再跑。"""
    async with AsyncSessionLocal() as s:
        render = await video_render_repo.get_render(s, render_id)
        if render is None:
            return None
        await video_render_repo.update_render(
            s,
            render_id,
            status="pending",
            stage=None,
            video_url=None,
            duration_sec=None,
            error=None,
        )
    _cancelled.discard(render_id)
    await task_runner.submit("video_render", render_id=render_id)
    async with AsyncSessionLocal() as s:
        r = await video_render_repo.get_render(s, render_id)
        return await _out_dict(r) if r else None


# 注册为后台任务(供 task_runner 调度)
task_runner.register_task("video_render", run_render_task)
