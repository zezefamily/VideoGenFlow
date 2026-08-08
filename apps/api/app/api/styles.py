"""画风库路由:返回可选画风列表(供前端生图时选择)。"""

from fastapi import APIRouter

from app.prompts import STORYBOARD_STYLES
from app.schemas.storyboard import StyleOut

router = APIRouter(prefix="/api", tags=["styles"])


@router.get("/styles", response_model=list[StyleOut])
async def list_styles():
    """返回全部可选画风(名 + 中文描述,去掉末尾 AI 关键词部分供前端展示)。"""
    result = []
    for name, desc in STORYBOARD_STYLES.items():
        short = desc.split("AI提示词关键词")[0].rstrip("。.，, ") or desc
        result.append(StyleOut(name=name, description=short))
    return result
