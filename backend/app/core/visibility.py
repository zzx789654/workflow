"""日曆可視範圍解析。

主管可見的成員集合 = (自己所管理的單位子樹) ∪ (admin 額外授權的單位子樹)，
展開成 user_ids，再加上自己。admin 視為可見全體。

組織規模約 100 人，單位數量小，採應用層 BFS 展開子樹即可，不需遞迴 CTE（不過度設計）。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import OrgUnit, UserCalendarGrant
from app.models.user import User, UserRole


async def _descendant_unit_ids(db: AsyncSession, root_ids: set[uuid.UUID]) -> set[uuid.UUID]:
    """以 BFS 展開給定單位集合的所有子孫（含自身）。"""
    if not root_ids:
        return set()
    # 一次撈出所有單位的 (id, parent_id)，在記憶體建子樹（單位數量小）
    rows = (await db.execute(select(OrgUnit.id, OrgUnit.parent_id))).all()
    children: dict[uuid.UUID, list[uuid.UUID]] = {}
    for uid, pid in rows:
        if pid is not None:
            children.setdefault(pid, []).append(uid)

    result: set[uuid.UUID] = set()
    stack = list(root_ids)
    while stack:
        cur = stack.pop()
        if cur in result:
            continue
        result.add(cur)
        stack.extend(children.get(cur, []))
    return result


async def resolve_visible_unit_ids(db: AsyncSession, user: User) -> set[uuid.UUID] | None:
    """回傳該使用者可檢視日曆的「單位 id 集合」（已展開子樹）。

    admin 回傳 None 表示「不受單位限制（可見全體）」。
    """
    if user.role == UserRole.admin:
        return None

    root_ids: set[uuid.UUID] = set()
    # (a) 自己擔任 manager 的單位
    managed = (await db.execute(select(OrgUnit.id).where(OrgUnit.manager_user_id == user.id))).scalars().all()
    root_ids.update(managed)
    # (b) admin 額外授權的單位
    granted = (
        (await db.execute(select(UserCalendarGrant.org_unit_id).where(UserCalendarGrant.user_id == user.id)))
        .scalars()
        .all()
    )
    root_ids.update(granted)

    return await _descendant_unit_ids(db, root_ids)


async def resolve_visible_user_ids(db: AsyncSession, user: User) -> set[uuid.UUID] | None:
    """回傳該使用者可檢視日曆的「成員 user_id 集合」（含自己）。

    admin 回傳 None 表示「可見全體」。一般使用者至少可見自己。
    """
    unit_ids = await resolve_visible_unit_ids(db, user)
    if unit_ids is None:
        return None  # admin：全體
    if not unit_ids:
        return {user.id}  # 非主管、無授權：只看自己
    member_ids = (await db.execute(select(User.id).where(User.org_unit_id.in_(unit_ids)))).scalars().all()
    return set(member_ids) | {user.id}
