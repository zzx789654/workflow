import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.template import ProjectTemplate, TemplateTask
from app.models.user import User
from app.schemas.project import ProjectOut
from app.schemas.template import (
    ApplyTemplateRequest,
    ProjectTemplateCreate,
    ProjectTemplateOut,
    ProjectTemplateUpdate,
    TemplateTaskCreate,
)

router = APIRouter(prefix="/project-templates", tags=["project-templates"])


async def _load_template(template_id: uuid.UUID, db: AsyncSession) -> ProjectTemplate:
    result = await db.execute(
        select(ProjectTemplate).options(selectinload(ProjectTemplate.tasks)).where(ProjectTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.get("/", response_model=list[ProjectTemplateOut])
async def list_templates(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(ProjectTemplate).options(selectinload(ProjectTemplate.tasks)).order_by(ProjectTemplate.name)
    )
    return result.scalars().all()


@router.post("/", response_model=ProjectTemplateOut, status_code=201)
async def create_template(
    body: ProjectTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = ProjectTemplate(
        name=body.name,
        description=body.description,
        color=body.color,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.flush()
    for i, t in enumerate(body.tasks):
        db.add(
            TemplateTask(
                template_id=tmpl.id,
                title=t.title,
                description=t.description,
                priority=t.priority,
                day_offset_start=t.day_offset_start,
                day_offset_end=t.day_offset_end,
                position=i,
            )
        )
    await db.commit()
    return await _load_template(tmpl.id, db)


@router.get("/{template_id}", response_model=ProjectTemplateOut)
async def get_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    return await _load_template(template_id, db)


@router.patch("/{template_id}", response_model=ProjectTemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body: ProjectTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = await _load_template(template_id, db)
    if tmpl.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tmpl, field, value)
    await db.commit()
    return await _load_template(template_id, db)


@router.put("/{template_id}/tasks", response_model=ProjectTemplateOut)
async def replace_template_tasks(
    template_id: uuid.UUID,
    tasks: Annotated[list[TemplateTaskCreate], Body()],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """完整替換範本的任務清單（先刪全部，再重建）"""
    tmpl = await _load_template(template_id, db)
    if tmpl.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    # 刪除舊任務
    for old_task in list(tmpl.tasks):
        await db.delete(old_task)
    await db.flush()
    # 重建新任務
    for i, t in enumerate(tasks):
        db.add(TemplateTask(
            template_id=tmpl.id,
            title=t.title,
            description=t.description,
            priority=t.priority,
            day_offset_start=t.day_offset_start,
            day_offset_end=t.day_offset_end,
            position=i,
        ))
    await db.commit()
    db.expire_all()  # 清除 SQLAlchemy identity map，強制重新查詢
    return await _load_template(template_id, db)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = await _load_template(template_id, db)
    if tmpl.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    await db.delete(tmpl)
    await db.commit()


@router.post("/{template_id}/apply", response_model=ProjectOut, status_code=201)
async def apply_template(
    template_id: uuid.UUID,
    body: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = await _load_template(template_id, db)
    project = Project(name=body.project_name, description=body.project_description, color=tmpl.color)
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=current_user.id, role=ProjectRole.owner))

    base = date.fromisoformat(body.start_date) if body.start_date else date.today()
    for tt in sorted(tmpl.tasks, key=lambda x: x.position):
        priority_map = {
            "low": TaskPriority.low,
            "medium": TaskPriority.medium,
            "high": TaskPriority.high,
            "urgent": TaskPriority.urgent,
        }
        task = Task(
            project_id=project.id,
            title=tt.title,
            description=tt.description,
            priority=priority_map.get(tt.priority, TaskPriority.medium),
            status=TaskStatus.todo,
            position=tt.position,
            start_date=base + timedelta(days=tt.day_offset_start),
            end_date=(base + timedelta(days=tt.day_offset_end)) if tt.day_offset_end is not None else None,
        )
        db.add(task)
    await db.commit()
    await db.refresh(project)
    return ProjectOut(**project.__dict__, member_count=1)


@router.post("/from-project/{project_id}", response_model=ProjectTemplateOut, status_code=201)
async def create_template_from_project(
    project_id: uuid.UUID,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tmpl = ProjectTemplate(
        name=name,
        description=project.description,
        color=project.color,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.flush()

    tasks_result = await db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.position))
    for i, task in enumerate(tasks_result.scalars().all()):
        db.add(
            TemplateTask(
                template_id=tmpl.id,
                title=task.title,
                description=task.description,
                priority=task.priority.value if task.priority else "medium",
                day_offset_start=0,
                position=i,
            )
        )
    await db.commit()
    return await _load_template(tmpl.id, db)
