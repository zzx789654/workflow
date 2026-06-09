import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserOut, UserUpdate

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


@router.patch("/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: uuid.UUID, role: UserRole, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # 防鎖死：admin 走 remote-first fallback local，remote 帳號無可用本地密碼，
    # 一旦升為 admin 將永久無法登入（remote 不被視為 admin 逃生門）。從根本擋下。
    if role == UserRole.admin and user.auth_source != "local":
        raise HTTPException(status_code=400, detail="遠端帳號不可設為管理者，請改用本地帳號")
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
