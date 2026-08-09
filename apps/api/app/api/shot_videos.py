from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_owned_conversation
from app.models import Conversation
from app.schemas.shot_video import ShotVideoGenerateIn, ShotVideoListOut, ShotVideoPlanIn
from app.services import shot_video_service

router = APIRouter(prefix="/api/conversations", tags=["shot-videos"])


@router.post("/{conv_id}/shot-videos/plan")
async def plan(body: ShotVideoPlanIn, conv: Conversation = Depends(get_owned_conversation)):
    try: return await shot_video_service.plan(conv.id, body.strategy, body.shot_indices)
    except ValueError as exc: raise HTTPException(400, str(exc))


@router.post("/{conv_id}/shot-videos/generate", response_model=ShotVideoListOut)
async def generate(body: ShotVideoGenerateIn, conv: Conversation = Depends(get_owned_conversation)):
    try: return await shot_video_service.start(conv.id, body.strategy, body.shot_indices, body.confirmed)
    except ValueError as exc: raise HTTPException(400, str(exc))


@router.get("/{conv_id}/shot-videos", response_model=ShotVideoListOut)
async def get_assets(conv: Conversation = Depends(get_owned_conversation)):
    return await shot_video_service.get_for_conversation(conv.id)
