import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["bulk_actions"])


async def _check_manager(project_id: uuid.UUID, user: User, db: AsyncSession) -> None:
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
                ProjectMember.role.in_([ProjectRole.owner, ProjectRole.manager]),
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Manager or owner role required")


class BulkActionBody(BaseModel):
    task_ids: list[uuid.UUID]
    action: str  # "status" | "assignee" | "delete"
    value: str | None = None


@router.patch("/bulk")
async def bulk_action(
    project_id: uuid.UUID,
    body: BulkActionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)

    if not body.task_ids:
        raise HTTPException(status_code=400, detail="task_ids must not be empty")

    # Verify all tasks belong to this project
    tasks_result = await db.execute(select(Task).where(and_(Task.id.in_(body.task_ids), Task.project_id == project_id)))
    tasks = tasks_result.scalars().all()
    if len(tasks) != len(body.task_ids):
        raise HTTPException(status_code=404, detail="One or more tasks not found in this project")

    if body.action == "status":
        if not body.value:
            raise HTTPException(status_code=400, detail="value required for status action")
        try:
            new_status = TaskStatus(body.value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.value}")
        for task in tasks:
            task.status = new_status
        await db.commit()
        return {"updated": len(tasks), "action": "status", "value": body.value}

    elif body.action == "assignee":
        if not body.value:
            raise HTTPException(status_code=400, detail="value (user_id UUID) required for assignee action")
        try:
            assignee_id = uuid.UUID(body.value)
        except ValueError:
            raise HTTPException(status_code=400, detail="value must be a valid UUID for assignee action")
        from app.models.task import TaskAssignee

        for task in tasks:
            # Remove existing assignees and set the new one
            existing = await db.execute(select(TaskAssignee).where(TaskAssignee.task_id == task.id))
            for a in existing.scalars().all():
                await db.delete(a)
            db.add(TaskAssignee(task_id=task.id, user_id=assignee_id))
        await db.commit()
        return {"updated": len(tasks), "action": "assignee", "value": body.value}

    elif body.action == "delete":
        for task in tasks:
            await db.delete(task)
        await db.commit()
        return {"deleted": len(tasks), "action": "delete"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")
