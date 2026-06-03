import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.project import ProjectRole
from app.models.user import User
from app.models.v3_models import ProjectField, TaskFieldValue

router = APIRouter(prefix="/projects/{project_id}", tags=["custom_fields"])

_VALID_TYPES = {"text", "number", "date", "select"}
_MAX_FIELDS = 10


async def _require_manager(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.manager)


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    await require_project_membership(project_id, user, db, min_role=ProjectRole.viewer)


class FieldCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    field_type: str = Field("text")
    options: list[str] | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.field_type not in _VALID_TYPES:
            raise ValueError(f"field_type must be one of {_VALID_TYPES}")


class FieldOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    field_type: str
    options: Any
    position: int

    model_config = {"from_attributes": True}


class FieldValueSet(BaseModel):
    field_id: uuid.UUID
    value: str | None = None


@router.get("/fields", response_model=list[FieldOut])
async def list_fields(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(
        select(ProjectField).where(ProjectField.project_id == project_id).order_by(ProjectField.position)
    )
    return result.scalars().all()


@router.post("/fields", response_model=FieldOut, status_code=201)
async def create_field(
    project_id: uuid.UUID,
    body: FieldCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_manager(project_id, current_user, db)
    count_result = await db.execute(select(func.count()).where(ProjectField.project_id == project_id))
    if (count_result.scalar() or 0) >= _MAX_FIELDS:
        raise HTTPException(status_code=400, detail=f"Maximum {_MAX_FIELDS} fields per project")
    pos_result = await db.execute(select(func.max(ProjectField.position)).where(ProjectField.project_id == project_id))
    pos = (pos_result.scalar() or 0) + 1
    options = {"choices": body.options} if body.options else None
    field = ProjectField(
        project_id=project_id, name=body.name, field_type=body.field_type, options=options, position=pos
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field


@router.delete("/fields/{field_id}", status_code=204)
async def delete_field(
    project_id: uuid.UUID,
    field_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_manager(project_id, current_user, db)
    field = await db.get(ProjectField, field_id)
    if not field or str(field.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Field not found")
    await db.delete(field)
    await db.commit()


@router.get("/tasks/{task_id}/field-values")
async def get_field_values(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(TaskFieldValue).where(TaskFieldValue.task_id == task_id))
    return [{"field_id": str(v.field_id), "value": v.value} for v in result.scalars().all()]


@router.put("/tasks/{task_id}/field-values", status_code=200)
async def set_field_values(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    values: list[FieldValueSet],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    for fv in values:
        existing = await db.execute(
            select(TaskFieldValue).where(TaskFieldValue.task_id == task_id, TaskFieldValue.field_id == fv.field_id)
        )
        rec = existing.scalar_one_or_none()
        if rec:
            rec.value = fv.value
        else:
            db.add(TaskFieldValue(task_id=task_id, field_id=fv.field_id, value=fv.value))
    await db.commit()
    return {"ok": True}
