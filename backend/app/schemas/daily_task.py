import datetime as _dt
import uuid

from pydantic import BaseModel, Field

from app.models.daily_task import DailyTaskStatus


class LinkedTaskInfo(BaseModel):
    id: uuid.UUID
    title: str
    project_id: uuid.UUID
    project_name: str

    model_config = {"from_attributes": True}


class DailyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    status: DailyTaskStatus = DailyTaskStatus.pending
    progress: int = Field(0, ge=0, le=100)
    date: _dt.date
    started_at: _dt.datetime | None = None
    ended_at: _dt.datetime | None = None
    notify_at: _dt.datetime | None = None
    work_minutes: int = Field(0, ge=0)
    labels: list[str] = []
    linked_task_id: uuid.UUID | None = None


class DailyTaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    status: DailyTaskStatus | None = None
    progress: int | None = Field(None, ge=0, le=100)
    date: _dt.date | None = None
    started_at: _dt.datetime | None = None
    ended_at: _dt.datetime | None = None
    notify_at: _dt.datetime | None = None
    work_minutes: int | None = Field(None, ge=0)
    labels: list[str] | None = None
    linked_task_id: uuid.UUID | None = None


class DailyTaskOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: DailyTaskStatus
    progress: int
    date: _dt.date
    started_at: _dt.datetime | None
    ended_at: _dt.datetime | None
    notify_at: _dt.datetime | None
    work_minutes: int
    created_at: _dt.datetime
    updated_at: _dt.datetime
    labels: list[str] = []
    linked_task_id: uuid.UUID | None = None
    linked_task: LinkedTaskInfo | None = None

    model_config = {"from_attributes": True}
