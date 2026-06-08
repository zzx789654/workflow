"""N08 — AI 今日任務建議（Claude API，fallback 規則引擎）"""

import json
import logging
import os
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.models.v3_models import TaskDependency

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/priority-suggestions", tags=["ai_assist"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _urgency_score(task: Task, blocking_count: int) -> float:
    score = 0.0
    if task.due_date:
        days_left = (date.fromisoformat(task.due_date) - date.today()).days
        if days_left < 0:
            score += 50 + min(abs(days_left) * 2, 30)
        elif days_left == 0:
            score += 45
        elif days_left <= 2:
            score += 35
        elif days_left <= 7:
            score += 20
        else:
            score += max(0, 10 - days_left * 0.5)
    score += blocking_count * 15
    weights = {"urgent": 30, "high": 20, "medium": 10, "low": 0}
    score += weights.get(task.priority, 0)
    return round(score, 1)


def _rule_reason(task: Task, blocking: int) -> str:
    parts = []
    if task.due_date:
        days_left = (date.fromisoformat(task.due_date) - date.today()).days
        if days_left < 0:
            parts.append(f"已逾期 {abs(days_left)} 天")
        elif days_left == 0:
            parts.append("今天截止")
        elif days_left <= 2:
            parts.append(f"還有 {days_left} 天截止")
    if blocking > 0:
        parts.append(f"有 {blocking} 個任務等待完成")
    if task.priority in ("urgent", "high"):
        parts.append("高優先度")
    return "；".join(parts) if parts else "常規追蹤"


async def _get_claude_suggestions(tasks_data: list[dict]) -> list[dict] | None:
    """Call Claude API to rank top 3 tasks. Returns None if API unavailable."""
    if not ANTHROPIC_API_KEY or len(tasks_data) == 0:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        task_list = "\n".join(
            f"- [{t['priority']}] {t['title']} (截止：{t['due_date'] or '未設定'}，狀態：{t['status']})"
            for t in tasks_data[:20]
        )
        prompt = (
            f"以下是我今天的任務清單：\n{task_list}\n\n"
            "請從中挑出最應該優先處理的 3 件任務，"
            "用 JSON 陣列回答，每項包含 title 和 reason（50 字以內，繁體中文）。"
            '只輸出 JSON，不要其他說明。格式：[{"title":"...","reason":"..."}]'
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        parsed = json.loads(raw)
        # Match parsed titles back to task data
        title_map = {t["title"]: t for t in tasks_data}
        result = []
        for item in parsed[:3]:
            matched = title_map.get(item["title"])
            if matched:
                result.append({**matched, "reason": item["reason"], "model": "claude-haiku-4-5"})
        return result if result else None
    except Exception as e:
        logger.warning("Claude API call failed, falling back to rule engine: %s", e)
        return None


@router.get("")
async def priority_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value == "admin":
        proj_res = await db.execute(select(ProjectMember.project_id))
    else:
        proj_res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id))
    proj_ids = [r[0] for r in proj_res.all()]

    tasks_res = await db.execute(
        select(Task)
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(
            and_(
                TaskAssignee.user_id == current_user.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.project_id.in_(proj_ids),
            )
        )
    )
    tasks = tasks_res.scalars().all()

    if not tasks:
        return {
            "suggestions": [],
            "generated_at": datetime.now(UTC).isoformat(),
            "model": "none",
            "ai_enabled": bool(ANTHROPIC_API_KEY),
        }

    blocking_res = await db.execute(
        select(TaskDependency.to_task_id, func.count().label("cnt"))
        .where(TaskDependency.to_task_id.in_([t.id for t in tasks]))
        .group_by(TaskDependency.to_task_id)
    )
    blocking_map = {str(r.to_task_id): r.cnt for r in blocking_res.all()}

    # Build rule-scored list
    scored = []
    for t in tasks:
        blocking = blocking_map.get(str(t.id), 0)
        scored.append(
            {
                "task_id": str(t.id),
                "title": t.title,
                "project_id": str(t.project_id),
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date,
                "urgency_score": _urgency_score(t, blocking),
                "reason": _rule_reason(t, blocking),
            }
        )
    scored.sort(key=lambda x: x["urgency_score"], reverse=True)

    # Attempt Claude API upgrade
    claude_result = await _get_claude_suggestions(scored)
    if claude_result:
        return {
            "suggestions": claude_result[:3],
            "generated_at": datetime.now(UTC).isoformat(),
            "model": "claude-haiku-4-5",
            "ai_enabled": True,
        }

    return {
        "suggestions": scored[:3],
        "generated_at": datetime.now(UTC).isoformat(),
        "model": "rule_engine_v1",
        "ai_enabled": bool(ANTHROPIC_API_KEY),
    }
