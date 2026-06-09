"""F10 — 重複排程任務（RRULE-lite: daily/weekly/monthly）"""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/recurrence", tags=["recurring"])


async def _check_write(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role.in_(["owner", "manager", "member"]),
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Write access required")


class RecurrenceSet(BaseModel):
    rule: str = Field(..., pattern="^(daily|weekly|monthly)$", description="daily | weekly | monthly")


@router.put("")
async def set_recurrence(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: RecurrenceSet,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_write(project_id, current_user, db)
    task = await db.get(Task, task_id)
    if not task or str(task.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Task not found")
    task.recurrence_rule = body.rule
    await db.commit()
    return {"task_id": str(task_id), "recurrence_rule": body.rule}


@router.delete("")
async def remove_recurrence(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_write(project_id, current_user, db)
    task = await db.get(Task, task_id)
    if not task or str(task.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Task not found")
    task.recurrence_rule = None
    await db.commit()
    return {"task_id": str(task_id), "recurrence_rule": None}


@router.post("/spawn")
async def spawn_next(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually spawn the next recurrence instance (also called by cron job)."""
    await _check_write(project_id, current_user, db)
    task = await db.get(Task, task_id)
    if not task or str(task.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.recurrence_rule:
        raise HTTPException(status_code=400, detail="Task has no recurrence rule")

    # due_date 是 Date 欄位；可能為 date 物件或（歷史資料）ISO 字串，統一轉成 date。
    if isinstance(task.due_date, str):  # pragma: no cover - 歷史資料相容（現行 due_date 一律 date 物件）
        base_due = date.fromisoformat(task.due_date)
    elif isinstance(task.due_date, date):
        base_due = task.due_date
    else:
        base_due = date.today()
    if task.recurrence_rule == "daily":
        next_due = base_due + timedelta(days=1)
    elif task.recurrence_rule == "weekly":
        next_due = base_due + timedelta(weeks=1)
    else:
        m = base_due.month + 1 if base_due.month < 12 else 1
        y = base_due.year if base_due.month < 12 else base_due.year + 1
        next_due = base_due.replace(year=y, month=m)

    new_task = Task(
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status="todo",
        due_date=next_due,
        recurrence_rule=task.recurrence_rule,
        recurrence_parent_id=task.id,
        position=0,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return {"spawned_task_id": str(new_task.id), "due_date": next_due.isoformat()}
