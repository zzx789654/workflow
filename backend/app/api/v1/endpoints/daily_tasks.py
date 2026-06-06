import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskLabel
from app.models.task import Task
from app.models.project import Project
from app.models.user import User
from app.schemas.daily_task import DailyTaskCreate, DailyTaskOut, DailyTaskUpdate, LinkedTaskInfo

router = APIRouter(prefix="/daily-tasks", tags=["daily-tasks"])


def _build_linked_task_info(dt: DailyTask) -> LinkedTaskInfo | None:
    t = getattr(dt, "linked_task", None)
    if t is None:
        return None
    project = getattr(t, "project", None)
    return LinkedTaskInfo(
        id=t.id,
        title=t.title,
        project_id=t.project_id,
        project_name=project.name if project else "",
    )


def _to_out(dt: DailyTask) -> DailyTaskOut:
    data = {k: v for k, v in dt.__dict__.items() if not k.startswith("_") and k not in ("labels", "linked_task")}
    return DailyTaskOut(
        **data,
        labels=[lb.label for lb in dt.labels],
        linked_task=_build_linked_task_info(dt),
    )


async def _load(task_id: uuid.UUID, user: User, db: AsyncSession) -> DailyTask:
    result = await db.execute(
        select(DailyTask)
        .options(
            selectinload(DailyTask.labels),
            selectinload(DailyTask.linked_task).selectinload(Task.project),
        )
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
    pending_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.daily_task import DailyTaskStatus
    q = (
        select(DailyTask)
        .options(
            selectinload(DailyTask.labels),
            selectinload(DailyTask.linked_task).selectinload(Task.project),
        )
        .where(DailyTask.user_id == current_user.id)
    )
    if task_date:
        q = q.where(DailyTask.date == task_date)
    if pending_only:
        # 未完成：所有日期的 pending/in_progress + 今天的 done/cancelled
        from sqlalchemy import or_, and_
        today = date.today()
        q = q.where(
            or_(
                DailyTask.status.in_([DailyTaskStatus.pending, DailyTaskStatus.in_progress]),
                and_(DailyTask.date == today, DailyTask.status.notin_([DailyTaskStatus.pending, DailyTaskStatus.in_progress]))
            )
        )
    if label:
        q = q.join(DailyTaskLabel).where(DailyTaskLabel.label == label)
    q = q.order_by(DailyTask.date.asc(), DailyTask.created_at.asc())
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
        linked_task_id=body.linked_task_id,
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
    update_data = body.model_dump(exclude_none=True, exclude={"labels"})
    for field, value in update_data.items():
        setattr(task, field, value)
    # Allow explicit unlink: linked_task_id=None only when key is present
    if "linked_task_id" not in update_data and body.model_fields_set and "linked_task_id" in body.model_fields_set:
        task.linked_task_id = None
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


# ─── 查詢指定專案任務的已關聯日常任務 ─────────────────────────────
@router.get("/by-task/{task_id}", response_model=list[DailyTaskOut])
async def list_daily_tasks_by_project_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(DailyTask)
        .options(
            selectinload(DailyTask.labels),
            selectinload(DailyTask.linked_task).selectinload(Task.project),
        )
        .where(DailyTask.linked_task_id == task_id)
        .order_by(DailyTask.date.desc(), DailyTask.created_at.desc())
    )
    result = await db.execute(q)
    return [_to_out(t) for t in result.scalars().unique().all()]
