"""F08 — 週報自動生成"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/weekly-report", tags=["weekly_report"])


@router.get("")
async def get_weekly_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    # Accessible project IDs
    if current_user.role.value == "admin":
        proj_res = await db.execute(select(Project.id))
        proj_ids = [r[0] for r in proj_res.all()]
    else:
        proj_res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
        proj_ids = [r[0] for r in proj_res.all()]

    # Completed this week
    done_res = await db.execute(
        select(Task)
        .where(
            and_(
                Task.project_id.in_(proj_ids),
                Task.status == "done",
                Task.updated_at >= week_start,
                Task.updated_at < week_end,
            )
        )
        .order_by(Task.updated_at.desc())
    )
    done_tasks = done_res.scalars().all()

    # Overdue (not done, past due_date)
    overdue_res = await db.execute(
        select(Task)
        .where(
            and_(
                Task.project_id.in_(proj_ids),
                Task.status != "done",
                Task.due_date < now.date(),
            )
        )
        .order_by(Task.due_date)
    )
    overdue_tasks = overdue_res.scalars().all()

    # In-progress
    wip_res = await db.execute(
        select(Task)
        .where(
            and_(
                Task.project_id.in_(proj_ids),
                Task.status.in_(["in_progress", "review"]),
            )
        )
        .order_by(Task.priority.desc())
    )
    wip_tasks = wip_res.scalars().all()

    def task_dict(t: Task):
        return {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
            "project_id": str(t.project_id),
        }

    # Build markdown
    done_lines = [f"- {t.title}" for t in done_tasks] or ["- 本週尚無完成項目"]
    wip_lines = [f"- [{t.priority.upper()}] {t.title}" for t in wip_tasks] or ["- 無"]
    overdue_lines = [f"- {t.title}（截止 {t.due_date}）" for t in overdue_tasks] or ["- 無延遲任務"]
    lines = (
        [
            f"# 週報 {week_start.strftime('%Y/%m/%d')} — {(week_end - timedelta(days=1)).strftime('%Y/%m/%d')}",
            "",
            f"## 本週完成（{len(done_tasks)} 項）",
        ]
        + done_lines
        + ["", f"## 進行中（{len(wip_tasks)} 項）"]
        + wip_lines
        + ["", f"## 延遲任務（{len(overdue_tasks)} 項）"]
        + overdue_lines
        + ["", "## 下週計畫", "<!-- 請在此填寫下週計畫 -->"]
    )
    markdown = "\n".join(lines)

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "done_count": len(done_tasks),
        "overdue_count": len(overdue_tasks),
        "wip_count": len(wip_tasks),
        "done_tasks": [task_dict(t) for t in done_tasks],
        "overdue_tasks": [task_dict(t) for t in overdue_tasks],
        "wip_tasks": [task_dict(t) for t in wip_tasks],
        "markdown": markdown,
    }
