import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskComment
from app.models.user import User
from app.models.v3_p2_models import CommentReaction

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/comments", tags=["reactions"])


async def _get_comment(
    project_id: uuid.UUID, task_id: uuid.UUID, comment_id: uuid.UUID, db: AsyncSession
) -> TaskComment:
    result = await db.execute(
        select(TaskComment)
        .join(Task, Task.id == TaskComment.task_id)
        .where(and_(TaskComment.id == comment_id, Task.id == task_id, Task.project_id == project_id))
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found")
    return c


class ReactionBody(BaseModel):
    emoji: str


@router.post("/{comment_id}/reactions", status_code=201)
async def add_reaction(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: ReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_comment(project_id, task_id, comment_id, db)
    existing = await db.execute(
        select(CommentReaction).where(
            and_(
                CommentReaction.comment_id == comment_id,
                CommentReaction.user_id == current_user.id,
                CommentReaction.emoji == body.emoji,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Reaction already exists")
    reaction = CommentReaction(comment_id=comment_id, user_id=current_user.id, emoji=body.emoji)
    db.add(reaction)
    await db.commit()
    await db.refresh(reaction)
    return {"id": str(reaction.id), "comment_id": str(comment_id), "emoji": body.emoji, "user_id": str(current_user.id)}


@router.delete("/{comment_id}/reactions/{emoji}", status_code=204)
async def remove_reaction(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_comment(project_id, task_id, comment_id, db)
    result = await db.execute(
        select(CommentReaction).where(
            and_(
                CommentReaction.comment_id == comment_id,
                CommentReaction.user_id == current_user.id,
                CommentReaction.emoji == emoji,
            )
        )
    )
    reaction = result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    await db.delete(reaction)
    await db.commit()
