"""F13 — 批次操作 Bulk Actions"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/tasks/bulk", tags=["bulk_tasks"])


async def _check_write(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role.in_(["owner", "manager", "member"]),
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Write access required")


class BulkUpdate(BaseModel):
    task_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)
    status: str | None = Field(None, pattern="^(todo|in_progress|review|done)$")
    priority: str | None = Field(None, pattern="^(low|medium|high|urgent)$")
    assignee_ids: list[uuid.UUID] | None = None


class BulkDelete(BaseModel):
    task_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


@router.patch("")
async def bulk_update(
    project_id: uuid.UUID,
    body: BulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_write(project_id, current_user, db)

    res = await db.execute(
        select(Task).where(
            Task.id.in_(body.task_ids),
            Task.project_id == project_id,
        )
    )
    tasks = res.scalars().all()
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found")

    updated = []
    for t in tasks:
        if body.status:
            t.status = body.status
        if body.priority:
            t.priority = body.priority
        updated.append(str(t.id))

    await db.commit()
    return {"updated": updated, "count": len(updated)}


@router.delete("")
async def bulk_delete(
    project_id: uuid.UUID,
    body: BulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_write(project_id, current_user, db)

    res = await db.execute(
        select(Task).where(
            Task.id.in_(body.task_ids),
            Task.project_id == project_id,
        )
    )
    tasks = res.scalars().all()
    deleted = []
    for t in tasks:
        deleted.append(str(t.id))
        await db.delete(t)
    await db.commit()
    return {"deleted": deleted, "count": len(deleted)}
