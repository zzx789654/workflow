import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_project_membership
from app.db.session import get_db
from app.models.daily_task import DailyTask, DailyTaskArchive
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.schemas.project import (
    AddMemberRequest,
    ProjectCreate,
    ProjectMemberOut,
    ProjectOut,
    ProjectOverviewItem,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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
        # due_date is a Date column — pass the date object, not str().
        await db.execute(update(Task).where(Task.project_id == project_id).values(due_date=project.end_date))
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
    is_admin = current_user.role.value == "admin"

    # admin 可看所有專案；一般使用者只看自己是成員的專案
    membership_result = await db.execute(select(ProjectMember).where(ProjectMember.user_id == uid))
    memberships = {m.project_id: m.role.value for m in membership_result.scalars().all()}

    if is_admin:
        all_result = await db.execute(select(Project))
    else:
        all_result = await db.execute(select(Project).where(Project.id.in_(set(memberships.keys()))))
    all_projects = all_result.scalars().all()

    result_items: list[ProjectOverviewItem] = []
    for p in all_projects:
        total_r = await db.execute(select(func.count()).where(Task.project_id == p.id))
        done_r = await db.execute(select(func.count()).where(Task.project_id == p.id, Task.status == "done"))
        mc_r = await db.execute(select(func.count()).where(ProjectMember.project_id == p.id))
        result_items.append(
            ProjectOverviewItem(
                id=p.id,
                name=p.name,
                description=p.description,
                color=p.color,
                is_archived=p.is_archived,
                start_date=p.start_date,
                end_date=p.end_date,
                member_count=mc_r.scalar() or 0,
                task_total=total_r.scalar() or 0,
                task_done=done_r.scalar() or 0,
                my_role=memberships.get(p.id),
            )
        )

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

    # 封存專案前的擋關與同步搬移
    if update_data.get("is_archived") is True and not project.is_archived:
        # 取得專案下所有任務 ID
        task_ids_result = await db.execute(select(Task.id).where(Task.project_id == project_id))
        task_ids = [r[0] for r in task_ids_result.all()]

        if task_ids:
            # 檢查是否有未完成的關聯日常任務
            blocking_result = await db.execute(
                select(func.count()).where(
                    and_(
                        DailyTask.linked_task_id.in_(task_ids),
                        DailyTask.status.notin_(["done", "cancelled"]),
                    )
                )
            )
            blocking_count = blocking_result.scalar() or 0
            if blocking_count > 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"有 {blocking_count} 筆關聯日常任務尚未完成，請先完成後再封存專案。",
                )

            # 同步搬移所有關聯日常任務到封存表
            linked_result = await db.execute(select(DailyTask).where(DailyTask.linked_task_id.in_(task_ids)))
            linked_tasks = linked_result.scalars().all()
            if linked_tasks:
                archived_at = datetime.now(UTC)
                ids_to_move = []
                for dt in linked_tasks:
                    db.add(
                        DailyTaskArchive(
                            id=dt.id,
                            user_id=dt.user_id,
                            title=dt.title,
                            description=dt.description,
                            status=dt.status.value if hasattr(dt.status, "value") else dt.status,
                            progress=dt.progress,
                            date=dt.date,
                            started_at=dt.started_at,
                            ended_at=dt.ended_at,
                            notify_at=dt.notify_at,
                            work_minutes=dt.work_minutes,
                            linked_task_id=dt.linked_task_id,
                            created_at=dt.created_at,
                            updated_at=dt.updated_at,
                            archived_at=archived_at,
                        )
                    )
                    ids_to_move.append(dt.id)
                await db.flush()
                await db.execute(delete(DailyTask).where(DailyTask.id.in_(ids_to_move)))

    for field, value in update_data.items():
        setattr(project, field, value)
    # When end_date is updated, propagate to all tasks in the project.
    # due_date is a Date column — pass the date object, not str(), or asyncpg raises DataError.
    if "end_date" in update_data and update_data["end_date"]:
        await db.execute(update(Task).where(Task.project_id == project_id).values(due_date=update_data["end_date"]))
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
