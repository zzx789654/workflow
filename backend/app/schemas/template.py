import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TemplateTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    priority: str = "medium"
    day_offset_start: int = 0
    day_offset_end: int | None = None
    position: int = 0
    depends_on_position: int | None = None


class TemplateTaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    priority: str
    day_offset_start: int
    day_offset_end: int | None
    position: int
    depends_on_position: int | None

    model_config = {"from_attributes": True}


class ProjectTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    tasks: list[TemplateTaskCreate] = []


class ProjectTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class ProjectTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    color: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    tasks: list[TemplateTaskOut] = []

    model_config = {"from_attributes": True}


class ApplyTemplateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=200)
    project_description: str | None = None
    start_date: str | None = None   # ISO date string, used as day-offset base
    end_date: str | None = None     # project deadline (sets project.end_date)
