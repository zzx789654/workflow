import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.v3_p2_models import TaskAttachment

UPLOAD_DIR = Path("/tmp/uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/attachments", tags=["attachments"])
file_router = APIRouter(prefix="/attachments", tags=["attachments"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


async def _get_task(task_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


class AttachmentOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    file_path: str
    file_size: int | None
    content_type: str | None
    created_at: object

    model_config = {"from_attributes": True}


@router.post("/", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    await _get_task(task_id, project_id, db)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{file.filename}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(contents)

    attachment = TaskAttachment(
        task_id=task_id,
        user_id=current_user.id,
        filename=file.filename or safe_name,
        file_path=str(dest),
        file_size=len(contents),
        content_type=file.content_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/", response_model=list[AttachmentOut])
async def list_attachments(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    await _get_task(task_id, project_id, db)
    result = await db.execute(
        select(TaskAttachment).where(TaskAttachment.task_id == task_id).order_by(TaskAttachment.created_at)
    )
    return result.scalars().all()


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    await _get_task(task_id, project_id, db)
    attachment = await db.get(TaskAttachment, attachment_id)
    if not attachment or str(attachment.task_id) != str(task_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    if str(attachment.user_id) != str(current_user.id) and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete another user's attachment")
    # Remove file from disk
    file_path = Path(attachment.file_path)
    if file_path.exists():
        file_path.unlink()
    await db.delete(attachment)
    await db.commit()


@file_router.get("/{attachment_id}/file")
async def download_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = await db.get(TaskAttachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(file_path),
        filename=attachment.filename,
        media_type=attachment.content_type or "application/octet-stream",
    )
