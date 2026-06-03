import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.project import ProjectRole
from app.models.task import Task
from app.models.user import User
from app.models.v3_models import TaskDependency

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/dependencies", tags=["dependencies"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.viewer)


async def _require_write(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.member)


class DepCreate(BaseModel):
    to_task_id: uuid.UUID
    dep_type: str = "finish_to_start"


class DepOut(BaseModel):
    id: uuid.UUID
    from_task_id: uuid.UUID
    to_task_id: uuid.UUID
    dep_type: str

    model_config = {"from_attributes": True}


async def _has_cycle(from_id: uuid.UUID, to_id: uuid.UUID, db: AsyncSession) -> bool:
    """DFS cycle detection: check if adding from_id→to_id creates a cycle."""
    visited: set[uuid.UUID] = set()
    stack = [to_id]
    while stack:
        node = stack.pop()
        if node == from_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        result = await db.execute(select(TaskDependency.to_task_id).where(TaskDependency.from_task_id == node))
        for row in result.all():
            stack.append(row[0])
    return False


@router.get("/", response_model=list[DepOut])
async def list_deps(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(TaskDependency).where(TaskDependency.from_task_id == task_id))
    return result.scalars().all()


@router.post("/", response_model=DepOut, status_code=201)
async def add_dep(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: DepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_write(project_id, current_user, db)
    if task_id == body.to_task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")
    # 確認 target task 存在且在同一專案
    target = await db.get(Task, body.to_task_id)
    if not target or str(target.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Target task not found in this project")
    # Cycle detection
    if await _has_cycle(task_id, body.to_task_id, db):
        raise HTTPException(status_code=400, detail="Adding this dependency would create a cycle")
    dep = TaskDependency(from_task_id=task_id, to_task_id=body.to_task_id, dep_type=body.dep_type)
    db.add(dep)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Dependency already exists")
    await db.refresh(dep)
    return dep


@router.delete("/{dep_id}", status_code=204)
async def remove_dep(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    dep_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_write(project_id, current_user, db)
    dep = await db.get(TaskDependency, dep_id)
    if not dep or str(dep.from_task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Dependency not found")
    await db.delete(dep)
    await db.commit()
