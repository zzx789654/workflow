from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task, TaskAssignee, TaskStatus
from app.models.user import User
from app.models.v3_models import TaskDependency

router = APIRouter(prefix="/dashboard", tags=["ai_suggest"])


@router.get("/ai-suggest")
async def ai_suggest(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    # Get all non-done tasks accessible to the user
    if current_user.role.value == "admin":
        tasks_r = await db.execute(select(Task).where(Task.status != TaskStatus.done))
    else:
        # Tasks in projects user belongs to
        proj_q = select(ProjectMember.project_id).where(ProjectMember.user_id == uid)
        tasks_r = await db.execute(
            select(Task).where(
                and_(
                    Task.status != TaskStatus.done,
                    Task.project_id.in_(proj_q),
                )
            )
        )

    tasks = tasks_r.scalars().all()
    if not tasks:
        return []

    now = datetime.now(UTC)
    task_ids = [t.id for t in tasks]

    # Count blocking dependencies for each task (tasks that block others)
    blocking_r = await db.execute(
        select(TaskDependency.from_task_id, func.count().label("cnt"))
        .where(TaskDependency.from_task_id.in_(task_ids))
        .group_by(TaskDependency.from_task_id)
    )
    blocking_counts: dict = {row[0]: row[1] for row in blocking_r.all()}

    # Count assignee workload (how many tasks each assignee has)
    assignee_counts_r = await db.execute(
        select(TaskAssignee.user_id, func.count().label("cnt"))
        .select_from(TaskAssignee)
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(Task.status != TaskStatus.done)
        .group_by(TaskAssignee.user_id)
    )
    assignee_workload: dict = {row[0]: row[1] for row in assignee_counts_r.all()}

    # Get first assignee for each task
    task_assignees_r = await db.execute(
        select(TaskAssignee.task_id, TaskAssignee.user_id).where(TaskAssignee.task_id.in_(task_ids))
    )
    task_assignee_map: dict = {}
    for row in task_assignees_r.all():
        if row[0] not in task_assignee_map:
            task_assignee_map[row[0]] = row[1]

    scored = []
    for task in tasks:
        # days_until_due_inverse: higher score for tasks due sooner
        if task.due_date:
            days_until_due = (task.due_date - now.date()).days
            if days_until_due <= 0:
                due_score = 100.0
            else:
                due_score = max(0.0, 100.0 - days_until_due * 5)
        else:
            due_score = 10.0  # no due date gets low priority

        # blocking_count score (0-100)
        blocking = blocking_counts.get(task.id, 0)
        blocking_score = min(100.0, blocking * 20.0)

        # assignee_workload_inverse: less busy assignee = higher score
        assignee_id = task_assignee_map.get(task.id)
        if assignee_id:
            workload = assignee_workload.get(assignee_id, 1)
            workload_inverse = max(0.0, 100.0 - (workload - 1) * 10)
        else:
            workload_inverse = 50.0

        score = round(due_score * 0.4 + blocking_score * 0.3 + workload_inverse * 0.3, 1)

        # Build reason
        reasons = []
        if task.due_date and (task.due_date - now.date()).days <= 3:
            reasons.append("due soon")
        if blocking > 0:
            reasons.append(f"blocks {blocking} task(s)")
        if assignee_id and assignee_workload.get(assignee_id, 0) <= 3:
            reasons.append("assignee available")
        reason = ", ".join(reasons) if reasons else "high priority"

        scored.append(
            {
                "task_id": str(task.id),
                "title": task.title,
                "score": score,
                "reason": reason,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]
