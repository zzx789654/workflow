import json
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskAssignee, TaskStatus
from app.models.user import User
from app.models.v3_p2_models import WeeklyReport

router = APIRouter(prefix="/reports", tags=["reports"])


def _week_bounds(ref: date) -> tuple[date, date]:
    """Return (week_start Monday, week_end Sunday) for the week containing ref."""
    start = ref - timedelta(days=ref.weekday())
    end = start + timedelta(days=6)
    return start, end


class WeeklyReportCreate(BaseModel):
    next_week_plan: str = ""


@router.get("/weekly")
async def get_weekly_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    week_start, week_end = _week_bounds(today)
    uid = current_user.id

    # Assigned task ids subquery
    assigned_q = select(TaskAssignee.task_id).where(TaskAssignee.user_id == uid)

    # Completed tasks this week
    completed_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_q),
                Task.status == TaskStatus.done,
                func.date(Task.updated_at) >= week_start,
                func.date(Task.updated_at) <= week_end,
            )
        )
    )
    completed = completed_result.scalar() or 0

    # Overdue tasks (not done, past due)
    overdue_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_q),
                Task.status != TaskStatus.done,
                Task.due_date < today,
            )
        )
    )
    overdue = overdue_result.scalar() or 0

    # Created this week
    created_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_q),
                func.date(Task.created_at) >= week_start,
                func.date(Task.created_at) <= week_end,
            )
        )
    )
    created = created_result.scalar() or 0

    # Daily completed counts this week
    daily_tasks = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        r = await db.execute(
            select(func.count()).where(
                and_(
                    Task.id.in_(assigned_q),
                    Task.status == TaskStatus.done,
                    func.date(Task.updated_at) == d,
                )
            )
        )
        daily_tasks.append({"date": d.isoformat(), "completed": r.scalar() or 0})

    # Saved report content
    report_result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.user_id == uid, WeeklyReport.week_start == week_start)
        .order_by(WeeklyReport.created_at.desc())
        .limit(1)
    )
    saved = report_result.scalar_one_or_none()
    next_week_plan = ""
    if saved and saved.content:
        try:
            data = json.loads(saved.content)
            next_week_plan = data.get("next_week_plan", "")
        except Exception:
            next_week_plan = saved.content

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "completed_tasks": completed,
        "overdue_tasks": overdue,
        "created_tasks": created,
        "daily_tasks": daily_tasks,
        "next_week_plan": next_week_plan,
    }


@router.post("/weekly", status_code=201)
async def save_weekly_report(
    body: WeeklyReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    week_start, week_end = _week_bounds(today)
    content = json.dumps({"next_week_plan": body.next_week_plan})

    # Upsert: delete old and insert new
    old = await db.execute(
        select(WeeklyReport).where(WeeklyReport.user_id == current_user.id, WeeklyReport.week_start == week_start)
    )
    for r in old.scalars().all():
        await db.delete(r)

    report = WeeklyReport(
        id=uuid.uuid4(),
        user_id=current_user.id,
        week_start=week_start,
        week_end=week_end,
        content=content,
        created_at=datetime.now(UTC),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "next_week_plan": body.next_week_plan,
        "created_at": report.created_at.isoformat(),
    }
