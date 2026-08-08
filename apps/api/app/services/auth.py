"""用户认证服务(Phase 5):密码哈希 + JWT 签发/校验。

JWT 无状态,前端存 localStorage,每次请求带 Authorization: Bearer <token>。
密码用 bcrypt 直接哈希(避开 passlib 与 bcrypt 5.x 的版本不兼容)。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, expires_minutes: Optional[int] = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    payload = {"sub": user_id, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


async def get_user_by_email(s: AsyncSession, email: str) -> Optional[User]:
    q = select(User).where(User.email == email)
    return (await s.execute(q)).scalar_one_or_none()


async def get_user(s: AsyncSession, user_id: str) -> Optional[User]:
    return await s.get(User, user_id)


async def create_user(
    s: AsyncSession, email: str, password: str, name: Optional[str] = None
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        name=name,
    )
    s.add(user)
    await s.commit()
    await s.refresh(user)
    return user
