import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.project import ProjectRole
from app.schemas.user import UserOut


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_archived: bool | None = None


class ProjectMemberOut(BaseModel):
    id: uuid.UUID
    user: UserOut
    role: ProjectRole
    joined_at: datetime

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    color: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: ProjectRole = ProjectRole.member
