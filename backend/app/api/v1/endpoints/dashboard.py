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

    # 今日到期：assigned + not done + due_date = today
    today_result = await db.execute(
        select(Task)
        .where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status != TaskStatus.done,
                Task.due_date == today,
                Task.project_id.in_(project_ids),
            )
        )
        .order_by(Task.priority.desc())
        .limit(20)
    )
    today_tasks = today_result.scalars().all()

    # 需我處理：assigned + not done，按 due_date 升冪，取前 15
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
        .limit(15)
    )
    urgent_tasks = urgent_result.scalars().all()

    # 即將到期（7 天內，未完成，assigned 給我）
    upcoming_result = await db.execute(
        select(Task)
        .where(
            and_(
                Task.id.in_(assigned_task_ids_q),
                Task.status != TaskStatus.done,
                Task.due_date > today,
                Task.due_date <= today + timedelta(days=7),
                Task.project_id.in_(project_ids),
            )
        )
        .order_by(Task.due_date.asc())
        .limit(15)
    )
    upcoming_tasks = upcoming_result.scalars().all()

    # 專案截止日預警（14 天內即將到達 end_date，未封存）
    deadline_result = await db.execute(
        select(Project)
        .where(
            and_(
                Project.id.in_(project_ids),
                Project.is_archived == False,
                Project.end_date.isnot(None),
                Project.end_date <= today + timedelta(days=14),
            )
        )
        .order_by(Project.end_date.asc())
        .limit(10)
    )
    deadline_projects = deadline_result.scalars().all()

    # 建立 project_id → name 對照表（供 _task_dict 使用）
    all_task_pids = {t.project_id for t in list(today_tasks) + list(urgent_tasks) + list(upcoming_tasks)}
    proj_name_result = await db.execute(select(Project.id, Project.name).where(Project.id.in_(all_task_pids)))
    project_name_map: dict = {str(r[0]): r[1] for r in proj_name_result.all()}

    # 各專案完成率
    async def _project_progress(pid):
        total_r = await db.execute(select(func.count()).where(Task.project_id == pid))
        done_r = await db.execute(select(func.count()).where(Task.project_id == pid, Task.status == TaskStatus.done))
        total = total_r.scalar() or 0
        done = done_r.scalar() or 0
        return total, done

    deadline_out = []
    for p in deadline_projects:
        total, done = await _project_progress(p.id)
        diff = (p.end_date - today).days
        deadline_out.append(
            {
                "id": str(p.id),
                "name": p.name,
                "color": p.color,
                "end_date": p.end_date.isoformat(),
                "days_left": diff,
                "task_total": total,
                "task_done": done,
            }
        )

    # 待辦與進行中日常任務（所有日期）
    daily_today_result = await db.execute(
        select(DailyTask)
        .where(
            and_(
                DailyTask.user_id == uid,
                DailyTask.status.in_([DailyTaskStatus.pending, DailyTaskStatus.in_progress]),
            )
        )
        .order_by(DailyTask.date.asc(), DailyTask.created_at.asc())
        .limit(20)
    )
    daily_today = daily_today_result.scalars().all()

    def _task_dict(t: Task) -> dict:
        pid = str(t.project_id)
        return {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "project_id": pid,
            "project_name": project_name_map.get(pid),
            "item_type": "task",
        }

    def _daily_dict(d: DailyTask) -> dict:
        return {
            "id": str(d.id),
            "title": d.title,
            "status": d.status,
            "priority": "medium",
            "due_date": d.date.isoformat(),
            "project_id": None,
            "item_type": "daily",
            "work_minutes": d.work_minutes,
        }

    return {
        "kpi": {
            "todo": todo_count,
            "overdue": overdue_count,
            "completed_this_week": completed_count,
        },
        "today_due": [_task_dict(t) for t in today_tasks] + [_daily_dict(d) for d in daily_today],
        "action_required": [_task_dict(t) for t in urgent_tasks],
        "upcoming": [_task_dict(t) for t in upcoming_tasks],
        "deadline_projects": deadline_out,
    }
