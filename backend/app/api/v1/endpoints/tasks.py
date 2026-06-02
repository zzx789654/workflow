import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.v1.endpoints.notifications import _parse_and_notify
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task, TaskAssignee, TaskComment
from app.models.user import User
from app.schemas.task import KanbanMoveRequest, TaskCommentCreate, TaskCommentOut, TaskCreate, TaskOut, TaskUpdate
from app.websocket.manager import manager

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


async def _load_task(task_id: uuid.UUID, db: AsyncSession) -> Task:
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignees).selectinload(TaskAssignee.user),
            selectinload(Task.comments).selectinload(TaskComment.author),
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


@router.get("/", response_model=list[TaskOut])
async def list_tasks(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignees).selectinload(TaskAssignee.user),
            selectinload(Task.comments).selectinload(TaskComment.author),
        )
        .where(Task.project_id == project_id)
        .order_by(Task.status, Task.position)
    )
    return result.scalars().all()


@router.post("/", response_model=TaskOut, status_code=201)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    task_data = body.model_dump(exclude={"assignee_ids"})
    task = Task(project_id=project_id, **task_data)
    db.add(task)
    await db.flush()
    for uid in body.assignee_ids:
        db.add(TaskAssignee(task_id=task.id, user_id=uid))
    await db.commit()
    loaded = await _load_task(task.id, db)
    await manager.broadcast(str(project_id), {"type": "task_created", "task": str(loaded.id)})
    return loaded


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    return await _load_task(task_id, db)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    task = await _load_task(task_id, db)
    update_data = body.model_dump(exclude_none=True, exclude={"assignee_ids"})
    for field, value in update_data.items():
        setattr(task, field, value)
    if body.assignee_ids is not None:
        await db.execute(select(TaskAssignee).where(TaskAssignee.task_id == task_id))
        for a in task.assignees:
            await db.delete(a)
        await db.flush()
        for uid in body.assignee_ids:
            db.add(TaskAssignee(task_id=task_id, user_id=uid))
    await db.commit()
    loaded = await _load_task(task_id, db)
    await manager.broadcast(str(project_id), {"type": "task_updated", "task_id": str(task_id)})
    return loaded


@router.patch("/{task_id}/move", response_model=TaskOut)
async def move_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: KanbanMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    task = await _load_task(task_id, db)
    task.status = body.status
    task.position = body.position
    await db.commit()
    loaded = await _load_task(task_id, db)
    await manager.broadcast(
        str(project_id),
        {"type": "task_moved", "task_id": str(task_id), "status": body.status, "position": body.position},
    )
    return loaded


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    task = await _load_task(task_id, db)
    await db.delete(task)
    await db.commit()
    await manager.broadcast(str(project_id), {"type": "task_deleted", "task_id": str(task_id)})


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=201)
async def add_comment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    task = await _load_task(task_id, db)
    comment = TaskComment(task_id=task_id, author_id=current_user.id, content=body.content)
    db.add(comment)
    await db.flush()
    await _parse_and_notify(body.content, current_user, task, db)
    await db.commit()
    result = await db.execute(
        select(TaskComment).options(selectinload(TaskComment.author)).where(TaskComment.id == comment.id)
    )
    loaded = result.scalar_one()
    await manager.broadcast(str(project_id), {"type": "comment_added", "task_id": str(task_id)})
    return loaded
