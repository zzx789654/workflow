from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskLabel
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarEvent(BaseModel):
    id: str
    title: str
    date: date
    type: str  # "task" | "daily"
    status: str
    priority: str | None = None
    progress: int = 0
    project_id: str | None = None
    project_name: str | None = None
    labels: list[str] = []


@router.get("/", response_model=list[CalendarEvent])
async def get_calendar_events(
    year: int = Query(...),
    month: int = Query(...),
    label: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    events: list[CalendarEvent] = []

    # Project tasks (only from projects user is member of)
    subq = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
    task_q = (
        select(Task)
        .where(
            Task.project_id.in_(subq),
            Task.due_date >= start,
            Task.due_date <= end,
        )
        .order_by(Task.due_date)
    )
    task_result = await db.execute(task_q)
    for task in task_result.scalars().all():
        if task.due_date:
            events.append(
                CalendarEvent(
                    id=str(task.id),
                    title=task.title,
                    date=task.due_date,
                    type="task",
                    status=task.status.value,
                    priority=task.priority.value,
                    progress=task.progress,
                    project_id=str(task.project_id),
                    labels=[],
                )
            )

    # Daily tasks
    daily_q = (
        select(DailyTask)
        .options(selectinload(DailyTask.labels))
        .where(
            DailyTask.user_id == current_user.id,
            DailyTask.date >= start,
            DailyTask.date <= end,
        )
    )
    if label:
        daily_q = daily_q.join(DailyTaskLabel).where(DailyTaskLabel.label == label)
    daily_result = await db.execute(daily_q)
    for dt in daily_result.scalars().unique().all():
        lbls = [lb.label for lb in dt.labels]
        if label and label not in lbls:
            continue
        events.append(
            CalendarEvent(
                id=str(dt.id),
                title=dt.title,
                date=dt.date,
                type="daily",
                status=dt.status.value,
                progress=dt.progress,
                labels=lbls,
            )
        )

    return sorted(events, key=lambda e: e.date)
