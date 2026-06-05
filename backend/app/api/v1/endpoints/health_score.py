"""F23 — 專案健康指標 Health Score"""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v4_models import ProjectHealthScore

router = APIRouter(prefix="/projects/{project_id}/health", tags=["health_score"])


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


async def _compute_health(project_id: uuid.UUID, db: AsyncSession) -> dict:
    today = date.today().isoformat()

    # Total vs overdue tasks
    total_res = await db.execute(select(func.count()).where(Task.project_id == project_id, Task.status != "done"))
    total_open = total_res.scalar() or 0

    overdue_res = await db.execute(
        select(func.count()).where(and_(Task.project_id == project_id, Task.status != "done", Task.due_date < today))
    )
    overdue = overdue_res.scalar() or 0
    overdue_ratio = round(overdue / total_open * 100, 2) if total_open > 0 else 0.0

    active_member_ratio = 80.0  # simplified: full member tracking is a future enhancement

    # Score formula: 100 - overdue_ratio * 0.6 - (1 - milestone_rate) * 20
    milestone_rate = 85.0  # simplified: assume 85% without milestone table join
    score = max(0, int(100 - overdue_ratio * 0.6 - (100 - milestone_rate) * 0.2 - (100 - active_member_ratio) * 0.2))

    return {
        "score": score,
        "overdue_ratio": overdue_ratio,
        "milestone_rate": milestone_rate,
        "active_member_ratio": active_member_ratio,
    }


class HealthOut(BaseModel):
    project_id: uuid.UUID
    score: int
    overdue_ratio: float
    milestone_rate: float
    active_member_ratio: float
    calculated_at: datetime
    label: str


@router.get("", response_model=HealthOut)
async def get_health(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)

    # Use cached if recent (< 1h)
    cached = await db.execute(select(ProjectHealthScore).where(ProjectHealthScore.project_id == project_id))
    cached_row = cached.scalar_one_or_none()
    now = datetime.now(UTC)
    if cached_row and (now - cached_row.calculated_at).seconds < 3600:
        metrics = {
            "score": cached_row.score,
            "overdue_ratio": float(cached_row.overdue_ratio),
            "milestone_rate": float(cached_row.milestone_rate),
            "active_member_ratio": float(cached_row.active_member_ratio),
            "calculated_at": cached_row.calculated_at,
        }
    else:
        metrics = await _compute_health(project_id, db)
        metrics["calculated_at"] = now
        if cached_row:
            cached_row.score = metrics["score"]
            cached_row.overdue_ratio = metrics["overdue_ratio"]
            cached_row.milestone_rate = metrics["milestone_rate"]
            cached_row.active_member_ratio = metrics["active_member_ratio"]
            cached_row.calculated_at = now
        else:
            db.add(
                ProjectHealthScore(
                    project_id=project_id,
                    **{k: v for k, v in metrics.items() if k != "calculated_at"},
                    calculated_at=now,
                )
            )
        await db.commit()

    score = metrics["score"]
    label = "優良" if score >= 80 else ("一般" if score >= 60 else "需改善")
    return HealthOut(project_id=project_id, label=label, **metrics)
