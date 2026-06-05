"""F17 — 公告板 Announcements"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.v4_models import Announcement, AnnouncementRead

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    expires_at: datetime | None = None


class AnnouncementOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    content: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    is_read: bool = False

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AnnouncementOut])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC)
    res = await db.execute(
        select(Announcement)
        .where(
            and_(
                Announcement.is_active == True,
                or_(Announcement.expires_at is None, Announcement.expires_at > now),
            )
        )
        .order_by(Announcement.created_at.desc())
    )
    announcements = res.scalars().all()

    # Check read status
    read_res = await db.execute(
        select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == current_user.id)
    )
    read_ids = {str(r[0]) for r in read_res.all()}

    return [
        AnnouncementOut(
            **{
                "id": a.id,
                "author_id": a.author_id,
                "title": a.title,
                "content": a.content,
                "is_active": a.is_active,
                "expires_at": a.expires_at,
                "created_at": a.created_at,
                "is_read": str(a.id) in read_ids,
            }
        )
        for a in announcements
    ]


@router.post("/", response_model=AnnouncementOut, status_code=201)
async def create_announcement(
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    ann = Announcement(
        author_id=current_user.id,
        title=body.title,
        content=body.content,
        expires_at=body.expires_at,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return AnnouncementOut(**{**ann.__dict__, "is_read": False})


@router.post("/{announcement_id}/read", status_code=200)
async def mark_read(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    read = AnnouncementRead(announcement_id=announcement_id, user_id=current_user.id)
    db.add(read)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return {"status": "ok"}


@router.delete("/{announcement_id}", status_code=204)
async def deactivate_announcement(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    ann = await db.get(Announcement, announcement_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    ann.is_active = False
    await db.commit()
