from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskAssignee, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    today = date.today()

    # 使用者所在專案 IDs
    if current_user.role.value == "admin":
        proj_result = await db.execute(select(Project.id).where(Project.is_archived == False))
    else:
        proj_result = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == uid))
    project_ids = [r[0] for r in proj_result.all()]

    # 指派給我的任務子查詢
    assigned_task_ids_q = select(TaskAssignee.task_id).where(TaskAssignee.user_id == uid)

    # KPI 1：今日待辦（assigned + not done + due_date <= today 或無 due_date）
    todo_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status != TaskStatus.done,
                Task.project_id.in_(project_ids),
            )
        )
    )
    todo_count = todo_result.scalar() or 0

    # KPI 2：已延遲（due_date < today + not done）
    overdue_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status != TaskStatus.done,
                Task.due_date < today,
                Task.project_id.in_(project_ids),
            )
        )
    )
    overdue_count = overdue_result.scalar() or 0

    # KPI 3：本週完成（done + updated_at in 7 days）
    week_start = today - timedelta(days=6)
    completed_result = await db.execute(
        select(func.count()).where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status == TaskStatus.done,
                Task.updated_at >= week_start,
                Task.project_id.in_(project_ids),
            )
        )
    )
    completed_count = completed_result.scalar() or 0

    # 趨勢：過去 7 天每天完成數（任務 + 日常作業合計）
    trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        # 任務完成
        t_result = await db.execute(
            select(func.count()).where(
                and_(
                    Task.id.in_(assigned_task_ids_q),
                    Task.status == TaskStatus.done,
                    func.date(Task.updated_at) == d,
                    Task.project_id.in_(project_ids),
                )
            )
        )
        t_count = t_result.scalar() or 0
        # 日常作業完成
        dt_result = await db.execute(
            select(func.count()).where(
                and_(
                    DailyTask.user_id == uid,
                    DailyTask.status == DailyTaskStatus.done,
                    DailyTask.date == d,
                )
            )
        )
        dt_count = dt_result.scalar() or 0
        trend.append({"date": d.isoformat(), "count": t_count + dt_count})

    # 需我處理：指派給我、未完成、按 due_date 升冪，取前 10
    urgent_result = await db.execute(
        select(Task)
        .where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status != TaskStatus.done,
                Task.project_id.in_(project_ids),
            )
        )
        .order_by(Task.due_date.asc().nulls_last(), Task.priority.desc())
        .limit(10)
    )
    urgent_tasks = urgent_result.scalars().all()

    return {
        "kpi": {
            "todo": todo_count,
            "overdue": overdue_count,
            "completed_this_week": completed_count,
        },
        "trend": trend,
        "action_required": [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "project_id": str(t.project_id),
            }
            for t in urgent_tasks
        ],
    }
