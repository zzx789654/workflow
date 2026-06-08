import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v3_models import Notification
from app.websocket.manager import manager

router = APIRouter(prefix="/notifications", tags=["notifications"])

_MENTION_RE = re.compile(r"@(\S+)")


async def _notify_task_progress(
    task: Task,
    actor: User,
    db: AsyncSession,
    old_status: str | None = None,
    new_status: str | None = None,
    old_progress: int | None = None,
    new_progress: int | None = None,
):
    """當任務 status 或 progress 有異動時，通知所有專案成員（排除操作者自己）。"""
    parts = []
    if old_status and new_status and old_status != new_status:
        status_label = {
            "todo": "待處理",
            "in_progress": "進行中",
            "review": "審核中",
            "done": "已完成",
        }
        parts.append(
            f"狀態從「{status_label.get(old_status, old_status)}」更新為「{status_label.get(new_status, new_status)}」"
        )
    if old_progress is not None and new_progress is not None and old_progress != new_progress:
        parts.append(f"進度從 {old_progress}% 更新為 {new_progress}%")
    if not parts:
        return

    message = f"{actor.display_name} 將任務「{task.title}」的{'、'.join(parts)}"

    # 取得專案所有成員（排除操作者）
    members_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id != actor.id,
        )
    )
    members = members_result.scalars().all()

    ws_payload = {
        "type": "notification",
        "message": message,
        "ref_id": str(task.id),
        "ref_type": "task",
    }

    for member in members:
        notif = Notification(
            user_id=member.user_id,
            actor_id=actor.id,
            type="task_progress",
            ref_id=task.id,
            ref_type="task",
            message=message,
        )
        db.add(notif)
        await db.flush()
        # 廣播到個人通知頻道（全域 WS）
        await manager.broadcast(f"__notif_{member.user_id}", ws_payload)
        # 同時廣播到專案頻道（讓在該專案頁面的使用者也能即時更新）
        await manager.broadcast(str(task.project_id), {**ws_payload, "user_id": str(member.user_id)})


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

    # 批次查出 ref_type=task 的 project_id
    task_ref_ids = [n.ref_id for n in notifs if n.ref_type == "task" and n.ref_id]
    project_id_map: dict[str, str] = {}
    if task_ref_ids:
        task_rows = await db.execute(select(Task.id, Task.project_id).where(Task.id.in_(task_ref_ids)))
        for tid, pid in task_rows.all():
            project_id_map[str(tid)] = str(pid)

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
                "project_id": project_id_map.get(str(n.ref_id)) if n.ref_id else None,
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
