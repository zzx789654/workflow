import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.project import ProjectRole
from app.schemas.user import UserOut


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    start_date: date | None = None
    end_date: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_archived: bool | None = None
    recurrence_rule: str | None = None
    start_date: date | None = None
    end_date: date | None = None


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
    recurrence_rule: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class ProjectOverviewItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    color: str
    is_archived: bool
    start_date: date | None = None
    end_date: date | None = None
    member_count: int = 0
    task_total: int = 0
    task_done: int = 0
    my_role: str | None = None

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: ProjectRole = ProjectRole.member
