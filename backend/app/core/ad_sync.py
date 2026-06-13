"""AD/OU 組織樹同步。

把 AD 中 search_base 下的 organizationalUnit 階層（DN 路徑）同步成 org_units 樹。

並行隔離（與手動建立的 org_units 並存、互不踩）：
- 只新增/更新 source='ad' 的單位；source='manual' 永不被本同步動到。
- 以 external_id（=OU 的 DN）做冪等對應：重跑同步用 DN 找既有 ad 單位更新，而非重複建。
- AD 中消失的 ad 單位 → is_active=False（保留可人工複核，不硬刪、不孤兒化使用者）。

使用者歸屬：只在「ad 帳號 + org_unit_id 為空或指向 ad 單位」時，依其 DN 所在 OU 自動帶；
手動指派（指向 manual 單位）的不覆蓋。

只讀目錄、不寫回 AD。憑證沿用系統設定中既有的 ldap bind 服務帳號。
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_backends.ldap_auth import LdapOu, LdapUserEntry, list_ous, list_users
from app.core.dn_utils import normalize_dn, ou_depth, parent_dn
from app.models.org import OrgUnit
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    created: int = 0  # 新建 OU
    updated: int = 0  # 更新 OU
    deactivated: int = 0  # 停用 OU
    members_assigned: int = 0  # 依 DN 歸入 OU 的使用者數
    users_created: int = 0  # 預建的 AD 使用者
    users_updated: int = 0  # 更新的 AD 使用者
    users_deactivated: int = 0  # AD 消失 → 本地停用的使用者
    message: str = ""


# DN 解析統一走 dn_utils（處理大小寫、跳脫字元等各版本 AD 格式落差）。


async def _load_ldap_config(db: AsyncSession) -> dict[str, str]:
    from app.core.crypto import decrypt_secret
    from app.models.system_setting import SystemSetting

    rows = (await db.execute(select(SystemSetting))).scalars().all()
    return {r.key: (decrypt_secret(r.value) if r.is_secret else r.value) for r in rows}


async def sync_ad_org_tree(db: AsyncSession) -> SyncSummary:
    """執行一次 AD/OU 同步。回傳摘要；任何失敗回 message 並保留既有資料（fail-safe）。"""
    cfg = await _load_ldap_config(db)

    def g(k: str, fallback: str = "") -> str:
        return cfg.get(k) or fallback

    if g("auth_backend", "local") != "ldap":
        return SyncSummary(message="未啟用 LDAP 認證，略過 AD 同步")

    conn_args = dict(
        host=g("ldap_host"),
        port=int(g("ldap_port", "389")),
        use_ssl=g("ldap_use_ssl", "false") == "true",
        use_tls=g("ldap_use_tls", "false") == "true",
        bind_dn=g("ldap_bind_dn"),
        bind_password=g("ldap_bind_password"),
        search_base=g("ldap_search_base"),
    )

    ous = list_ous(**conn_args)
    if ous is None:
        # 連線/bind 失敗 → 不動既有資料
        return SyncSummary(message="AD 連線或查詢失敗，未變更任何資料")

    # 先建/更新 OU 樹，拿到 正規化DN → OrgUnit 對應供使用者歸屬
    summary, norm_to_unit = await _apply_ous(db, ous)

    # 再撈 AD 使用者預建/更新；user 查詢失敗不回滾 OU（OU 已成功）
    users = list_users(
        username_attr=g("ldap_username_attr", "sAMAccountName"),
        display_name_attr=g("ldap_display_name_attr", "displayName"),
        email_attr=g("ldap_email_attr", "mail"),
        title_attr=g("ldap_title_attr", "title"),
        **conn_args,
    )
    if users is not None:
        await _apply_users(db, users, norm_to_unit, summary)

    await db.commit()
    summary.message = (
        f"同步完成：單位 新增{summary.created}/更新{summary.updated}/停用{summary.deactivated}；"
        f"使用者 新增{summary.users_created}/更新{summary.users_updated}/停用{summary.users_deactivated}；"
        f"歸入部門 {summary.members_assigned}"
    )
    return summary


async def _apply_ous(db: AsyncSession, ous: list[LdapOu]) -> tuple[SyncSummary, dict[str, OrgUnit]]:
    summary = SyncSummary()

    # 既有 ad 單位：以「正規化 DN」當鍵（大小寫無關），吸收各版本 AD 大小寫落差。
    existing_ad = {
        normalize_dn(u.external_id): u
        for u in (await db.execute(select(OrgUnit).where(OrgUnit.source == "ad"))).scalars().all()
        if u.external_id
    }

    # 正規化父 DN → 對應 OrgUnit（建立後填入），供子單位接 parent（大小寫無關）。
    norm_to_unit: dict[str, OrgUnit] = {}
    incoming_norms: set[str] = set()

    # 由淺到深處理（OU 段數少的先），確保父單位先存在
    for ou in sorted(ous, key=lambda o: ou_depth(o.dn)):
        norm = normalize_dn(ou.dn)
        incoming_norms.add(norm)
        parent_unit = norm_to_unit.get(normalize_dn(parent_dn(ou.dn)))  # 父須也是同步進來的 OU，否則頂層

        unit = existing_ad.get(norm)
        if unit is None:
            unit = OrgUnit(
                name=ou.name,
                source="ad",
                external_id=ou.dn,
                is_active=True,
                parent_id=parent_unit.id if parent_unit else None,
            )
            db.add(unit)
            await db.flush()  # 取得 id 供子單位 parent_id 引用
            summary.created += 1
        else:
            # 冪等更新：名稱、父關係、external_id（AD 改了大小寫也跟上）、重新啟用
            changed = False
            if unit.name != ou.name:
                unit.name = ou.name
                changed = True
            new_parent_id = parent_unit.id if parent_unit else None
            if unit.parent_id != new_parent_id:
                unit.parent_id = new_parent_id
                changed = True
            if unit.external_id != ou.dn:
                unit.external_id = ou.dn  # 保存 AD 最新原樣 DN（僅大小寫變不算 updated）
            if not unit.is_active:
                unit.is_active = True
                changed = True
            if changed:
                summary.updated += 1
            await db.flush()
        norm_to_unit[norm] = unit

    # AD 中消失的 ad 單位 → 標停用（不刪）。比對用正規化 DN。
    for norm, unit in existing_ad.items():
        if norm not in incoming_norms and unit.is_active:
            unit.is_active = False
            summary.deactivated += 1

    await db.flush()
    # 回傳 正規化DN → OrgUnit，供 _apply_users 依使用者 DN 的父 OU 歸屬。
    return summary, norm_to_unit


async def _apply_users(
    db: AsyncSession,
    ldap_users: list[LdapUserEntry],
    norm_to_unit: dict[str, OrgUnit],
    summary: SyncSummary,
) -> None:
    """預建/更新 AD 使用者（不存可用密碼），並依其 DN 父 OU 自動歸屬。

    判斷機制：
    - 有 DN 且其父 OU 對應到已同步單位 → 自動設 org_unit_id（不覆蓋手動指派）。
    - 無對應（掛在 container 或該 OU 未同步）→ 只同步使用者本身，不指派單位。

    互斥：username 撞到 local 帳號 → 不接管（跳過，比照 login 的來源互斥）。
    AD 中消失的 ad 預建帳號 → is_active=False（不刪、保留歷史關聯）。
    """
    incoming_usernames: set[str] = set()

    for lu in ldap_users:
        incoming_usernames.add(lu.username)
        existing = (await db.execute(select(User).where(User.username == lu.username))).scalar_one_or_none()

        # 依 DN 父 OU 找對應單位（大小寫無關）；無對應則不指派
        target_unit = norm_to_unit.get(normalize_dn(parent_dn(lu.dn)))

        if existing is None:
            user = User(
                username=lu.username,
                display_name=lu.display_name or lu.username,
                email=lu.email or None,
                position=lu.title or None,
                external_id=lu.dn,
                auth_source="ldap",
                # placeholder 密碼：不可用於本地登入，登入必走遠端 LDAP 驗證
                hashed_password="__remote_auth__",
                org_unit_id=target_unit.id if target_unit else None,
            )
            db.add(user)
            await db.flush()
            summary.users_created += 1
            if target_unit:
                summary.members_assigned += 1
        elif existing.auth_source == "local":
            # 來源互斥：不接管 local 帳號（避免把本地帳號變成 AD 帳號）
            continue
        else:
            changed = False
            if existing.display_name != (lu.display_name or lu.username):
                existing.display_name = lu.display_name or lu.username
                changed = True
            if lu.email and existing.email != lu.email:
                existing.email = lu.email
                changed = True
            if lu.title and existing.position != lu.title:
                existing.position = lu.title
                changed = True
            if existing.external_id != lu.dn:
                existing.external_id = lu.dn
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            # 歸屬：只在「未手動指派（org_unit_id 為空或指向 ad 單位）」時自動帶；不覆蓋手動
            if target_unit and await _can_auto_assign(db, existing):
                if existing.org_unit_id != target_unit.id:
                    existing.org_unit_id = target_unit.id
                    summary.members_assigned += 1
                    changed = True
            if changed:
                summary.users_updated += 1
            await db.flush()

    # AD 消失的 ad 預建帳號 → 本地停用（不刪）
    ad_users = (
        (await db.execute(select(User).where(User.auth_source == "ldap", User.external_id.isnot(None)))).scalars().all()
    )
    for u in ad_users:
        if u.username not in incoming_usernames and u.is_active:
            u.is_active = False
            summary.users_deactivated += 1


async def _can_auto_assign(db: AsyncSession, user: User) -> bool:
    """可自動歸屬的條件：使用者目前沒單位，或現單位是 ad 來源（非手動指派）。"""
    if user.org_unit_id is None:
        return True
    cur = (await db.execute(select(OrgUnit).where(OrgUnit.id == user.org_unit_id))).scalar_one_or_none()
    return cur is not None and cur.source == "ad"
