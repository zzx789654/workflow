"""F15 — 任務 Check-in 每日進度更新"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v4_models import TaskCheckin

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/checkins", tags=["checkins"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


class CheckinCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    progress: int = Field(0, ge=0, le=100)


class CheckinOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    progress: int
    checked_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[CheckinOut])
async def list_checkins(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    res = await db.execute(
        select(TaskCheckin).where(TaskCheckin.task_id == task_id).order_by(TaskCheckin.checked_at.desc())
    )
    return res.scalars().all()


@router.post("/", response_model=CheckinOut, status_code=201)
async def create_checkin(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: CheckinCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    checkin = TaskCheckin(
        task_id=task_id,
        user_id=current_user.id,
        content=body.content,
        progress=body.progress,
    )
    db.add(checkin)
    await db.commit()
    await db.refresh(checkin)
    return checkin


# Stale-task summary: tasks with no check-in in past 2 days
stale_router = APIRouter(prefix="/tasks/stale-checkins", tags=["checkins"])


@stale_router.get("")
async def stale_checkins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = datetime.now(UTC) - timedelta(days=2)
    if current_user.role.value == "admin":
        proj_res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
    else:
        proj_res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
    proj_ids = [r[0] for r in proj_res.all()]

    # Tasks in progress with no recent checkin
    res = await db.execute(
        select(Task).where(
            and_(
                Task.project_id.in_(proj_ids),
                Task.status.in_(["in_progress", "review"]),
            )
        )
    )
    tasks = res.scalars().all()

    stale = []
    for t in tasks:
        last_res = await db.execute(
            select(TaskCheckin).where(TaskCheckin.task_id == t.id).order_by(TaskCheckin.checked_at.desc()).limit(1)
        )
        last = last_res.scalar_one_or_none()
        if not last or last.checked_at < cutoff:
            stale.append(
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "project_id": str(t.project_id),
                    "last_checkin": last.checked_at.isoformat() if last else None,
                }
            )

    return {"stale_tasks": stale}
