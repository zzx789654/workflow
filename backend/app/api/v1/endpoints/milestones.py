import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.milestone import Milestone
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.milestone import MilestoneCreate, MilestoneOut, MilestoneUpdate

router = APIRouter(prefix="/projects/{project_id}/milestones", tags=["milestones"])


async def _check_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


@router.get("/", response_model=list[MilestoneOut])
async def list_milestones(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.due_date))
    milestones = result.scalars().all()
    out = []
    for m in milestones:
        count_result = await db.execute(select(func.count()).where(Task.milestone_id == m.id))
        out.append(MilestoneOut(**m.__dict__, task_count=count_result.scalar()))
    return out


@router.post("/", response_model=MilestoneOut, status_code=201)
async def create_milestone(
    project_id: uuid.UUID,
    body: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    milestone = Milestone(project_id=project_id, **body.model_dump())
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneOut(**milestone.__dict__, task_count=0)


@router.patch("/{milestone_id}", response_model=MilestoneOut)
async def update_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project_id))
    milestone = result.scalar_one_or_none()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(milestone, field, value)
    await db.commit()
    await db.refresh(milestone)
    count_result = await db.execute(select(func.count()).where(Task.milestone_id == milestone_id))
    return MilestoneOut(**milestone.__dict__, task_count=count_result.scalar())


@router.delete("/{milestone_id}", status_code=204)
async def delete_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_member(project_id, current_user, db)
    result = await db.execute(select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project_id))
    milestone = result.scalar_one_or_none()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    await db.delete(milestone)
    await db.commit()
