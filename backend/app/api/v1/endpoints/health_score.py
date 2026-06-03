import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.milestone import Milestone, MilestoneStatus
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}", tags=["health_score"])


@router.get("/health")
async def get_project_health(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check project exists and user has access
    proj_r = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role.value != "admin":
        member_r = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == current_user.id
            )
        )
        if not member_r.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a project member")

    # Total and overdue tasks
    total_r = await db.execute(select(func.count()).where(Task.project_id == project_id))
    total_tasks = total_r.scalar() or 0

    today = datetime.now(UTC).date()
    overdue_r = await db.execute(
        select(func.count()).where(
            and_(Task.project_id == project_id, Task.status != TaskStatus.done, Task.due_date < today)
        )
    )
    overdue_tasks = overdue_r.scalar() or 0

    # Overdue ratio score (weight 40)
    if total_tasks > 0:
        overdue_score = 100 * (1 - overdue_tasks / total_tasks)
    else:
        overdue_score = 100.0

    # Milestone achievement (weight 30)
    total_ms_r = await db.execute(select(func.count()).where(Milestone.project_id == project_id))
    total_milestones = total_ms_r.scalar() or 0

    completed_ms_r = await db.execute(
        select(func.count()).where(
            and_(Milestone.project_id == project_id, Milestone.status == MilestoneStatus.completed)
        )
    )
    completed_milestones = completed_ms_r.scalar() or 0

    milestone_score = (completed_milestones / total_milestones * 100) if total_milestones > 0 else 100.0

    # Member activity (weight 30): members who updated tasks in last 7 days / total members
    week_ago = datetime.now(UTC) - timedelta(days=7)
    total_members_r = await db.execute(select(func.count()).where(ProjectMember.project_id == project_id))
    total_members = total_members_r.scalar() or 0

    from app.models.task import TaskAssignee

    active_members_r = await db.execute(
        select(func.count(distinct(TaskAssignee.user_id)))
        .select_from(TaskAssignee)
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(and_(Task.project_id == project_id, Task.updated_at >= week_ago))
    )
    active_members = active_members_r.scalar() or 0

    activity_score = (active_members / total_members * 100) if total_members > 0 else 100.0

    # Weighted health score
    health_score = round(overdue_score * 0.4 + milestone_score * 0.3 + activity_score * 0.3, 1)

    return {
        "project_id": str(project_id),
        "health_score": health_score,
        "breakdown": {
            "overdue_score": round(overdue_score, 1),
            "milestone_score": round(milestone_score, 1),
            "activity_score": round(activity_score, 1),
        },
        "details": {
            "total_tasks": total_tasks,
            "overdue_tasks": overdue_tasks,
            "total_milestones": total_milestones,
            "completed_milestones": completed_milestones,
            "total_members": total_members,
            "active_members_7d": active_members,
        },
    }
