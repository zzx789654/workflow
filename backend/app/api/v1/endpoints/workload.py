import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task, TaskAssignee, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/workload", tags=["workload"])

OVERLOAD_THRESHOLD = 10  # tasks per period considered overload


@router.get("/")
async def get_workload(
    period: str = "week",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if period not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period must be 'week' or 'month'")

    # Collect all projects where user is a member (or admin sees all)
    if current_user.role.value == "admin":
        from app.models.project import Project

        proj_result = await db.execute(select(Project.id).where(Project.is_archived == False))  # noqa: E712
        project_ids = [r[0] for r in proj_result.all()]
    else:
        pm_result = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
        project_ids = [r[0] for r in pm_result.all()]

    if not project_ids:
        return []

    # All members in these projects
    members_result = await db.execute(
        select(ProjectMember.user_id).where(ProjectMember.project_id.in_(project_ids)).distinct()
    )
    member_ids = [r[0] for r in members_result.all()]

    if not member_ids:
        return []

    # Load user display names
    users_result = await db.execute(select(User).where(User.id.in_(member_ids)))
    users_map: dict[uuid.UUID, User] = {u.id: u for u in users_result.scalars().all()}

    result = []
    for uid in member_ids:
        # Count tasks assigned to this user in the period (not done or in progress)
        task_count_r = await db.execute(
            select(func.count())
            .select_from(TaskAssignee)
            .join(Task, Task.id == TaskAssignee.task_id)
            .where(
                and_(
                    TaskAssignee.user_id == uid,
                    Task.project_id.in_(project_ids),
                    Task.status != TaskStatus.done,
                )
            )
        )
        task_count = task_count_r.scalar() or 0

        # Estimate hours: 2h per task as simple heuristic
        estimated_hours = task_count * 2

        u = users_map.get(uid)
        result.append(
            {
                "user_id": str(uid),
                "display_name": u.display_name if u else str(uid),
                "task_count": task_count,
                "estimated_hours": estimated_hours,
                "overload": task_count >= OVERLOAD_THRESHOLD,
            }
        )

    result.sort(key=lambda x: x["task_count"], reverse=True)
    return result
