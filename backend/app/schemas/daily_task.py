import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.daily_task import DailyTaskStatus


class DailyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    status: DailyTaskStatus = DailyTaskStatus.pending
    progress: int = Field(0, ge=0, le=100)
    date: date
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notify_at: datetime | None = None
    work_minutes: int = Field(0, ge=0)
    labels: list[str] = []


class DailyTaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    status: DailyTaskStatus | None = None
    progress: int | None = Field(None, ge=0, le=100)
    date: date | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notify_at: datetime | None = None
    work_minutes: int | None = Field(None, ge=0)
    labels: list[str] | None = None


class DailyTaskOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: DailyTaskStatus
    progress: int
    date: date
    started_at: datetime | None
    ended_at: datetime | None
    notify_at: datetime | None
    work_minutes: int
    created_at: datetime
    updated_at: datetime
    labels: list[str] = []

    model_config = {"from_attributes": True}
