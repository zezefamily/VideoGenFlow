"""TTS + 字幕路由(成片管线):音色列表/批量配音/音轨查询/取消/整轨重生成。

音色与情绪 DubbingX;配音+字幕走整段 TTS->TOS->火山 ATA 打轴。
按当前用户归属隔离(同图片路由)。
"""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user, get_owned_conversation
from app.models import Conversation, User
from app.repositories import (
    audio_track_repo,
    conversation_repo,
    project_repo,
    script_repo,
)
from app.schemas.audio import (
    AudioTrackOut,
    DebugTTSRequest,
    DebugTTSResponse,
    EmotionListOut,
    EmotionOut,
    TTSGenerateRequest,
    VoiceListOut,
    VoiceOut,
)
from app.services import dubbingx_client, tts_service
from app.services.dubbingx_client import DubbingXError

router = APIRouter(prefix="/api/conversations", tags=["tts"])
voices_router = APIRouter(prefix="/api/tts", tags=["tts"])
regen_router = APIRouter(prefix="/api/audio-tracks", tags=["tts"])


# ---- 音色 / 情绪(DubbingX,前端选择用)----

@voices_router.get("/voices", response_model=VoiceListOut)
async def list_voices(
    current: User = Depends(get_current_user),
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    grade: Optional[str] = None,
    gender: Optional[int] = None,
    age_group: Optional[str] = None,
    keyword: Optional[str] = None,
    is_my_model: Optional[bool] = None,
):
    """获取 DubbingX 音色列表(可筛选/搜索)。grade: premium/ordinary/custom;gender: 0女/1男;is_my_model: 仅自定义音色。"""
    try:
        data = await dubbingx_client.list_voices(
            page_index=page_index,
            page_size=page_size,
            grade=grade,
            gender=gender,
            age_group=age_group,
            keyword=keyword,
            is_my_model=is_my_model,
        )
    except DubbingXError as e:
        raise HTTPException(status_code=503, detail=str(e))
    items = data.get("list", []) or []
    return VoiceListOut(
        total=data.get("total", 0),
        list=[VoiceOut(**i) for i in items],
    )


@voices_router.get("/voices/{voice_id}/emotions", response_model=EmotionListOut)
async def list_emotions(voice_id: str, current: User = Depends(get_current_user)):
    """获取某音色支持的情绪列表。"""
    try:
        raw = await dubbingx_client.list_emotions(voice_id)
    except DubbingXError as e:
        raise HTTPException(status_code=503, detail=str(e))
    out = []
    for item in raw:
        type_obj = item.get("type") or {}
        out.append(
            EmotionOut(
                type=type_obj.get("zh", "") if isinstance(type_obj, dict) else str(type_obj),
                auras=[a.get("zh", "") for a in (item.get("aura") or [])],
            )
        )
    return EmotionListOut(list=out)


# ---- 调试台(临时,不落库)----

@voices_router.post("/analyze-emotion")
async def analyze_emotion_endpoint(body: dict, current: User = Depends(get_current_user)):
    """分析文本情绪,返回全情绪格式字符串(类型-风格-档位)。调试用。"""
    text = (body or {}).get("text", "")
    if not text.strip():
        raise HTTPException(400, "text 为空")
    try:
        async with httpx.AsyncClient() as c:
            emo = await dubbingx_client.analyze_emotion(c, text)
    except DubbingXError as e:
        raise HTTPException(503, str(e))
    return {"emotion": emo}


@voices_router.post("/debug-synthesize", response_model=DebugTTSResponse)
async def debug_synthesize_endpoint(
    body: DebugTTSRequest, current: User = Depends(get_current_user)
):
    """调试用:不落库,直接合成(+可选 autoPause 停顿 +可选 ATA 打轴),返回音频URL+字幕。"""
    try:
        result = await tts_service.debug_synthesize(
            text=body.text,
            voice_id=body.voice_id,
            emotion=body.emotion,
            language=body.language,
            audio_speed=body.audio_speed,
            audio_pitch=body.audio_pitch,
            audio_volume=body.audio_volume,
            file_format=body.file_format,
            auto_pause=body.auto_pause,
            align=body.align,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 - 调试端点兜底
        raise HTTPException(502, f"{type(e).__name__}: {e}")
    return result


# ---- 配音 + 字幕(按会话/作品)----

@router.post("/{conv_id}/tts/generate", response_model=AudioTrackOut)
async def generate_tts(
    body: TTSGenerateRequest,
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """整段脚本一次性配音 + ATA 字幕打轴(按当前激活脚本)。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        raise HTTPException(status_code=400, detail="当前没有作品,请先创作脚本")
    script = await script_repo.get_active_script(s, project.id)
    if script is None or not (script.content or "").strip():
        raise HTTPException(status_code=400, detail="当前没有可用脚本,请先创作脚本")
    try:
        artifact = await tts_service.start_generation(
            conversation_id=conv.id,
            project_id=project.id,
            script_version_id=script.id,
            script_text=script.content,
            provider=body.provider,
            voice_id=body.voice_id,
            emotion=body.emotion,
            language=body.language,
            audio_speed=body.audio_speed,
            audio_pitch=body.audio_pitch,
            audio_volume=body.audio_volume,
            file_format=body.file_format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AudioTrackOut(**artifact, has_active=True)


@router.get("/{conv_id}/audio-track", response_model=Optional[AudioTrackOut])
async def get_audio_track(
    conv: Conversation = Depends(get_owned_conversation),
    s: AsyncSession = Depends(get_session),
):
    """取会话当前音轨(前端轮询用);无音轨返回 null。"""
    project = await project_repo.get_conversation_project(s, conv.id)
    if project is None:
        return None
    track = await audio_track_repo.get_active_track(s, project.id)
    if track is None:
        return None
    artifact = audio_track_repo.to_artifact_dict(track)
    has_active = track.status in ("pending", "generating")
    return AudioTrackOut(**artifact, has_active=has_active)


@router.post("/{conv_id}/tts/cancel")
async def cancel_tts(conv: Conversation = Depends(get_owned_conversation)):
    """取消会话当前进行中的音轨生成。"""
    return await tts_service.cancel_generation(conv.id)


# ---- 整轨重生成(单独挂在 /api/audio-tracks 下)----

@regen_router.post("/{track_id}/regenerate", response_model=AudioTrackOut)
async def regenerate_track(
    track_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    track = await audio_track_repo.get_track(s, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="音轨不存在")
    # 校验归属:音轨 -> 会话 -> owner
    conv = await conversation_repo.get_conversation(s, track.conversation_id)
    if conv is None or conv.owner_id != current.id:
        raise HTTPException(status_code=404, detail="音轨不存在")
    result = await tts_service.regenerate(track_id)
    if result is None:
        raise HTTPException(status_code=404, detail="音轨不存在")
    return AudioTrackOut(**result, has_active=True)
