"""System settings CRUD + remote-auth test endpoints (Admin only)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system-settings", tags=["system_settings"])

# Keys that hold encrypted secrets
_SECRET_KEYS = {"ldap_bind_password", "radius_secret"}

# Public safe-to-read keys (no secrets)
_PUBLIC_KEYS = {
    "site_name",
    "allow_registration",
    "session_timeout_minutes",
    "auth_backend",
}


class SettingOut(BaseModel):
    key: str
    value: str
    is_secret: bool


class SettingsBulkUpdate(BaseModel):
    settings: dict[str, str]


class LdapTestRequest(BaseModel):
    username: str
    password: str


class RadiusTestRequest(BaseModel):
    username: str
    password: str


async def _get_all_settings(db: AsyncSession) -> dict[str, dict]:
    from app.models.system_setting import SystemSetting

    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()
    return {r.key: {"value": r.value, "is_secret": r.is_secret} for r in rows}


async def _get_setting(db: AsyncSession, key: str) -> str:
    from app.models.system_setting import SystemSetting

    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    if not row:
        return ""
    if row.is_secret:
        return decrypt_secret(row.value)
    return row.value


@router.get("/", response_model=list[SettingOut])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all settings; secret values are masked."""
    settings = await _get_all_settings(db)
    return [
        SettingOut(
            key=k,
            value=mask_secret(v["value"]) if v["is_secret"] else v["value"],
            is_secret=v["is_secret"],
        )
        for k, v in sorted(settings.items())
    ]


@router.put("/", status_code=200)
async def update_settings(
    body: SettingsBulkUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Bulk-update settings. Secret values are encrypted before storage."""
    from datetime import UTC, datetime

    from app.models.system_setting import SystemSetting

    for key, value in body.settings.items():
        # Skip masked placeholder — caller didn't change the secret
        if value == "••••••••":
            continue
        is_secret = key in _SECRET_KEYS
        stored_value = encrypt_secret(value) if is_secret and value else value

        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = stored_value
            row.updated_at = datetime.now(UTC)
        else:
            db.add(SystemSetting(key=key, value=stored_value, is_secret=is_secret))

    await db.commit()
    return {"ok": True}


@router.post("/test-ldap", status_code=200)
async def test_ldap(
    body: LdapTestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Test LDAP connectivity with a real username/password (Admin only)."""
    settings = await _get_all_settings(db)

    def gs(k: str, fallback: str = "") -> str:
        row = settings.get(k)
        if not row:
            return fallback
        return decrypt_secret(row["value"]) if row["is_secret"] else row["value"]

    host = gs("ldap_host")
    if not host:
        raise HTTPException(status_code=400, detail="LDAP host not configured")

    from app.core.auth_backends.ldap_auth import authenticate_ldap

    info = authenticate_ldap(
        host=host,
        port=int(gs("ldap_port", "389")),
        use_ssl=gs("ldap_use_ssl", "false") == "true",
        use_tls=gs("ldap_use_tls", "false") == "true",
        bind_dn=gs("ldap_bind_dn"),
        bind_password=gs("ldap_bind_password"),
        search_base=gs("ldap_search_base"),
        search_filter=gs("ldap_search_filter", "(sAMAccountName={username})"),
        display_name_attr=gs("ldap_display_name_attr", "displayName"),
        email_attr=gs("ldap_email_attr", "mail"),
        username=body.username,
        password=body.password,
    )
    if info is None:
        raise HTTPException(status_code=401, detail="LDAP authentication failed")
    return {"ok": True, "display_name": info.display_name, "email": info.email}


@router.post("/test-radius", status_code=200)
async def test_radius(
    body: RadiusTestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Test RADIUS connectivity with a real username/password (Admin only)."""
    settings = await _get_all_settings(db)

    def gs(k: str, fallback: str = "") -> str:
        row = settings.get(k)
        if not row:
            return fallback
        return decrypt_secret(row["value"]) if row["is_secret"] else row["value"]

    host = gs("radius_host")
    if not host:
        raise HTTPException(status_code=400, detail="RADIUS host not configured")

    from app.core.auth_backends.radius_auth import authenticate_radius

    ok = authenticate_radius(
        host=host,
        port=int(gs("radius_port", "1812")),
        secret=gs("radius_secret"),
        timeout=int(gs("radius_timeout", "5")),
        username=body.username,
        password=body.password,
    )
    if not ok:
        raise HTTPException(status_code=401, detail="RADIUS authentication failed")
    return {"ok": True}
