import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    # username 是登入鍵；只允許英數與底線，全域唯一（後端再查重）
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_]+$")
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    email: EmailStr | None = None  # 選填，純聯絡資訊

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: str | None = None
    auto_archive_days: int | None = Field(None, ge=0, le=3650)
    email: EmailStr | None = None  # 僅 local 帳號可改（後端守門）


class AdminUserUpdate(BaseModel):
    """admin 專用：維護使用者的組織歸屬與職位。一般使用者不可自改（防越權竄改歸屬）。"""

    org_unit_id: uuid.UUID | None = None
    position: str | None = Field(None, max_length=100)
    # 顯式區分「未提供」與「清空」：set_unit/set_position 為 True 時才套用對應欄位
    set_org_unit: bool = False
    set_position: bool = False


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    auth_source: str
    display_name: str
    role: UserRole
    is_active: bool
    avatar_url: str | None
    org_unit_id: uuid.UUID | None
    position: str | None
    auto_archive_days: int
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str
