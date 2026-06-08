import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy import exists as sa_exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskArchive, DailyTaskLabel, DailyTaskStatus
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
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
    q = (
        select(DailyTask)
        .options(
            selectinload(DailyTask.labels),
            selectinload(DailyTask.linked_task).selectinload(Task.project),
        )
        .where(DailyTask.id == task_id)
    )
    if user.role != UserRole.admin:
        q = q.where(DailyTask.user_id == user.id)
    result = await db.execute(q)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")
    return task


@router.get("/", response_model=list[DailyTaskOut])
async def list_daily_tasks(
    task_date: date | None = Query(None, alias="date"),
    label: str | None = Query(None),
    pending_only: bool = Query(False),
    target_user_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = current_user.role == UserRole.admin

    q = select(DailyTask).options(
        selectinload(DailyTask.labels),
        selectinload(DailyTask.linked_task).selectinload(Task.project),
    )
    if is_admin and target_user_id:
        q = q.where(DailyTask.user_id == target_user_id)
    elif not is_admin:
        q = q.where(DailyTask.user_id == current_user.id)
    if task_date:
        q = q.where(DailyTask.date == task_date)
    if pending_only:
        today = date.today()
        q = q.where(
            or_(
                DailyTask.status.in_([DailyTaskStatus.pending, DailyTaskStatus.in_progress]),
                and_(
                    DailyTask.date == today,
                    DailyTask.status.notin_([DailyTaskStatus.pending, DailyTaskStatus.in_progress]),
                ),
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


# ─── 批次封存（刪除）已完成的日常任務 ────────────────────────────
class ArchiveDailyTasksRequest(BaseModel):
    mode: Literal["done_immediately", "done_1month", "done_3months", "done_custom"]
    before_date: date | None = None  # mode=done_custom 時使用


def _compute_cutoff(mode: str, before_date: date | None) -> date:
    today = date.today()
    if mode == "done_immediately":
        return today
    elif mode == "done_1month":
        return today - timedelta(days=30)
    elif mode == "done_3months":
        return today - timedelta(days=90)
    elif mode == "done_custom":
        if not before_date:
            raise HTTPException(status_code=422, detail="before_date is required for done_custom mode")
        return before_date
    raise HTTPException(status_code=422, detail="Invalid mode")


def _build_archive_query(uid, cutoff: date):
    # 阻擋封存：linked task 存在且尚未完成（只有 done 算完成）
    unfinished_linked = (
        select(Task.id)
        .where(
            and_(
                Task.id == DailyTask.linked_task_id,
                Task.status != TaskStatus.done,
            )
        )
        .correlate(DailyTask)
    )
    return select(DailyTask).where(
        and_(
            DailyTask.user_id == uid,
            DailyTask.status == DailyTaskStatus.done,
            DailyTask.date <= cutoff,
            ~sa_exists(unfinished_linked),
        )
    )


@router.post("/archive/preview", status_code=200)
async def preview_archive_daily_tasks(
    body: ArchiveDailyTasksRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """預覽將封存的筆數（不實際執行）。"""
    cutoff = _compute_cutoff(body.mode, body.before_date)
    q = _build_archive_query(current_user.id, cutoff).with_only_columns(func.count())
    result = await db.execute(q)
    count = result.scalar() or 0
    return {"count": count, "cutoff": cutoff.isoformat()}


@router.post("/archive", status_code=200)
async def archive_daily_tasks(
    body: ArchiveDailyTasksRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """將已完成的日常任務搬移到封存表，不刪除。
    - done_immediately：封存所有已完成（狀態 done）
    - done_1month：封存 1 個月前完成（date <= today-30）
    - done_3months：封存 3 個月前完成（date <= today-90）
    - done_custom：封存 before_date 之前完成
    """
    cutoff = _compute_cutoff(body.mode, body.before_date)
    rows_result = await db.execute(_build_archive_query(current_user.id, cutoff))
    rows = rows_result.scalars().all()
    if not rows:
        return {"archived": 0}

    archived_at = datetime.now(UTC)
    ids_to_delete = []

    for dt in rows:
        archive_row = DailyTaskArchive(
            id=dt.id,
            user_id=dt.user_id,
            title=dt.title,
            description=dt.description,
            status=dt.status.value if hasattr(dt.status, "value") else dt.status,
            progress=dt.progress,
            date=dt.date,
            started_at=dt.started_at,
            ended_at=dt.ended_at,
            notify_at=dt.notify_at,
            work_minutes=dt.work_minutes,
            linked_task_id=dt.linked_task_id,
            created_at=dt.created_at,
            updated_at=dt.updated_at,
            archived_at=archived_at,
        )
        db.add(archive_row)
        ids_to_delete.append(dt.id)

    # Flush archive inserts first, then delete originals
    await db.flush()
    await db.execute(delete(DailyTask).where(DailyTask.id.in_(ids_to_delete)))
    await db.commit()
    return {"archived": len(ids_to_delete)}


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


# ─── 歷史日常任務查詢 ──────────────────────────────────────────────


class ArchiveHistoryItem(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: str
    progress: int
    date: date
    work_minutes: int
    linked_task_id: uuid.UUID | None
    linked_task_title: str | None
    linked_project_id: uuid.UUID | None
    linked_project_name: str | None
    archived_at: datetime

    model_config = {"from_attributes": True}


class ArchiveHistoryStats(BaseModel):
    total_records: int
    total_work_minutes: int
    total_work_hours: float


class ArchiveHistoryResponse(BaseModel):
    items: list[ArchiveHistoryItem]
    stats: ArchiveHistoryStats


@router.get("/archive/history", response_model=ArchiveHistoryResponse)
async def get_archive_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    linked_task_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查詢歷史日常任務封存記錄，支援日期範圍篩選與關聯任務篩選。"""
    q = select(DailyTaskArchive).where(DailyTaskArchive.user_id == current_user.id)
    if date_from:
        q = q.where(DailyTaskArchive.date >= date_from)
    if date_to:
        q = q.where(DailyTaskArchive.date <= date_to)
    if linked_task_id:
        q = q.where(DailyTaskArchive.linked_task_id == linked_task_id)
    q = q.order_by(DailyTaskArchive.date.desc(), DailyTaskArchive.archived_at.desc())

    result = await db.execute(q)
    rows = result.scalars().all()

    # 批次查詢關聯任務與專案名稱
    task_ids = {r.linked_task_id for r in rows if r.linked_task_id}
    task_map: dict[uuid.UUID, tuple[str, uuid.UUID | None, str]] = {}
    if task_ids:
        tasks_result = await db.execute(select(Task.id, Task.title, Task.project_id).where(Task.id.in_(task_ids)))
        task_rows = tasks_result.all()
        project_ids = {t.project_id for t in task_rows if t.project_id}
        project_map: dict[uuid.UUID, str] = {}
        if project_ids:
            proj_result = await db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids)))
            project_map = {p.id: p.name for p in proj_result.all()}
        for t in task_rows:
            task_map[t.id] = (t.title, t.project_id, project_map.get(t.project_id, ""))

    items = []
    for r in rows:
        t_info = task_map.get(r.linked_task_id) if r.linked_task_id else None
        items.append(
            ArchiveHistoryItem(
                id=r.id,
                title=r.title,
                description=r.description,
                status=r.status if isinstance(r.status, str) else r.status.value,
                progress=r.progress,
                date=r.date,
                work_minutes=r.work_minutes,
                linked_task_id=r.linked_task_id,
                linked_task_title=t_info[0] if t_info else None,
                linked_project_id=t_info[1] if t_info else None,
                linked_project_name=t_info[2] if t_info else None,
                archived_at=r.archived_at,
            )
        )

    total_work_minutes = sum(r.work_minutes for r in rows)
    stats = ArchiveHistoryStats(
        total_records=len(rows),
        total_work_minutes=total_work_minutes,
        total_work_hours=round(total_work_minutes / 60, 1),
    )
    return ArchiveHistoryResponse(items=items, stats=stats)


@router.get("/archive/history/export")
async def export_archive_history_csv(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    linked_task_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """匯出歷史日常任務為 CSV。"""
    # 複用相同查詢邏輯
    resp = await get_archive_history(
        date_from=date_from,
        date_to=date_to,
        linked_task_id=linked_task_id,
        db=db,
        current_user=current_user,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "日期",
            "標題",
            "描述",
            "狀態",
            "進度(%)",
            "工時(分鐘)",
            "工時(小時)",
            "關聯任務",
            "所屬專案",
            "封存時間",
        ]
    )
    STATUS_ZH = {"pending": "待辦", "in_progress": "進行中", "done": "完成", "cancelled": "已取消"}
    for item in resp.items:
        writer.writerow(
            [
                str(item.date),
                item.title,
                item.description or "",
                STATUS_ZH.get(item.status, item.status),
                item.progress,
                item.work_minutes,
                round(item.work_minutes / 60, 2),
                item.linked_task_title or "",
                item.linked_project_name or "",
                item.archived_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )

    output.seek(0)
    filename = f"daily_tasks_history_{date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── 自動排程輔助（供 lifespan 呼叫）─────────────────────────────


async def run_auto_archive(db_factory) -> int:
    """自動將符合使用者設定天數的已完成日常任務搬移至封存表。
    回傳封存總筆數。
    """
    today = date.today()
    total_archived = 0

    async with db_factory() as db:
        # 取得所有有設定 auto_archive_days > 0 的使用者
        users_result = await db.execute(select(User).where(User.auto_archive_days > 0, User.is_active == True))
        users = users_result.scalars().all()

        for user in users:
            cutoff = today - timedelta(days=user.auto_archive_days)

            unfinished_linked = (
                select(Task.id)
                .where(
                    and_(
                        Task.id == DailyTask.linked_task_id,
                        Task.status != TaskStatus.done,
                    )
                )
                .correlate(DailyTask)
            )

            rows_result = await db.execute(
                select(DailyTask).where(
                    and_(
                        DailyTask.user_id == user.id,
                        DailyTask.status == DailyTaskStatus.done,
                        DailyTask.date <= cutoff,
                        ~sa_exists(unfinished_linked),
                    )
                )
            )
            rows = rows_result.scalars().all()
            if not rows:
                continue

            archived_at = datetime.now(UTC)
            ids_to_delete = []
            for dt in rows:
                db.add(
                    DailyTaskArchive(
                        id=dt.id,
                        user_id=dt.user_id,
                        title=dt.title,
                        description=dt.description,
                        status=dt.status.value if hasattr(dt.status, "value") else dt.status,
                        progress=dt.progress,
                        date=dt.date,
                        started_at=dt.started_at,
                        ended_at=dt.ended_at,
                        notify_at=dt.notify_at,
                        work_minutes=dt.work_minutes,
                        linked_task_id=dt.linked_task_id,
                        created_at=dt.created_at,
                        updated_at=dt.updated_at,
                        archived_at=archived_at,
                    )
                )
                ids_to_delete.append(dt.id)

            await db.flush()
            await db.execute(delete(DailyTask).where(DailyTask.id.in_(ids_to_delete)))
            await db.commit()
            total_archived += len(ids_to_delete)

    return total_archived
