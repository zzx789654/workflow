import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.v3_p2_models import Announcement, AnnouncementRead

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    title: str
    content: str | None = None
    expires_at: datetime | None = None


@router.get("/")
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC)
    result = await db.execute(
        select(Announcement)
        .where(
            and_(
                Announcement.is_active == True,  # noqa: E712
                or_(Announcement.expires_at == None, Announcement.expires_at > now),  # noqa: E711
            )
        )
        .order_by(Announcement.created_at.desc())
    )
    announcements = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "title": a.title,
            "content": a.content,
            "author_id": str(a.author_id),
            "is_active": a.is_active,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in announcements
    ]


@router.post("/", status_code=201)
async def create_announcement(
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    announcement = Announcement(
        id=uuid.uuid4(),
        title=body.title,
        content=body.content,
        author_id=current_user.id,
        expires_at=body.expires_at,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return {
        "id": str(announcement.id),
        "title": announcement.title,
        "content": announcement.content,
        "author_id": str(announcement.author_id),
        "is_active": announcement.is_active,
        "expires_at": announcement.expires_at.isoformat() if announcement.expires_at else None,
        "created_at": announcement.created_at.isoformat(),
    }


@router.post("/{announcement_id}/read", status_code=200)
async def mark_read(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Announcement not found")

    existing = await db.execute(
        select(AnnouncementRead).where(
            and_(AnnouncementRead.announcement_id == announcement_id, AnnouncementRead.user_id == current_user.id)
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "already_read"}

    read = AnnouncementRead(
        id=uuid.uuid4(),
        announcement_id=announcement_id,
        user_id=current_user.id,
    )
    db.add(read)
    await db.commit()
    return {"status": "marked_read"}
