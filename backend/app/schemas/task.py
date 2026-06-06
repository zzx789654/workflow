import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

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
    milestone_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus
    priority: TaskPriority
    position: int
    due_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_end_date: date | None = None
    progress: int = 0
    subtask_count: int = 0
    subtask_done_count: int = 0
    attachment_count: int = 0
    recurrence_rule: str | None = None
    recurrence_parent_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    assignees: list[UserOut] = []
    comments: list[TaskCommentOut] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _resolve_assignees(cls, data: Any) -> Any:
        """Resolve TaskAssignee ORM objects → UserOut-compatible dicts."""
        if not hasattr(data, "__dict__"):
            return data
        # Build a plain dict from ORM object
        result: dict = {}
        for col in [
            "id",
            "project_id",
            "milestone_id",
            "parent_task_id",
            "title",
            "description",
            "status",
            "priority",
            "position",
            "due_date",
            "start_date",
            "end_date",
            "actual_end_date",
            "progress",
            "subtask_count",
            "subtask_done_count",
            "attachment_count",
            "recurrence_rule",
            "recurrence_parent_id",
            "created_at",
            "updated_at",
        ]:
            result[col] = getattr(data, col, None)
        # Expand TaskAssignee → User
        result["assignees"] = [getattr(a, "user", a) for a in getattr(data, "assignees", [])]
        result["comments"] = list(getattr(data, "comments", []))
        return result


class KanbanMoveRequest(BaseModel):
    status: TaskStatus
    position: int
