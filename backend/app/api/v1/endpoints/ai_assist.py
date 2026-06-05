"""F24 — AI 優先度建議（規則引擎，預留 Claude API 介面）"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.models.v3_models import TaskDependency

router = APIRouter(prefix="/ai/priority-suggestions", tags=["ai_assist"])


def _urgency_score(task: Task, overdue_days: int, blocking_count: int) -> float:
    score = 0.0
    # Due date proximity
    if task.due_date:
        days_left = (date.fromisoformat(task.due_date) - date.today()).days
        if days_left < 0:
            score += 50 + min(abs(days_left) * 2, 30)
        elif days_left == 0:
            score += 45
        elif days_left <= 2:
            score += 35
        elif days_left <= 7:
            score += 20
        else:
            score += max(0, 10 - days_left * 0.5)
    # Blocking others
    score += blocking_count * 15
    # Priority weight
    weights = {"urgent": 30, "high": 20, "medium": 10, "low": 0}
    score += weights.get(task.priority, 0)
    return round(score, 1)


@router.get("")
async def priority_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get accessible projects
    if current_user.role.value == "admin":
        proj_res = await db.execute(select(ProjectMember.project_id))
    else:
        proj_res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
    proj_ids = [r[0] for r in proj_res.all()]

    # Open tasks assigned to current user
    tasks_res = await db.execute(
        select(Task)
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(
            and_(
                TaskAssignee.user_id == current_user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.project_id.in_(proj_ids),
            )
        )
    )
    tasks = tasks_res.scalars().all()

    # Count blocking dependencies (how many tasks depend on each)
    blocking_res = await db.execute(
        select(
            TaskDependency.to_task_id,
            func.count().label("blocking_count"),
        )
        .where(TaskDependency.to_task_id.in_([t.id for t in tasks]))
        .group_by(TaskDependency.to_task_id)
    )
    blocking_map = {str(r.to_task_id): r.blocking_count for r in blocking_res.all()}

    # Score & rank
    scored = []
    today = date.today().isoformat()
    for t in tasks:
        overdue = (date.today() - date.fromisoformat(t.due_date)).days if t.due_date and t.due_date < today else 0
        blocking = blocking_map.get(str(t.id), 0)
        score = _urgency_score(t, overdue, blocking)

        reason_parts = []
        if t.due_date:
            days_left = (date.fromisoformat(t.due_date) - date.today()).days
            if days_left < 0:
                reason_parts.append(f"已逾期 {abs(days_left)} 天")
            elif days_left <= 2:
                reason_parts.append(f"還有 {days_left} 天截止")
        if blocking > 0:
            reason_parts.append(f"有 {blocking} 個任務等待完成")
        if t.priority in ("urgent", "high"):
            reason_parts.append(f"優先度：{t.priority}")

        scored.append(
            {
                "task_id": str(t.id),
                "title": t.title,
                "project_id": str(t.project_id),
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date,
                "urgency_score": score,
                "reason": "；".join(reason_parts) if reason_parts else "常規追蹤",
            }
        )

    scored.sort(key=lambda x: x["urgency_score"], reverse=True)
    top5 = scored[:5]

    return {
        "suggestions": top5,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": "rule_engine_v1",
        "_note": "預留 Claude API 介面：可替換為 anthropic.Anthropic().messages.create(...)",
    }
