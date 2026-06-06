"""
里程碑模組：改為「任務完成自動記錄」。
每當專案中任何任務狀態變為 done，自動建立一筆 milestone_log。
也提供手動更新工時與備註的介面。
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.project import ProjectRole
from app.models.user import User
from app.models.v3_models import MilestoneLog

router = APIRouter(prefix="/projects/{project_id}/milestones", tags=["milestones"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.viewer)


# ── Output schema ──────────────────────────────────────────────
class MilestoneLogOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    task_title: str
    completed_by: uuid.UUID | None
    completed_by_name: str | None
    work_minutes: int
    daily_task_minutes: int = 0  # 關聯日常任務的時數加總
    note: str | None
    completed_at: datetime

    model_config = {"from_attributes": True}


class MilestoneLogUpdate(BaseModel):
    work_minutes: int | None = Field(None, ge=0)
    note: str | None = Field(None, max_length=1000)


# ── 列出完成記錄 ───────────────────────────────────────────────
@router.get("/", response_model=list[MilestoneLogOut])
async def list_milestone_logs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func
    from app.models.daily_task import DailyTask

    await _check_member(project_id, current_user, db)
    logs_result = await db.execute(
        select(MilestoneLog).where(MilestoneLog.project_id == project_id).order_by(MilestoneLog.completed_at.desc())
    )
    logs = logs_result.scalars().all()

    # 一次查詢所有相關 task_id 的日常任務時數加總
    task_ids = [l.task_id for l in logs if l.task_id is not None]
    daily_minutes_map: dict[uuid.UUID, int] = {}
    if task_ids:
        rows = await db.execute(
            select(DailyTask.linked_task_id, func.sum(DailyTask.work_minutes))
            .where(DailyTask.linked_task_id.in_(task_ids))
            .group_by(DailyTask.linked_task_id)
        )
        for task_id, total in rows.all():
            daily_minutes_map[task_id] = int(total or 0)

    out = []
    for log in logs:
        d = {c.key: getattr(log, c.key) for c in log.__table__.columns}
        d["daily_task_minutes"] = daily_minutes_map.get(log.task_id, 0) if log.task_id else 0
        out.append(MilestoneLogOut(**d))
    return out


# ── 更新工時 / 備註 ────────────────────────────────────────────
@router.patch("/{log_id}", response_model=MilestoneLogOut)
async def update_milestone_log(
    project_id: uuid.UUID,
    log_id: uuid.UUID,
    body: MilestoneLogUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    log = await db.get(MilestoneLog, log_id)
    if not log or str(log.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Record not found")
    if body.work_minutes is not None:
        log.work_minutes = body.work_minutes
    if body.note is not None:
        log.note = body.note
    await db.commit()
    await db.refresh(log)
    return log


# ── 刪除記錄 ───────────────────────────────────────────────────
@router.delete("/{log_id}", status_code=204)
async def delete_milestone_log(
    project_id: uuid.UUID,
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    log = await db.get(MilestoneLog, log_id)
    if not log or str(log.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Record not found")
    await db.delete(log)
    await db.commit()


# ── 供 tasks.py 呼叫的輔助函式 ────────────────────────────────
async def record_task_completion(
    task_id: uuid.UUID,
    task_title: str,
    project_id: uuid.UUID,
    completed_by: uuid.UUID,
    completed_by_name: str,
    db: AsyncSession,
) -> None:
    """任務狀態變為 done 時呼叫，自動建立 milestone_log。"""
    log = MilestoneLog(
        project_id=project_id,
        task_id=task_id,
        task_title=task_title,
        completed_by=completed_by,
        completed_by_name=completed_by_name,
        completed_at=datetime.now(UTC),
    )
    db.add(log)
