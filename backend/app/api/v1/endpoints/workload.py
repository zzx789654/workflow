"""F12 — 工作量視圖"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.models.v3_models import TimeLog

router = APIRouter(prefix="/workload", tags=["workload"])


@router.get("")
async def get_workload(
    period: str = Query("week", pattern="^(week|month)$"),
    project_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC).date()
    if period == "week":
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=7)
    else:
        start = now.replace(day=1)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            end = now.replace(month=now.month + 1, day=1)

    # Project filter
    if project_id:
        proj_ids = [project_id]
    elif current_user.role.value == "admin":
        res = await db.execute(select(Project.id))
        proj_ids = [r[0] for r in res.all()]
    else:
        res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
        proj_ids = [r[0] for r in res.all()]

    # Task count per assignee within date range
    res = await db.execute(
        select(
            TaskAssignee.user_id,
            User.display_name,
            func.count(TaskAssignee.task_id).label("task_count"),
        )
        .join(Task, TaskAssignee.task_id == Task.id)
        .join(User, TaskAssignee.user_id == User.id)
        .where(
            and_(
                Task.project_id.in_(proj_ids),
                Task.status != "done",
                Task.due_date >= start.isoformat() if start else True,
                Task.due_date <= end.isoformat() if end else True,
            )
        )
        .group_by(TaskAssignee.user_id, User.display_name)
        .order_by(func.count(TaskAssignee.task_id).desc())
    )
    rows = res.all()

    # Estimated work hours (time_logs in period)
    hours_res = await db.execute(
        select(
            TimeLog.user_id,
            func.sum(TimeLog.minutes).label("logged_minutes"),
        )
        .join(Task, TimeLog.task_id == Task.id)
        .where(
            and_(
                Task.project_id.in_(proj_ids),
                TimeLog.started_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=UTC)
                if start
                else True,
            )
        )
        .group_by(TimeLog.user_id)
    )
    logged = {str(r.user_id): r.logged_minutes for r in hours_res.all()}

    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "members": [
            {
                "user_id": str(r.user_id),
                "display_name": r.display_name,
                "task_count": r.task_count,
                "logged_minutes": logged.get(str(r.user_id), 0),
                "logged_hours": round(logged.get(str(r.user_id), 0) / 60, 1),
                "overloaded": r.task_count > 10,
            }
            for r in rows
        ],
    }
