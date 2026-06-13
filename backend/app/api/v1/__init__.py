from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_assist,
    announcements,
    attachments,
    auth,
    bulk_tasks,
    calendar,
    checkins,
    custom_fields,
    daily_task_import,
    daily_tasks,
    dashboard,
    dependencies,
    insights,
    milestones,
    notifications,
    org_units,
    projects,
    reactions,
    recurring,
    search,
    subtasks,
    system_settings,
    tasks,
    templates,
    time_logs,
    users,
    weekly_reports,
    workload,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(org_units.router)
router.include_router(projects.router)
router.include_router(milestones.router)
# bulk_tasks 必須在 tasks 之前註冊：/tasks/bulk 需優先於 /tasks/{task_id} 匹配，
# 否則 "bulk" 會被當成 task_id 嘗試解析為 UUID 而回 422。
router.include_router(bulk_tasks.router)
router.include_router(tasks.router)
router.include_router(subtasks.router)
router.include_router(time_logs.router)
router.include_router(time_logs.report_router)
router.include_router(daily_tasks.router)
router.include_router(daily_task_import.router)
router.include_router(templates.router)
router.include_router(calendar.router)
router.include_router(dashboard.router)
router.include_router(search.router)
router.include_router(notifications.router)
router.include_router(custom_fields.router)
router.include_router(dependencies.router)
# P2 features
router.include_router(weekly_reports.router)
router.include_router(workload.router)
router.include_router(reactions.router)
router.include_router(attachments.router)
router.include_router(attachments.project_files_router)
router.include_router(checkins.router)
router.include_router(checkins.stale_router)
router.include_router(recurring.router)
# P3 features
router.include_router(announcements.router)
router.include_router(insights.router)
router.include_router(ai_assist.router)
# System
router.include_router(system_settings.router)
