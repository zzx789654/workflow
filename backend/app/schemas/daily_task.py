import uuid
import datetime as _dt
from typing import Optional

from pydantic import BaseModel, Field

from app.models.daily_task import DailyTaskStatus


class DailyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: DailyTaskStatus = DailyTaskStatus.pending
    progress: int = Field(0, ge=0, le=100)
    date: _dt.date
    started_at: Optional[_dt.datetime] = None
    ended_at: Optional[_dt.datetime] = None
    notify_at: Optional[_dt.datetime] = None
    work_minutes: int = Field(0, ge=0)
    labels: list[str] = []


class DailyTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[DailyTaskStatus] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    date: Optional[_dt.date] = None
    started_at: Optional[_dt.datetime] = None
    ended_at: Optional[_dt.datetime] = None
    notify_at: Optional[_dt.datetime] = None
    work_minutes: Optional[int] = Field(None, ge=0)
    labels: Optional[list[str]] = None


class DailyTaskOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str]
    status: DailyTaskStatus
    progress: int
    date: _dt.date
    started_at: Optional[_dt.datetime]
    ended_at: Optional[_dt.datetime]
    notify_at: Optional[_dt.datetime]
    work_minutes: int
    created_at: _dt.datetime
    updated_at: _dt.datetime
    labels: list[str] = []

    model_config = {"from_attributes": True}
