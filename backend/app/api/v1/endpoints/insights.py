"""F16 — 個人效率分析 Personal Insights"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.models.v3_models import TimeLog

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
async def get_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)

    # Tasks completed in last 30 days (by day)
    day_expr = func.date_trunc("day", Task.updated_at)
    done_res = await db.execute(
        select(
            day_expr.label("day"),
            func.count().label("count"),
        )
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(
            and_(
                TaskAssignee.user_id == current_user.id,
                Task.status == "done",
                Task.updated_at >= thirty_days_ago,
            )
        )
        .group_by(day_expr)
        .order_by(day_expr)
    )
    done_by_day = [{"date": str(r.day.date()), "count": r.count} for r in done_res.all()]

    # Average time from creation to done (minutes)
    avg_res = await db.execute(
        select(func.avg(func.extract("epoch", Task.updated_at - Task.created_at) / 60).label("avg_minutes"))
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(
            and_(
                TaskAssignee.user_id == current_user.id,
                Task.status == "done",
                Task.updated_at >= thirty_days_ago,
            )
        )
    )
    avg_minutes_row = avg_res.scalar()
    avg_completion_hours = round(float(avg_minutes_row or 0) / 60, 1)

    # Total logged hours by day-of-week (to find most productive hours)
    hour_res = await db.execute(
        select(
            func.extract("dow", TimeLog.started_at).label("dow"),
            func.sum(TimeLog.minutes).label("total_minutes"),
        )
        .where(
            and_(
                TimeLog.user_id == current_user.id,
                TimeLog.started_at >= thirty_days_ago,
                TimeLog.ended_at != None,  # noqa: E711
            )
        )
        .group_by(func.extract("dow", TimeLog.started_at))
        .order_by(func.extract("dow", TimeLog.started_at))
    )
    DOW_LABELS = ["日", "一", "二", "三", "四", "五", "六"]
    by_dow = [{"dow": DOW_LABELS[int(r.dow)], "total_minutes": r.total_minutes} for r in hour_res.all()]

    # Total tasks summary
    total_res = await db.execute(
        select(Task.status, func.count().label("count"))
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(TaskAssignee.user_id == current_user.id)
        .group_by(Task.status)
    )
    status_counts = {r.status: r.count for r in total_res.all()}

    return {
        "done_trend": done_by_day,
        "avg_completion_hours": avg_completion_hours,
        "productivity_by_dow": by_dow,
        "task_summary": {
            "todo": status_counts.get("todo", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "review": status_counts.get("review", 0),
            "done": status_counts.get("done", 0),
        },
    }
