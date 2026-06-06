import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.schemas.project import AddMemberRequest, ProjectCreate, ProjectMemberOut, ProjectOut, ProjectOverviewItem, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def require_project_role(
    project_id: uuid.UUID, user: User, db: AsyncSession, min_role: ProjectRole = ProjectRole.viewer
) -> ProjectMember:
    role_order = [ProjectRole.viewer, ProjectRole.member, ProjectRole.manager, ProjectRole.owner]
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    if user.role.value == "admin":
        return membership
    if not membership:
        raise HTTPException(status_code=403, detail="Not a project member")
    if role_order.index(membership.role) < role_order.index(min_role):
        raise HTTPException(status_code=403, detail="Insufficient project role")
    return membership


@router.post("/", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    member = ProjectMember(project_id=project.id, user_id=current_user.id, role=ProjectRole.owner)
    db.add(member)
    await db.commit()
    await db.refresh(project)
    return ProjectOut(**project.__dict__, member_count=1)


@router.post("/{project_id}/apply-deadline", status_code=204)
async def apply_project_deadline_to_tasks(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Propagate project end_date to all tasks in the project."""
    await require_project_membership(project_id, current_user, db, ProjectRole.manager)
    project = await get_project_or_404(project_id, db)
    if project.end_date:
        await db.execute(update(Task).where(Task.project_id == project_id).values(due_date=str(project.end_date)))
        await db.commit()


@router.get("/", response_model=list[ProjectOut])
async def list_projects(
    archived: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value == "admin":
        result = await db.execute(select(Project).where(Project.is_archived == archived))
    else:
        subq = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
        result = await db.execute(select(Project).where(Project.id.in_(subq), Project.is_archived == archived))
    projects = result.scalars().all()
    out = []
    for p in projects:
        count_result = await db.execute(select(func.count()).where(ProjectMember.project_id == p.id))
        out.append(ProjectOut(**p.__dict__, member_count=count_result.scalar()))
    return out


@router.get("/overview", response_model=list[ProjectOverviewItem])
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    if current_user.role.value == "admin":
        visible_result = await db.execute(select(Project.id))
    else:
        visible_result = await db.execute(
            select(ProjectMember.project_id).where(ProjectMember.user_id == uid)
        )
    visible_ids = {r[0] for r in visible_result.all()}

    all_result = await db.execute(select(Project).where(Project.id.in_(visible_ids)))
    all_projects = all_result.scalars().all()

    result_items: list[ProjectOverviewItem] = []
    for p in all_projects:
        total_r = await db.execute(select(func.count()).where(Task.project_id == p.id))
        done_r = await db.execute(select(func.count()).where(Task.project_id == p.id, Task.status == "done"))
        mc_r = await db.execute(select(func.count()).where(ProjectMember.project_id == p.id))
        result_items.append(ProjectOverviewItem(
            id=p.id, name=p.name, description=p.description, color=p.color,
            is_archived=p.is_archived, start_date=p.start_date, end_date=p.end_date,
            member_count=mc_r.scalar() or 0,
            task_total=total_r.scalar() or 0,
            task_done=done_r.scalar() or 0,
        ))

    result_items.sort(key=lambda x: (x.is_archived, x.name))
    return result_items


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await require_project_membership(project_id, current_user, db)
    project = await get_project_or_404(project_id, db)
    count_result = await db.execute(select(func.count()).where(ProjectMember.project_id == project_id))
    return ProjectOut(**project.__dict__, member_count=count_result.scalar())


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_project_membership(project_id, current_user, db, ProjectRole.manager)
    project = await get_project_or_404(project_id, db)
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    # When end_date is updated, propagate to all tasks in the project
    if "end_date" in update_data and update_data["end_date"]:
        await db.execute(
            update(Task).where(Task.project_id == project_id).values(due_date=str(update_data["end_date"]))
        )
    await db.commit()
    await db.refresh(project)
    count_result = await db.execute(select(func.count()).where(ProjectMember.project_id == project_id))
    return ProjectOut(**project.__dict__, member_count=count_result.scalar())


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await require_project_membership(project_id, current_user, db, ProjectRole.owner)
    project = await get_project_or_404(project_id, db)
    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_members(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    await require_project_membership(project_id, current_user, db)
    result = await db.execute(
        select(ProjectMember).options(selectinload(ProjectMember.user)).where(ProjectMember.project_id == project_id)
    )
    return result.scalars().all()


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    body: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_project_membership(project_id, current_user, db, ProjectRole.manager)
    existing = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == body.user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already a member")
    member = ProjectMember(project_id=project_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.commit()
    result = await db.execute(
        select(ProjectMember).options(selectinload(ProjectMember.user)).where(ProjectMember.id == member.id)
    )
    return result.scalar_one()


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_project_membership(project_id, current_user, db, ProjectRole.manager)
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == ProjectRole.owner:
        raise HTTPException(status_code=400, detail="Cannot remove project owner")
    await db.delete(member)
    await db.commit()


@router.patch("/{project_id}/members/{user_id}/role", response_model=ProjectMemberOut)
async def update_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: ProjectRole,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager 以上可調整其他成員的專案角色（不能改 owner，不能改自己）。"""
    await require_project_membership(project_id, current_user, db, ProjectRole.manager)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="無法修改自己的角色")
    result = await db.execute(
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == ProjectRole.owner:
        raise HTTPException(status_code=400, detail="無法修改 Owner 的角色")
    member.role = role
    await db.commit()
    await db.refresh(member)
    return member
