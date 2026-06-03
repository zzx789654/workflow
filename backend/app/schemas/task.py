import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskStatus
from app.schemas.user import UserOut


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    milestone_id: uuid.UUID | None = None
    due_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    assignee_ids: list[uuid.UUID] = []
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    milestone_id: uuid.UUID | None = None
    due_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_end_date: date | None = None
    progress: int | None = Field(None, ge=0, le=100)
    position: int | None = None
    assignee_ids: list[uuid.UUID] | None = None
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class TaskCommentOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author: UserOut
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    milestone_id: uuid.UUID | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    position: int
    due_date: date | None
    start_date: date | None = None
    end_date: date | None = None
    actual_end_date: date | None = None
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    assignees: list[UserOut] = []
    comments: list[TaskCommentOut] = []
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None

    model_config = {"from_attributes": True}


class KanbanMoveRequest(BaseModel):
    status: TaskStatus
    position: int
