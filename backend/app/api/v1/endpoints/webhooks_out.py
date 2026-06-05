"""F18 — Outgoing Webhooks"""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.models.project import ProjectMember
from app.models.user import User
from app.models.v4_models import WebhookDelivery, WebhookEndpoint

router = APIRouter(prefix="/projects/{project_id}/webhooks", tags=["webhooks_out"])

VALID_EVENTS = {
    "task.created",
    "task.updated",
    "task.completed",
    "milestone.completed",
    "comment.created",
}


async def _check_manager(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role.in_(["owner", "manager"]),
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Manager access required")


def _validate_webhook_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError("Webhook URL must use http or https scheme")
    if not parsed.netloc:
        raise ValueError("Webhook URL must have a valid host")
    # Block private/loopback ranges (basic SSRF guard)
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "::1") or host.startswith("192.168.") or host.startswith("10."):
        raise ValueError("Webhook URL must not target private/loopback addresses")
    return url


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=2048)
    secret: str | None = Field(None, max_length=200)
    events: list[str] = Field(default_factory=list)

    from pydantic import field_validator

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_webhook_url(v)


class WebhookOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[WebhookOut])
async def list_webhooks(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.project_id == project_id))
    return res.scalars().all()


@router.post("/", response_model=WebhookOut, status_code=201)
async def create_webhook(
    project_id: uuid.UUID,
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    invalid_events = set(body.events) - VALID_EVENTS
    if invalid_events:
        raise HTTPException(status_code=400, detail=f"Invalid events: {invalid_events}")
    wh = WebhookEndpoint(
        project_id=project_id,
        name=body.name,
        url=body.url,
        secret=body.secret,
        events=body.events,
        created_by=current_user.id,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_manager(project_id, current_user, db)
    wh = await db.get(WebhookEndpoint, webhook_id)
    if not wh or str(wh.project_id) != str(project_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)
    await db.commit()


async def _deliver(endpoint_id: uuid.UUID, event_type: str, payload: dict):
    async with AsyncSessionLocal() as db:
        wh = await db.get(WebhookEndpoint, endpoint_id)
        if not wh or not wh.is_active:
            return

        delivery = WebhookDelivery(
            endpoint_id=endpoint_id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        db.add(delivery)
        await db.flush()

        body = str(payload).encode()
        headers = {"Content-Type": "application/json", "X-Workflow-Event": event_type}
        if wh.secret:
            sig = hmac.new(wh.secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Workflow-Signature"] = f"sha256={sig}"

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(wh.url, json=payload, headers=headers)
                delivery.response_status = resp.status_code
                delivery.attempt_count = attempt + 1
                if resp.is_success:
                    delivery.status = "delivered"
                    delivery.delivered_at = datetime.now(UTC)
                    wh.last_triggered_at = delivery.delivered_at
                    break
                delivery.status = "failed"
            except Exception:
                delivery.status = "failed"
                delivery.attempt_count = attempt + 1

        wh.retry_count = delivery.attempt_count
        await db.commit()
