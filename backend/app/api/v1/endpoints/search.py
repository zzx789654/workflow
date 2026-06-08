from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.daily_task import DailyTask
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/search", tags=["search"])

_MAX_Q_LEN = 200


@router.get("/")
async def search(
    q: str = Query(..., min_length=1, max_length=_MAX_Q_LEN),
    type: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = q.strip()
    uid = current_user.id
    # Escape LIKE special chars so user input is treated literally
    q_escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{q_escaped}%"
    results: list[dict] = []

    # 使用者可見的專案 IDs
    if current_user.role.value == "admin":
        proj_q = select(Project.id).where(Project.is_archived == False)
    else:
        proj_q = select(ProjectMember.project_id).where(ProjectMember.user_id == uid)
    proj_result = await db.execute(proj_q)
    project_ids = [r[0] for r in proj_result.all()]

    # 搜尋專案
    _ESC = "\\"
    if type in ("all", "project"):
        p_result = await db.execute(
            select(Project)
            .where(
                Project.id.in_(project_ids),
                Project.name.ilike(pattern, escape=_ESC),
            )
            .limit(10)
        )
        for p in p_result.scalars().all():
            results.append(
                {
                    "type": "project",
                    "id": str(p.id),
                    "title": p.name,
                    "description": p.description,
                    "project_id": str(p.id),
                    "project_name": p.name,
                    "status": None,
                    "priority": None,
                }
            )

    # 搜尋任務
    if type in ("all", "task"):
        t_result = await db.execute(
            select(Task)
            .options(selectinload(Task.project))
            .where(
                Task.project_id.in_(project_ids),
                Task.title.ilike(pattern, escape=_ESC),
            )
            .limit(20)
        )
        for t in t_result.scalars().all():
            results.append(
                {
                    "type": "task",
                    "id": str(t.id),
                    "title": t.title,
                    "description": t.description,
                    "project_id": str(t.project_id),
                    "project_name": t.project.name if t.project else None,
                    "status": t.status,
                    "priority": t.priority,
                }
            )

    # 搜尋日常作業（admin 看所有人，一般使用者只看自己）
    if type in ("all", "daily"):
        from app.models.user import UserRole

        daily_q = select(DailyTask).where(DailyTask.title.ilike(pattern, escape=_ESC))
        if current_user.role != UserRole.admin:
            daily_q = daily_q.where(DailyTask.user_id == uid)
        d_result = await db.execute(daily_q.limit(10))
        for d in d_result.scalars().all():
            results.append(
                {
                    "type": "daily",
                    "id": str(d.id),
                    "title": d.title,
                    "description": d.description,
                    "project_id": None,
                    "project_name": None,
                    "status": d.status,
                    "priority": None,
                }
            )

    return {"results": results, "total": len(results)}
