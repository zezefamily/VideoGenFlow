"""FastAPI 依赖:当前用户(Phase 5)。

从 Authorization: Bearer <token> 解析 JWT,加载 User。
所有需要登录的路由用 Depends(get_current_user);会话级数据用它做归属隔离。
SSE(EventSource 不能发自定义头)用 get_current_user_query 走 ?token= 查询参数。
"""

from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Conversation, User
from app.repositories import conversation_repo
from app.services import auth as auth_service

_bearer = HTTPBearer(auto_error=True)


async def _resolve_user(s: AsyncSession, token: Optional[str]) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证令牌")
    payload = auth_service.decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌缺少用户标识")
    user = await auth_service.get_user(s, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    return user


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    s: AsyncSession = Depends(get_session),
) -> User:
    return await _resolve_user(s, creds.credentials)


async def get_current_user_query(
    token: Optional[str] = Query(default=None, description="JWT(EventSource 用)"),
    s: AsyncSession = Depends(get_session),
) -> User:
    """SSE 流专用:从 ?token= 取 JWT。"""
    return await _resolve_user(s, token)


async def get_owned_conversation(
    conv_id: str,
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
) -> Conversation:
    """加载会话并校验归属。不存在或不属于当前用户 -> 404(不泄露存在性)。"""
    conv = await conversation_repo.get_conversation(s, conv_id)
    if conv is None or conv.archived_at is not None or conv.owner_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return conv
