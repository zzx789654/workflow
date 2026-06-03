import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.project import ProjectRole
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/subtasks", tags=["subtasks"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.viewer)


async def _require_write(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.member)


class SubTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None


class SubTaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    parent_task_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    priority: str
    progress: int

    model_config = {"from_attributes": True}


async def _update_parent_counts(parent_id: uuid.UUID, db: AsyncSession):
    total_result = await db.execute(select(func.count()).where(Task.parent_task_id == parent_id))
    total = total_result.scalar() or 0
    done_result = await db.execute(select(func.count()).where(Task.parent_task_id == parent_id, Task.status == "done"))
    done = done_result.scalar() or 0
    parent = await db.get(Task, parent_id)
    if parent:
        parent.subtask_count = total
        parent.subtask_done_count = done
        parent.progress = int(done / total * 100) if total > 0 else 0


@router.get("/", response_model=list[SubTaskOut])
async def list_subtasks(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(Task).where(Task.parent_task_id == task_id).order_by(Task.created_at))
    return result.scalars().all()


@router.post("/", response_model=SubTaskOut, status_code=201)
async def create_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: SubTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_write(project_id, current_user, db)
    parent = await db.get(Task, task_id)
    if not parent or str(parent.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if parent.parent_task_id is not None:
        raise HTTPException(status_code=400, detail="Nesting beyond 2 levels not allowed")
    subtask = Task(
        project_id=project_id,
        parent_task_id=task_id,
        title=body.title,
        description=body.description,
    )
    db.add(subtask)
    await db.flush()
    await _update_parent_counts(task_id, db)
    await db.commit()
    await db.refresh(subtask)
    return subtask


@router.patch("/{subtask_id}", response_model=SubTaskOut)
async def update_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_write(project_id, current_user, db)
    subtask = await db.get(Task, subtask_id)
    if not subtask or str(subtask.parent_task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Subtask not found")
    allowed = {"title", "description", "status", "priority", "progress"}
    for k, v in body.items():
        if k in allowed:
            setattr(subtask, k, v)
    await db.flush()
    await _update_parent_counts(task_id, db)
    await db.commit()
    await db.refresh(subtask)
    return subtask


@router.delete("/{subtask_id}", status_code=204)
async def delete_subtask(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    subtask_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_write(project_id, current_user, db)
    subtask = await db.get(Task, subtask_id)
    if not subtask or str(subtask.parent_task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Subtask not found")
    await db.delete(subtask)
    await db.flush()
    await _update_parent_counts(task_id, db)
    await db.commit()
