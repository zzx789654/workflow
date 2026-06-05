"""F14 — Emoji 反應"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.user import User
from app.models.v4_models import CommentReaction
from app.websocket.manager import manager

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/comments/{comment_id}/reactions", tags=["reactions"])

ALLOWED_EMOJIS = {"👍", "👎", "❤️", "😂", "🎉", "🚀", "👀", "🔥", "✅", "💯"}


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


class ReactionToggle(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)


class ReactionOut(BaseModel):
    id: uuid.UUID
    comment_id: uuid.UUID
    user_id: uuid.UUID
    emoji: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ReactionOut])
async def list_reactions(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    res = await db.execute(select(CommentReaction).where(CommentReaction.comment_id == comment_id))
    return res.scalars().all()


@router.post("/toggle", status_code=200)
async def toggle_reaction(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: ReactionToggle,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail=f"Emoji not allowed. Allowed: {sorted(ALLOWED_EMOJIS)}")
    await _check_member(project_id, current_user, db)

    existing = await db.execute(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == current_user.id,
            CommentReaction.emoji == body.emoji,
        )
    )
    existing_row = existing.scalar_one_or_none()

    if existing_row:
        await db.delete(existing_row)
        await db.commit()
        action = "removed"
    else:
        reaction = CommentReaction(
            comment_id=comment_id,
            user_id=current_user.id,
            emoji=body.emoji,
        )
        db.add(reaction)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Reaction already exists")
        action = "added"

    # Broadcast via WS
    await manager.broadcast(
        str(project_id),
        {
            "type": "reaction_updated",
            "task_id": str(task_id),
            "comment_id": str(comment_id),
            "user_id": str(current_user.id),
            "emoji": body.emoji,
            "action": action,
        },
    )

    # Return summary
    res = await db.execute(select(CommentReaction).where(CommentReaction.comment_id == comment_id))
    reactions = res.scalars().all()
    summary: dict[str, list[str]] = {}
    for r in reactions:
        summary.setdefault(r.emoji, []).append(str(r.user_id))

    return {"action": action, "summary": summary}
