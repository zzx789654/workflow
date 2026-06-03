import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task
from app.models.user import User
from app.models.v3_p2_models import TaskCheckin

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/checkins", tags=["checkins"])


async def _get_task(project_id: uuid.UUID, task_id: uuid.UUID, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(and_(Task.id == task_id, Task.project_id == project_id)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


class CheckinCreate(BaseModel):
    content: str = Field(..., min_length=1)
    progress: int = Field(0, ge=0, le=100)


@router.post("/", status_code=201)
async def create_checkin(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: CheckinCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task(project_id, task_id, db)
    checkin = TaskCheckin(task_id=task_id, user_id=current_user.id, content=body.content, progress=body.progress)
    db.add(checkin)
    await db.commit()
    await db.refresh(checkin)
    return {
        "id": str(checkin.id),
        "task_id": str(checkin.task_id),
        "user_id": str(checkin.user_id),
        "content": checkin.content,
        "progress": checkin.progress,
        "checked_at": checkin.checked_at.isoformat(),
    }


@router.get("/")
async def list_checkins(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_task(project_id, task_id, db)
    result = await db.execute(
        select(TaskCheckin).where(TaskCheckin.task_id == task_id).order_by(TaskCheckin.checked_at.desc())
    )
    checkins = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "task_id": str(c.task_id),
            "user_id": str(c.user_id),
            "content": c.content,
            "progress": c.progress,
            "checked_at": c.checked_at.isoformat(),
        }
        for c in checkins
    ]
