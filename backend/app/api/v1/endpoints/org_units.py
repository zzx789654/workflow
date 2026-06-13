import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.ad_sync import sync_ad_org_tree
from app.db.session import get_db
from app.models.org import OrgUnit
from app.models.user import User
from app.schemas.org import AdSyncResult, OrgUnitCreate, OrgUnitOut, OrgUnitUpdate

router = APIRouter(prefix="/org-units", tags=["org-units"])


@router.post("/sync-ad", response_model=AdSyncResult)
async def sync_ad(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """手動觸發一次 AD/OU 組織樹同步（admin only）。只讀目錄、不寫回 AD。

    註冊在 /{unit_id} 動態路由之前，避免 "sync-ad" 被當成 unit_id 解析。
    """
    summary = await sync_ad_org_tree(db)
    return AdSyncResult(
        created=summary.created,
        updated=summary.updated,
        deactivated=summary.deactivated,
        members_assigned=summary.members_assigned,
        users_created=summary.users_created,
        users_updated=summary.users_updated,
        users_deactivated=summary.users_deactivated,
        message=summary.message,
    )


async def _ancestor_or_self(db: AsyncSession, start_id: uuid.UUID) -> set[uuid.UUID]:
    """回傳 start_id 自身 + 所有祖先的 id（用於成環偵測）。"""
    rows = (await db.execute(select(OrgUnit.id, OrgUnit.parent_id))).all()
    parent_of = {uid: pid for uid, pid in rows}
    chain: set[uuid.UUID] = set()
    cur: uuid.UUID | None = start_id
    while cur is not None and cur not in chain:
        chain.add(cur)
        cur = parent_of.get(cur)
    return chain


async def _validate_parent(db: AsyncSession, unit_id: uuid.UUID | None, parent_id: uuid.UUID | None):
    """確認 parent 存在，且不會造成成環（parent 不可為自己或自己的子孫）。"""
    if parent_id is None:
        return
    parent = (await db.execute(select(OrgUnit).where(OrgUnit.id == parent_id))).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="上層單位不存在")
    if unit_id is not None:
        # parent 若是 unit 自己或其子孫，則成環。子孫 = 「unit 在其祖先鏈中」者。
        if parent_id == unit_id:
            raise HTTPException(status_code=400, detail="上層單位不可為自己")
        ancestors = await _ancestor_or_self(db, parent_id)
        if unit_id in ancestors:
            raise HTTPException(status_code=400, detail="上層單位不可指向自己的子單位（會造成循環）")


async def _validate_manager(db: AsyncSession, manager_user_id: uuid.UUID | None):
    if manager_user_id is None:
        return
    exists = (
        await db.execute(select(User.id).where(User.id == manager_user_id, User.is_active == True))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="指定的主管使用者不存在")


@router.get("/", response_model=list[OrgUnitOut])
async def list_org_units(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """列出所有組織單位（前端自行組樹）。任何登入者可讀（用於下拉選單/組織圖）。"""
    result = await db.execute(select(OrgUnit).order_by(OrgUnit.name))
    return result.scalars().all()


@router.post("/", response_model=OrgUnitOut, status_code=201)
async def create_org_unit(body: OrgUnitCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    await _validate_parent(db, None, body.parent_id)
    await _validate_manager(db, body.manager_user_id)
    unit = OrgUnit(name=body.name, parent_id=body.parent_id, manager_user_id=body.manager_user_id)
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return unit


@router.patch("/{unit_id}", response_model=OrgUnitOut)
async def update_org_unit(
    unit_id: uuid.UUID,
    body: OrgUnitUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    unit = (await db.execute(select(OrgUnit).where(OrgUnit.id == unit_id))).scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="組織單位不存在")
    data = body.model_dump(exclude_unset=True)
    if "parent_id" in data:
        await _validate_parent(db, unit_id, data["parent_id"])
        unit.parent_id = data["parent_id"]
    if "manager_user_id" in data:
        await _validate_manager(db, data["manager_user_id"])
        unit.manager_user_id = data["manager_user_id"]
    if "name" in data and data["name"] is not None:
        unit.name = data["name"]
    await db.commit()
    await db.refresh(unit)
    return unit


@router.delete("/{unit_id}", status_code=204)
async def delete_org_unit(unit_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    unit = (await db.execute(select(OrgUnit).where(OrgUnit.id == unit_id))).scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="組織單位不存在")
    # FK 為 SET NULL：子單位升為頂層、所屬使用者脫離單位，不孤兒化。
    await db.delete(unit)
    await db.commit()
