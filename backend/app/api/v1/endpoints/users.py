import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.org import OrgUnit, UserCalendarGrant
from app.models.user import User, UserRole
from app.schemas.org import CalendarGrantCreate, CalendarGrantOut
from app.schemas.user import AdminUserUpdate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    update_data = body.model_dump(exclude_none=True)
    # email 僅 local 帳號可改；remote 帳號 email 由遠端目錄管理，登入時自動帶入
    if "email" in update_data and current_user.auth_source != "local":
        raise HTTPException(status_code=400, detail="遠端帳號的 Email 由目錄服務管理，無法在此修改")
    for field, value in update_data.items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.is_active == True).order_by(User.display_name))
    return result.scalars().all()


@router.patch("/{user_id}/org", response_model=UserOut)
async def update_user_org(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """admin 維護使用者的組織歸屬（部門/課別單位）與職位文字。

    一般使用者不可自改此二欄位（不在 UserUpdate schema），由此 admin 端點集中管理，
    防止越權竄改組織歸屬（比照 auth_source 防竄改）。
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.set_org_unit:
        if body.org_unit_id is not None:
            exists = (await db.execute(select(OrgUnit.id).where(OrgUnit.id == body.org_unit_id))).scalar_one_or_none()
            if exists is None:
                raise HTTPException(status_code=404, detail="組織單位不存在")
        user.org_unit_id = body.org_unit_id
    if body.set_position:
        user.position = body.position
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}/calendar-grants", response_model=list[CalendarGrantOut])
async def list_calendar_grants(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    result = await db.execute(select(UserCalendarGrant).where(UserCalendarGrant.user_id == user_id))
    return result.scalars().all()


@router.post("/{user_id}/calendar-grants", response_model=CalendarGrantOut, status_code=201)
async def add_calendar_grant(
    user_id: uuid.UUID,
    body: CalendarGrantCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """admin 額外授權某使用者可檢視某組織單位（含子樹）的日曆。"""
    user = (await db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    unit = (await db.execute(select(OrgUnit.id).where(OrgUnit.id == body.org_unit_id))).scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="組織單位不存在")
    existing = (
        await db.execute(
            select(UserCalendarGrant).where(
                UserCalendarGrant.user_id == user_id,
                UserCalendarGrant.org_unit_id == body.org_unit_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    grant = UserCalendarGrant(user_id=user_id, org_unit_id=body.org_unit_id)
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


@router.delete("/{user_id}/calendar-grants/{grant_id}", status_code=204)
async def remove_calendar_grant(
    user_id: uuid.UUID,
    grant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    grant = (
        await db.execute(
            select(UserCalendarGrant).where(UserCalendarGrant.id == grant_id, UserCalendarGrant.user_id == user_id)
        )
    ).scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="授權不存在")
    await db.delete(grant)
    await db.commit()


@router.patch("/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: uuid.UUID, role: UserRole, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # remote 帳號可升 admin：login 不再強制 admin 走 local 密碼，admin 依其 auth_source
    # 正常驗證（remote admin 走目錄、local admin 走本地），故升 admin 不會鎖死。
    # 注意：未強制保留 local admin，若所有 admin 皆為 remote 且目錄服務中斷，
    # 期間將無人能以 admin 身分登入（已與使用者確認接受此取捨）。
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = False
    await db.commit()
