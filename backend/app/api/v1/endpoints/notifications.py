import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task
from app.models.user import User
from app.models.v3_models import Notification
from app.websocket.manager import manager

router = APIRouter(prefix="/notifications", tags=["notifications"])

_MENTION_RE = re.compile(r"@(\S+)")


async def _parse_and_notify(
    content: str,
    actor: User,
    task: Task,
    db: AsyncSession,
):
    """Parse @mention in comment content and create notifications."""
    mentions = _MENTION_RE.findall(content)
    if not mentions:
        return
    result = await db.execute(select(User).where(User.is_active == True))
    all_users = result.scalars().all()
    name_map = {u.display_name.lower(): u for u in all_users}

    for m in mentions:
        target = name_map.get(m.lower())
        if not target or target.id == actor.id:
            continue
        notif = Notification(
            user_id=target.id,
            actor_id=actor.id,
            type="mention",
            ref_id=task.id,
            ref_type="task",
            message=f"{actor.display_name} 在任務「{task.title}」中提及了你",
        )
        db.add(notif)
        await db.flush()
        # WebSocket 推播
        await manager.broadcast(
            str(task.project_id),
            {
                "type": "notification",
                "user_id": str(target.id),
                "message": notif.message,
                "ref_id": str(task.id),
            },
        )


@router.get("/")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = result.scalars().all()
    unread = sum(1 for n in notifs if n.read_at is None)
    return {
        "unread": unread,
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "message": n.message,
                "ref_id": str(n.ref_id) if n.ref_id else None,
                "ref_type": n.ref_type,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ],
    }


@router.patch("/{notif_id}/read", status_code=200)
async def mark_read(
    notif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = await db.get(Notification, notif_id)
    if not notif or str(notif.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}


@router.patch("/read-all", status_code=200)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC)
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at == None)  # noqa: E711
        .values(read_at=now)
    )
    await db.commit()
    return {"ok": True}
