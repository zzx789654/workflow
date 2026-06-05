import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, Token, UserCreate, UserOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        display_name=body.display_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _get_auth_backend(db) -> str:
    """Read auth_backend setting from DB; default to 'local' on any error."""
    try:
        from app.models.system_setting import SystemSetting

        r = await db.execute(select(SystemSetting).where(SystemSetting.key == "auth_backend"))
        row = r.scalar_one_or_none()
        return (row.value if row else None) or "local"
    except Exception:
        return "local"


async def _try_remote_auth(backend: str, username: str, password: str, db) -> bool:
    """Attempt LDAP or RADIUS authentication; return True on success."""
    from app.core.crypto import decrypt_secret
    from app.models.system_setting import SystemSetting

    result = await db.execute(select(SystemSetting))
    rows = result.scalars().all()
    cfg = {r.key: (decrypt_secret(r.value) if r.is_secret else r.value) for r in rows}

    def g(k: str, fallback: str = "") -> str:
        return cfg.get(k) or fallback

    if backend == "ldap":
        from app.core.auth_backends.ldap_auth import authenticate_ldap

        info = authenticate_ldap(
            host=g("ldap_host"),
            port=int(g("ldap_port", "389")),
            use_ssl=g("ldap_use_ssl", "false") == "true",
            use_tls=g("ldap_use_tls", "false") == "true",
            bind_dn=g("ldap_bind_dn"),
            bind_password=g("ldap_bind_password"),
            search_base=g("ldap_search_base"),
            search_filter=g("ldap_search_filter", "(sAMAccountName={username})"),
            display_name_attr=g("ldap_display_name_attr", "displayName"),
            email_attr=g("ldap_email_attr", "mail"),
            username=username,
            password=password,
        )
        return info is not None

    if backend == "radius":
        from app.core.auth_backends.radius_auth import authenticate_radius

        return authenticate_radius(
            host=g("radius_host"),
            port=int(g("radius_port", "1812")),
            secret=g("radius_secret"),
            timeout=int(g("radius_timeout", "5")),
            username=username,
            password=password,
        )

    return False


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_backend = await _get_auth_backend(db)

    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if auth_backend == "local" or (user and user.role.value == "admin"):
        # Local auth: always available; admin account always uses local password
        if not user or not verify_password(body.password, user.hashed_password):
            logger.warning("Auth(local) failed for email=%s", body.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    else:
        # Remote auth (LDAP / RADIUS): use email prefix as username
        username = body.email.split("@")[0] if "@" in body.email else body.email
        ok = await _try_remote_auth(auth_backend, username, body.password, db)
        if not ok:
            logger.warning("Auth(%s) failed for email=%s", auth_backend, body.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        # Auto-provision user if not exists
        if not user:
            user = User(
                email=body.email,
                display_name=username,
                hashed_password=hash_password("__remote_auth__"),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

    logger.info("Login success backend=%s user=%s", auth_backend, body.email)
    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="目前密碼不正確")
    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}


@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(refresh_token, expected_type="refresh")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id), User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
