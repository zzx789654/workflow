from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    calendar,
    custom_fields,
    daily_tasks,
    dashboard,
    dependencies,
    milestones,
    notifications,
    projects,
    search,
    subtasks,
    tasks,
    templates,
    time_logs,
    users,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(projects.router)
router.include_router(milestones.router)
router.include_router(tasks.router)
router.include_router(subtasks.router)
router.include_router(time_logs.router)
router.include_router(time_logs.report_router)
router.include_router(daily_tasks.router)
router.include_router(templates.router)
router.include_router(calendar.router)
router.include_router(dashboard.router)
router.include_router(search.router)
router.include_router(notifications.router)
router.include_router(custom_fields.router)
router.include_router(dependencies.router)
