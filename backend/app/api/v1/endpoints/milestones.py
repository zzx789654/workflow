"""
里程碑模組：改為「任務完成自動記錄」。
每當專案中任何任務狀態變為 done，自動建立一筆 milestone_log。
也提供手動更新工時與備註的介面。
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

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
    task_id: Optional[uuid.UUID]
    task_title: str
    completed_by: Optional[uuid.UUID]
    completed_by_name: Optional[str]
    work_minutes: int
    note: Optional[str]
    completed_at: datetime

    model_config = {"from_attributes": True}


class MilestoneLogUpdate(BaseModel):
    work_minutes: Optional[int] = Field(None, ge=0)
    note: Optional[str] = Field(None, max_length=1000)


# ── 列出完成記錄 ───────────────────────────────────────────────
@router.get("/", response_model=list[MilestoneLogOut])
async def list_milestone_logs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(
        select(MilestoneLog)
        .where(MilestoneLog.project_id == project_id)
        .order_by(MilestoneLog.completed_at.desc())
    )
    return result.scalars().all()


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
