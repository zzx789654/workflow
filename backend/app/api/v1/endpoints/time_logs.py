import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v3_models import TimeLog

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/time-logs", tags=["time_logs"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


class TimeLogStart(BaseModel):
    note: str | None = Field(None, max_length=500)


class TimeLogManual(BaseModel):
    minutes: int = Field(..., ge=1, le=1440)
    note: str | None = Field(None, max_length=500)
    started_at: datetime | None = None


class TimeLogOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    minutes: int
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TimeLogOut])
async def list_time_logs(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(TimeLog).where(TimeLog.task_id == task_id).order_by(TimeLog.started_at.desc()))
    return result.scalars().all()


@router.post("/start", response_model=TimeLogOut, status_code=201)
async def start_timer(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TimeLogStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    # 確認沒有未結束的計時器
    running = await db.execute(
        select(TimeLog).where(
            TimeLog.task_id == task_id,
            TimeLog.user_id == current_user.id,
            TimeLog.ended_at == None,  # noqa: E711
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Timer already running for this task")
    log = TimeLog(
        task_id=task_id,
        user_id=current_user.id,
        started_at=datetime.now(UTC),
        note=body.note,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.patch("/{log_id}/stop", response_model=TimeLogOut)
async def stop_timer(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    log = await db.get(TimeLog, log_id)
    if not log or str(log.task_id) != str(task_id) or str(log.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Timer not found")
    if log.ended_at:
        raise HTTPException(status_code=400, detail="Timer already stopped")
    now = datetime.now(UTC)
    log.ended_at = now
    elapsed = int((now - log.started_at).total_seconds() / 60)
    log.minutes = max(elapsed, 1)
    await db.commit()
    await db.refresh(log)
    return log


@router.post("/manual", response_model=TimeLogOut, status_code=201)
async def log_manual(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TimeLogManual,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    started = body.started_at or datetime.now(UTC)
    log = TimeLog(
        task_id=task_id,
        user_id=current_user.id,
        started_at=started,
        ended_at=started,
        minutes=body.minutes,
        note=body.note,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.delete("/{log_id}", status_code=204)
async def delete_log(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    log = await db.get(TimeLog, log_id)
    if not log or str(log.task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Log not found")
    if str(log.user_id) != str(current_user.id) and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete another user's log")
    await db.delete(log)
    await db.commit()


# 時間報表：GET /api/v1/time-logs/report
report_router = APIRouter(prefix="/time-logs", tags=["time_logs"])


@report_router.get("/report")
async def time_report(
    project_id: uuid.UUID | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = []
    if project_id:
        # Verify caller is a member of the requested project
        if current_user.role.value != "admin":
            membership = await db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == current_user.id,
                )
            )
            if not membership.scalar_one_or_none():
                raise HTTPException(status_code=403, detail="Not a project member")
        filters.append(Task.project_id == project_id)
    else:
        # Without a project filter, restrict to projects the user belongs to
        if current_user.role.value != "admin":
            proj_result = await db.execute(
                select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
            )
            visible_ids = [r[0] for r in proj_result.all()]
            filters.append(Task.project_id.in_(visible_ids))
    if user_id:
        filters.append(TimeLog.user_id == user_id)
    else:
        filters.append(TimeLog.user_id == current_user.id)

    from app.models.project import Project
    from app.models.user import User as UserModel

    result = await db.execute(
        select(
            TimeLog.user_id,
            UserModel.display_name.label("user_name"),
            Task.project_id,
            Project.name.label("project_name"),
            func.sum(TimeLog.minutes).label("total_minutes"),
        )
        .join(Task, TimeLog.task_id == Task.id)
        .join(UserModel, TimeLog.user_id == UserModel.id)
        .join(Project, Task.project_id == Project.id)
        .where(and_(*filters) if filters else True)
        .group_by(TimeLog.user_id, UserModel.display_name, Task.project_id, Project.name)
    )
    rows = result.all()
    return {
        "report": [
            {
                "user_id": str(r.user_id),
                "user_name": r.user_name,
                "project_id": str(r.project_id),
                "project_name": r.project_name,
                "total_minutes": r.total_minutes,
                "total_hours": round(r.total_minutes / 60, 1),
            }
            for r in rows
        ]
    }
