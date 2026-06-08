"""F11 — 檔案附件（local volume）"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v4_models import TaskAttachment

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
MAX_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/attachments", tags=["attachments"])
project_files_router = APIRouter(prefix="/projects/{project_id}/files", tags=["attachments"])


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


class AttachmentOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    content_type: str
    file_size: int

    model_config = {"from_attributes": True}


class ProjectFileOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_title: str
    user_id: uuid.UUID
    uploader_name: str
    filename: str
    content_type: str
    file_size: int
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AttachmentOut])
async def list_attachments(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    res = await db.execute(
        select(TaskAttachment).where(TaskAttachment.task_id == task_id).order_by(TaskAttachment.created_at.desc())
    )
    return res.scalars().all()


@router.post("/", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="File type not allowed")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    # Store in task-scoped directory
    task_dir = UPLOAD_DIR / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = Path(file.filename or "file").suffix
    storage_path = task_dir / f"{file_id}{ext}"
    storage_path.write_bytes(content)

    attachment = TaskAttachment(
        task_id=task_id,
        user_id=current_user.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        storage_path=str(storage_path),
    )
    db.add(attachment)
    task_obj = await db.get(Task, task_id)
    if task_obj:
        task_obj.attachment_count = (task_obj.attachment_count or 0) + 1
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{attachment_id}/download")
async def download_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    att = await db.get(TaskAttachment, attachment_id)
    if not att or str(att.task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = Path(att.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(path, filename=att.filename, media_type=att.content_type)


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    att = await db.get(TaskAttachment, attachment_id)
    if not att or str(att.task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    if str(att.user_id) != str(current_user.id) and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete another user's attachment")
    try:
        Path(att.storage_path).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(att)
    task_obj = await db.get(Task, task_id)
    if task_obj and task_obj.attachment_count > 0:
        task_obj.attachment_count -= 1
    await db.commit()


# ── 專案層級：列出所有檔案 ─────────────────────────────────────
@project_files_router.get("/", response_model=list[ProjectFileOut])
async def list_project_files(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    from app.models.user import User as UserModel

    await _check_member(project_id, current_user, db)

    # 聯查 TaskAttachment + Task + User(uploader)
    res = await db.execute(
        select(TaskAttachment)
        .join(Task, TaskAttachment.task_id == Task.id)
        .join(UserModel, TaskAttachment.user_id == UserModel.id)
        .where(Task.project_id == project_id)
        .order_by(TaskAttachment.created_at.desc())
    )
    attachments = res.scalars().all()

    out = []
    for att in attachments:
        task_obj = await db.get(Task, att.task_id)
        uploader = await db.get(UserModel, att.user_id)
        out.append(ProjectFileOut(
            id=att.id,
            task_id=att.task_id,
            task_title=task_obj.title if task_obj else "(已刪除)",
            user_id=att.user_id,
            uploader_name=uploader.display_name if uploader else "(未知)",
            filename=att.filename,
            content_type=att.content_type,
            file_size=att.file_size,
            created_at=att.created_at.isoformat(),
        ))
    return out
