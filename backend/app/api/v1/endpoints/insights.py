from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskAssignee, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/users/me", tags=["insights"])


@router.get("/insights")
async def get_user_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    now = datetime.now(UTC)
    since_30d = now - timedelta(days=30)

    assigned_q = select(TaskAssignee.task_id).where(TaskAssignee.user_id == uid)

    # Completed in last 30 days
    completed_r = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_q),
                Task.status == TaskStatus.done,
                Task.updated_at >= since_30d,
            )
        )
    )
    completed_30d = completed_r.scalar() or 0

    # Avg completion days (from created_at to updated_at for done tasks)
    avg_r = await db.execute(
        select(func.avg(func.extract("epoch", Task.updated_at - Task.created_at) / 86400)).where(
            and_(
                Task.id.in_(assigned_q),
                Task.status == TaskStatus.done,
                Task.updated_at >= since_30d,
            )
        )
    )
    avg_val = avg_r.scalar()
    avg_completion_days = round(float(avg_val), 2) if avg_val is not None else 0.0

    # Top hour of day (hour when most tasks are completed)
    hour_r = await db.execute(
        select(extract("hour", Task.updated_at).label("hr"), func.count().label("cnt"))
        .where(
            and_(
                Task.id.in_(assigned_q),
                Task.status == TaskStatus.done,
                Task.updated_at >= since_30d,
            )
        )
        .group_by("hr")
        .order_by(func.count().desc())
        .limit(1)
    )
    hour_row = hour_r.first()
    top_hour = int(hour_row[0]) if hour_row else 9

    # Daily completed counts for last 30 days
    daily_counts = []
    for i in range(30):
        day = (now - timedelta(days=29 - i)).date()
        r = await db.execute(
            select(func.count()).where(
                and_(
                    Task.id.in_(assigned_q),
                    Task.status == TaskStatus.done,
                    func.date(Task.updated_at) == day,
                )
            )
        )
        daily_counts.append({"date": day.isoformat(), "count": r.scalar() or 0})

    return {
        "completed_30d": completed_30d,
        "avg_completion_days": avg_completion_days,
        "top_hour": top_hour,
        "daily_counts": daily_counts,
    }
