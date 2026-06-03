import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.project import ProjectMember
from app.models.user import User
from app.models.v3_p2_models import Webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = []
    project_id: uuid.UUID
    name: str | None = None
    secret: str | None = None
    is_active: bool = True


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    name: str | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    url: str
    events: list
    is_active: bool
    secret: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


async def _check_project_member(project_id: uuid.UUID, user: User, db: AsyncSession):
    if user.role.value == "admin":
        return
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a project member")


async def _get_webhook_for_user(webhook_id: uuid.UUID, user: User, db: AsyncSession) -> Webhook:
    webhook = await db.get(Webhook, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    # Verify user has access to the project this webhook belongs to
    await _check_project_member(webhook.project_id, user, db)
    return webhook


@router.post("/", response_model=WebhookOut, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_project_member(body.project_id, current_user, db)
    webhook = Webhook(
        project_id=body.project_id,
        name=body.name,
        url=body.url,
        events=body.events,
        is_active=body.is_active,
        secret=body.secret,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.get("/", response_model=list[WebhookOut])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.value == "admin":
        result = await db.execute(select(Webhook).order_by(Webhook.created_at.desc()))
    else:
        # Return webhooks for projects where user is a member
        result = await db.execute(
            select(Webhook)
            .join(ProjectMember, Webhook.project_id == ProjectMember.project_id)
            .where(ProjectMember.user_id == current_user.id)
            .order_by(Webhook.created_at.desc())
        )
    return result.scalars().all()


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    webhook = await _get_webhook_for_user(webhook_id, current_user, db)
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(webhook, field, value)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    webhook = await _get_webhook_for_user(webhook_id, current_user, db)
    await db.delete(webhook)
    await db.commit()


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    webhook = await _get_webhook_for_user(webhook_id, current_user, db)
    payload = {
        "event": "test",
        "webhook_id": str(webhook.id),
        "project_id": str(webhook.project_id),
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(webhook.url, json=payload)
        return {
            "success": response.is_success,
            "status_code": response.status_code,
            "detail": "Test payload delivered successfully" if response.is_success else "Delivery failed",
        }
    except httpx.RequestError as exc:
        return {
            "success": False,
            "status_code": None,
            "detail": f"Request error: {exc}",
        }
