import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.models.v3_p2_models import ProjectShareLink

router = APIRouter(tags=["public_share"])


async def _check_share_permission(project_id: uuid.UUID, user: User, db: AsyncSession) -> None:
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
                ProjectMember.role.in_([ProjectRole.owner, ProjectRole.manager]),
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Manager or owner role required")


class ShareLinkCreate(BaseModel):
    expires_at: datetime | None = None


@router.post("/projects/{project_id}/share", status_code=201)
async def create_share_link(
    project_id: uuid.UUID,
    body: ShareLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    await _check_share_permission(project_id, current_user, db)

    token = secrets.token_urlsafe(48)[:64]
    link = ProjectShareLink(
        id=uuid.uuid4(),
        project_id=project_id,
        token=token,
        created_by=current_user.id,
        expires_at=body.expires_at,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {
        "token": token,
        "url": f"/api/v1/public/projects/{token}",
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


@router.get("/public/projects/{token}")
async def get_public_project(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    result = await db.execute(
        select(ProjectShareLink).where(
            and_(
                ProjectShareLink.token == token,
                ProjectShareLink.is_active == True,  # noqa: E712
            )
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found or inactive")

    if link.expires_at and link.expires_at < now:
        raise HTTPException(status_code=410, detail="Share link has expired")

    # Load project
    proj_result = await db.execute(select(Project).where(Project.id == link.project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load tasks (read-only)
    tasks_result = await db.execute(select(Task).where(Task.project_id == link.project_id).order_by(Task.position))
    tasks = tasks_result.scalars().all()

    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "color": project.color,
        },
        "tasks": [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority.value,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "progress": t.progress,
            }
            for t in tasks
        ],
    }
