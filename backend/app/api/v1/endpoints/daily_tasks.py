import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskLabel
from app.models.user import User
from app.schemas.daily_task import DailyTaskCreate, DailyTaskOut, DailyTaskUpdate

router = APIRouter(prefix="/daily-tasks", tags=["daily-tasks"])


def _to_out(dt: DailyTask) -> DailyTaskOut:
    data = {k: v for k, v in dt.__dict__.items() if not k.startswith("_") and k != "labels"}
    return DailyTaskOut(**data, labels=[lb.label for lb in dt.labels])


async def _load(task_id: uuid.UUID, user: User, db: AsyncSession) -> DailyTask:
    result = await db.execute(
        select(DailyTask)
        .options(selectinload(DailyTask.labels))
        .where(DailyTask.id == task_id, DailyTask.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")
    return task


@router.get("/", response_model=list[DailyTaskOut])
async def list_daily_tasks(
    task_date: date | None = Query(None, alias="date"),
    label: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(DailyTask).options(selectinload(DailyTask.labels)).where(DailyTask.user_id == current_user.id)
    if task_date:
        q = q.where(DailyTask.date == task_date)
    if label:
        q = q.join(DailyTaskLabel).where(DailyTaskLabel.label == label)
    q = q.order_by(DailyTask.date.desc(), DailyTask.created_at.desc())
    result = await db.execute(q)
    return [_to_out(t) for t in result.scalars().unique().all()]


@router.post("/", response_model=DailyTaskOut, status_code=201)
async def create_daily_task(
    body: DailyTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = DailyTask(
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        status=body.status,
        progress=body.progress,
        date=body.date,
        started_at=body.started_at,
        ended_at=body.ended_at,
        notify_at=body.notify_at,
        work_minutes=body.work_minutes,
    )
    db.add(task)
    await db.flush()
    for lbl in body.labels:
        db.add(DailyTaskLabel(daily_task_id=task.id, label=lbl.strip()))
    await db.commit()
    loaded = await _load(task.id, current_user, db)
    return _to_out(loaded)


@router.get("/{task_id}", response_model=DailyTaskOut)
async def get_daily_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _to_out(await _load(task_id, current_user, db))


@router.patch("/{task_id}", response_model=DailyTaskOut)
async def update_daily_task(
    task_id: uuid.UUID,
    body: DailyTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _load(task_id, current_user, db)
    for field, value in body.model_dump(exclude_none=True, exclude={"labels"}).items():
        setattr(task, field, value)
    if body.labels is not None:
        for lb in task.labels:
            await db.delete(lb)
        await db.flush()
        for lbl in body.labels:
            db.add(DailyTaskLabel(daily_task_id=task.id, label=lbl.strip()))
    await db.commit()
    loaded = await _load(task_id, current_user, db)
    return _to_out(loaded)


@router.delete("/{task_id}", status_code=204)
async def delete_daily_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _load(task_id, current_user, db)
    await db.delete(task)
    await db.commit()
