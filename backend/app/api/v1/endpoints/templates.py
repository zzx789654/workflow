import uuid
from datetime import date, timedelta
from typing import Annotated


def _next_workday(d: date) -> date:
    """Advance d to the next weekday if it lands on Sat/Sun."""
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d += timedelta(days=1)
    return d


def _add_working_days(start: date, working_days: int) -> date:
    """Return the date after adding N working days (Mon–Fri) to start.
    start itself is counted as day 1 if it is a workday."""
    if working_days <= 0:
        return _next_workday(start)
    d = _next_workday(start)
    remaining = working_days - 1
    while remaining > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            remaining -= 1
    return d

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
                depends_on_position=t.depends_on_position,
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
        db.add(
            TemplateTask(
                template_id=tmpl.id,
                title=t.title,
                description=t.description,
                priority=t.priority,
                day_offset_start=t.day_offset_start,
                day_offset_end=t.day_offset_end,
                position=i,
                depends_on_position=t.depends_on_position,
            )
        )
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
    project = Project(
        name=body.project_name,
        description=body.project_description,
        color=tmpl.color,
        start_date=date.fromisoformat(body.start_date) if body.start_date else None,
        end_date=date.fromisoformat(body.end_date) if body.end_date else None,
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=current_user.id, role=ProjectRole.owner))

    raw_base = date.fromisoformat(body.start_date) if body.start_date else date.today()
    # Ensure project start is a workday
    base = _next_workday(raw_base)
    sorted_tasks = sorted(tmpl.tasks, key=lambda x: x.position)
    priority_map = {
        "low": TaskPriority.low,
        "medium": TaskPriority.medium,
        "high": TaskPriority.high,
        "urgent": TaskPriority.urgent,
    }
    # Walk tasks in order, tracking current cursor (next available workday)
    # position_to_task maps template position → created Task (for dependency wiring)
    cursor = base
    position_to_task: dict[int, Task] = {}
    for tt in sorted_tasks:
        duration = (
            (tt.day_offset_end - tt.day_offset_start + 1)
            if tt.day_offset_end is not None
            else 1
        )
        task_start = cursor
        task_end = _add_working_days(cursor, duration)
        cursor = task_end + timedelta(days=1)
        cursor = _next_workday(cursor)
        task = Task(
            project_id=project.id,
            title=tt.title,
            description=tt.description,
            priority=priority_map.get(tt.priority, TaskPriority.medium),
            status=TaskStatus.todo,
            position=tt.position,
            start_date=task_start,
            end_date=task_end,
            due_date=task_end,
        )
        db.add(task)
        await db.flush()  # get task.id before wiring deps
        position_to_task[tt.position] = task

    # Wire task dependencies from depends_on_position
    from app.models.v3_models import TaskDependency
    for tt in sorted_tasks:
        if tt.depends_on_position is not None:
            from_task = position_to_task.get(tt.depends_on_position)
            to_task = position_to_task.get(tt.position)
            if from_task and to_task and from_task.id != to_task.id:
                db.add(TaskDependency(
                    from_task_id=from_task.id,
                    to_task_id=to_task.id,
                    dep_type="finish_to_start",
                ))

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
