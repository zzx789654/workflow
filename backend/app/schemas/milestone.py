import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.milestone import MilestoneStatus


class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    status: MilestoneStatus = MilestoneStatus.planned


class MilestoneUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    status: MilestoneStatus | None = None


class MilestoneOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    status: MilestoneStatus
    due_date: date | None
    created_at: datetime
    task_count: int = 0

    model_config = {"from_attributes": True}
