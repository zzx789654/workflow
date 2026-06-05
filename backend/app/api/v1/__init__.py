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
    health_score,
    insights,
    milestones,
    notifications,
    projects,
    public_share,
    reactions,
    recurring,
    search,
    subtasks,
    tasks,
    templates,
    time_logs,
    users,
    webhooks_out,
    weekly_reports,
    workload,
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
router.include_router(bulk_tasks.router)
router.include_router(reactions.router)
router.include_router(attachments.router)
router.include_router(checkins.router)
router.include_router(checkins.stale_router)
router.include_router(recurring.router)
# P3 features
router.include_router(announcements.router)
router.include_router(webhooks_out.router)
router.include_router(public_share.router)
router.include_router(public_share.public_router)
router.include_router(health_score.router)
router.include_router(insights.router)
router.include_router(ai_assist.router)
