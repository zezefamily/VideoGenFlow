"""认证路由(Phase 5):注册/登录/当前用户。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import AuthOut, LoginIn, RegisterIn, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
async def register(payload: RegisterIn, s: AsyncSession = Depends(get_session)):
    existing = await auth_service.get_user_by_email(s, payload.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
    user = await auth_service.create_user(s, payload.email, payload.password, payload.name)
    token = auth_service.create_access_token(user.id)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthOut)
async def login(payload: LoginIn, s: AsyncSession = Depends(get_session)):
    user = await auth_service.get_user_by_email(s, payload.email)
    if user is None or not auth_service.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已停用")
    token = auth_service.create_access_token(user.id)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)):
    return current


@router.delete("/account")
async def delete_account(
    current: User = Depends(get_current_user),
    s: AsyncSession = Depends(get_session),
):
    """注销账户:删除当前用户全部会话(级联子数据+图片文件)及用户记录本身。

    Phase 5 数据删除(合规)。
    """
    from app.repositories import conversation_repo
    from app.services import storage as storage_service

    convs = await conversation_repo.list_conversations(s, current.id, include_archived=True)
    deleted_files = 0
    for c in convs:
        local_paths = await conversation_repo.hard_delete_conversation(s, c.id)
        for p in local_paths:
            await storage_service.delete_by_web_path(p)
            deleted_files += 1
    await s.delete(current)
    await s.commit()
    return {"ok": True, "deleted_conversations": len(convs), "deleted_files": deleted_files}
