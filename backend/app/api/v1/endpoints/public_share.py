"""F22 — 訪客分享連結 Public Share"""
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v4_models import ProjectShareLink

router = APIRouter(prefix="/projects/{project_id}/share", tags=["public_share"])
public_router = APIRouter(prefix="/public", tags=["public_share"])


async def _check_manager(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role.in_(["owner", "manager"]),
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Manager access required")


class ShareCreate(BaseModel):
    expires_at: datetime | None = None


class ShareOut(BaseModel):
    id: uuid.UUID
    token: str
    project_id: uuid.UUID
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/links", response_model=list[ShareOut])
async def list_share_links(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    res = await db.execute(
        select(ProjectShareLink).where(ProjectShareLink.project_id == project_id)
    )
    return res.scalars().all()


@router.post("/links", response_model=ShareOut, status_code=201)
async def create_share_link(
    project_id: uuid.UUID,
    body: ShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    token = secrets.token_urlsafe(48)[:64]
    link = ProjectShareLink(
        project_id=project_id,
        token=token,
        expires_at=body.expires_at,
        created_by=current_user.id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/links/{link_id}", status_code=204)
async def revoke_share_link(
    project_id: uuid.UUID,
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    link = await db.get(ProjectShareLink, link_id)
    if not link or str(link.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Link not found")
    link.is_active = False
    await db.commit()


@public_router.get("/projects/{token}")
async def public_project_view(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    res = await db.execute(
        select(ProjectShareLink).where(
            and_(
                ProjectShareLink.token == token,
                ProjectShareLink.is_active == True,
            )
        )
    )
    link = res.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    if link.expires_at and link.expires_at < now:
        raise HTTPException(status_code=410, detail="Share link has expired")

    project = await db.get(Project, link.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks_res = await db.execute(
        select(Task).where(Task.project_id == link.project_id).order_by(Task.position)
    )
    tasks = tasks_res.scalars().all()

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
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date,
                "progress": t.progress,
            }
            for t in tasks
        ],
    }
