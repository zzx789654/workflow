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
    # Check allow_registration system setting
    try:
        from app.models.system_setting import SystemSetting

        r = await db.execute(select(SystemSetting).where(SystemSetting.key == "allow_registration"))
        row = r.scalar_one_or_none()
        allow = (row.value if row else None) or "true"
    except Exception:
        allow = "true"

    if allow.lower() not in ("true", "1", "yes"):
        raise HTTPException(status_code=403, detail="自行註冊已關閉，請聯絡管理員開通帳號")

    # 互斥：username 全域唯一，且不可與任何來源（含 remote auto-provision）的帳號重疊
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="此帳號名稱已被使用")
    user = User(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        hashed_password=hash_password(body.password),
        auth_source="local",
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


async def _try_remote_auth(backend: str, username: str, password: str, db) -> tuple[bool, str | None]:
    """Attempt LDAP or RADIUS authentication.

    Returns (success, remote_email). RADIUS has no directory email → email is None.
    """
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
        if info is None:
            return False, None
        return True, (info.email or None)

    if backend == "radius":
        from app.core.auth_backends.radius_auth import authenticate_radius

        ok = authenticate_radius(
            host=g("radius_host"),
            port=int(g("radius_port", "1812")),
            secret=g("radius_secret"),
            timeout=int(g("radius_timeout", "5")),
            username=username,
            password=password,
        )
        return ok, None

    return False, None


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登入順序：依 auth_backend 設定先試單一 remote（ldap/radius），失敗再 fallback 比對 local 密碼。
    auth_backend=local 時只走 local，完全不碰 remote。
    來源互斥：username 撞到不同 auth_source 的帳號一律拒登。
    """
    auth_backend = await _get_auth_backend(db)

    result = await db.execute(select(User).where(User.username == body.username, User.is_active == True))
    user = result.scalar_one_or_none()

    authed = False

    # 1) remote-first（僅當設定為 ldap/radius）
    #    互斥原則：remote 只能驗證 remote 來源（或全新）的帳號；若 username 已屬 local 帳號，
    #    remote 即使驗證成功也「不接管」——視同 remote 未命中，落到 fallback local，
    #    讓 local 帳號永遠能用自己的本地密碼登入（避免被 remote 同名鎖死）。
    if auth_backend in ("ldap", "radius") and (user is None or user.auth_source == auth_backend):
        ok, remote_email = await _try_remote_auth(auth_backend, body.username, body.password, db)
        if ok:
            if user is None:
                # auto-provision 遠端帳號，帶入遠端 email
                user = User(
                    username=body.username,
                    email=remote_email,
                    display_name=body.username,
                    hashed_password=hash_password("__remote_auth__"),
                    auth_source=auth_backend,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
            else:
                # 既有 remote 帳號：自動帶入/更新遠端 email
                if remote_email and user.email != remote_email:
                    user.email = remote_email
                    await db.commit()
                    await db.refresh(user)
            authed = True

    # 2) fallback local：必須是 local 來源且本地密碼正確
    if not authed:
        if not user or user.auth_source != "local" or not verify_password(body.password, user.hashed_password):
            logger.warning("Auth failed for username=%s (backend=%s)", body.username, auth_backend)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.info("Login success backend=%s user=%s", auth_backend, body.username)
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
