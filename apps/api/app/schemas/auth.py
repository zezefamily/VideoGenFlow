"""认证相关 schema(Phase 5)。

email 用正则校验(而非 pydantic.EmailStr),允许开发用的 .local 等保留域名。
"""

from typing import Annotated, Optional

from pydantic import BaseModel, Field

# 简单 email 正则:够用且不拒绝 .local/.test 等保留域名
EmailField = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class RegisterIn(BaseModel):
    email: EmailField
    password: str = Field(min_length=6, max_length=128)
    name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailField
    password: str


class AuthOut(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None

    model_config = {"from_attributes": True}


AuthOut.model_rebuild()
