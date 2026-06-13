from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.visibility import resolve_visible_user_ids
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskLabel
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar"])

# 穩定的人員配色盤——依 user_id 雜湊取色，確保同一人每次同色（前端圖例據此上色/勾選）。
_PALETTE = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#db2777",
    "#65a30d",
    "#ea580c",
    "#4f46e5",
    "#0d9488",
    "#be123c",
    "#a16207",
    "#9333ea",
    "#0284c7",
]


def _color_for(user_id: str) -> str:
    return _PALETTE[hash(user_id) % len(_PALETTE)]


class CalendarEvent(BaseModel):
    id: str
    title: str
    date: date
    type: str  # "task" | "daily"
    status: str
    priority: str | None = None
    progress: int = 0
    project_id: str | None = None
    project_name: str | None = None
    labels: list[str] = []
    # 部門堆疊檢視用：daily task 的擁有者與其配色（task 類型留空）
    user_id: str | None = None
    user_name: str | None = None
    color: str | None = None


@router.get("/", response_model=list[CalendarEvent])
async def get_calendar_events(
    year: int = Query(...),
    month: int = Query(...),
    label: str | None = Query(None),
    include_team: bool = Query(False, description="主管堆疊檢視：含可視範圍內其他成員的日常作業"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    events: list[CalendarEvent] = []

    # Project tasks：顯示有 due_date 或 start_date / end_date 落在本月的任務
    from sqlalchemy import or_

    subq = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
    task_q = (
        select(Task)
        .options(selectinload(Task.project))
        .where(
            Task.project_id.in_(subq),
            or_(
                Task.due_date.between(start, end),
                Task.start_date.between(start, end),
                Task.end_date.between(start, end),
            ),
        )
        .order_by(Task.due_date.asc().nulls_last(), Task.start_date.asc().nulls_last())
    )
    seen_task_ids: set[str] = set()
    task_result = await db.execute(task_q)
    for task in task_result.scalars().all():
        if str(task.id) in seen_task_ids:
            continue
        seen_task_ids.add(str(task.id))
        # 優先用 due_date，其次 start_date，最後 end_date 作為顯示日期
        display_date = task.due_date or task.start_date or task.end_date
        if not display_date:
            continue
        events.append(
            CalendarEvent(
                id=str(task.id),
                title=task.title,
                date=display_date,
                type="task",
                status=task.status.value,
                priority=task.priority.value,
                progress=task.progress,
                project_id=str(task.project_id),
                project_name=task.project.name if task.project else None,
                labels=[],
            )
        )

    # Daily tasks：預設只看自己；include_team 時，主管堆疊檢視可視範圍內所有成員。
    # 可視範圍由 resolve_visible_user_ids 嚴格限制（自管單位子樹 ∪ admin 授權子樹），
    # 防止越權檢視非管轄成員的日常作業（OWASP A01）。
    if include_team:
        visible_ids = await resolve_visible_user_ids(db, current_user)
    else:
        visible_ids = {current_user.id}

    daily_q = (
        select(DailyTask)
        .options(selectinload(DailyTask.labels), selectinload(DailyTask.user))
        .where(
            DailyTask.date >= start,
            DailyTask.date <= end,
        )
    )
    # visible_ids 為 None 代表 admin（可見全體），不加 user 篩選
    if visible_ids is not None:
        daily_q = daily_q.where(DailyTask.user_id.in_(visible_ids))
    if label:
        daily_q = daily_q.join(DailyTaskLabel).where(DailyTaskLabel.label == label)
    daily_result = await db.execute(daily_q)
    for dt in daily_result.scalars().unique().all():
        lbls = [lb.label for lb in dt.labels]
        if label and label not in lbls:
            continue
        owner_id = str(dt.user_id)
        events.append(
            CalendarEvent(
                id=str(dt.id),
                title=dt.title,
                date=dt.date,
                type="daily",
                status=dt.status.value,
                progress=dt.progress,
                labels=lbls,
                user_id=owner_id,
                user_name=dt.user.display_name if dt.user else None,
                color=_color_for(owner_id),
            )
        )

    return sorted(events, key=lambda e: e.date)
