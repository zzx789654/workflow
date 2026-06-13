"""G10 AD/OU 組織樹同步測試（mock ldap3 / list_ous）。

涵蓋：DN 解析建樹、冪等重跑、OU 消失標停用、手動單位不被動、admin-only、
bind 失敗 fail-safe、未啟用 LDAP 略過。
"""

import pytest
from sqlalchemy import select

import app.core.ad_sync as ad_sync_mod
from app.core.auth_backends.ldap_auth import LdapOu, LdapUserEntry
from app.models.org import OrgUnit

API = "/api/v1"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _patch_ldap(monkeypatch, ous, config_backend="ldap", users=None):
    """讓 sync 走假的 list_ous / list_users 與假設定（auth_backend=ldap）。"""

    def fake_list_ous(**kwargs):
        return ous

    def fake_list_users(**kwargs):
        return users if users is not None else []

    async def fake_cfg(db):
        return {"auth_backend": config_backend, "ldap_host": "ad.test", "ldap_search_base": "DC=corp,DC=test"}

    monkeypatch.setattr(ad_sync_mod, "list_ous", fake_list_ous)
    monkeypatch.setattr(ad_sync_mod, "list_users", fake_list_users)
    monkeypatch.setattr(ad_sync_mod, "_load_ldap_config", fake_cfg)


async def _names_by_source(db, source):
    rows = (await db.execute(select(OrgUnit).where(OrgUnit.source == source))).scalars().all()
    return {u.name: u for u in rows}


# ── DN 解析建樹 ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_builds_tree(client, admin_token, monkeypatch):
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部"),
            LdapOu(dn="OU=後端課,OU=工程部,DC=corp,DC=test", name="後端課"),
            LdapOu(dn="OU=前端課,OU=工程部,DC=corp,DC=test", name="前端課"),
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 3 and body["deactivated"] == 0

    # 驗證父子關係：後端課/前端課的 parent = 工程部
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    by_name = {u["name"]: u for u in units}
    assert by_name["工程部"]["parent_id"] is None
    assert by_name["後端課"]["parent_id"] == by_name["工程部"]["id"]
    assert by_name["前端課"]["parent_id"] == by_name["工程部"]["id"]
    assert all(by_name[n]["source"] == "ad" for n in ("工程部", "後端課", "前端課"))


# ── 冪等：重跑不重複建 ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_idempotent(client, admin_token, monkeypatch):
    ous = [
        LdapOu(dn="OU=業務部,DC=corp,DC=test", name="業務部"),
        LdapOu(dn="OU=北區,OU=業務部,DC=corp,DC=test", name="北區"),
    ]
    _patch_ldap(monkeypatch, ous)
    r1 = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r1.json()["created"] == 2
    # 重跑：created=0、不重複
    r2 = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r2.json()["created"] == 0
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    assert len([u for u in units if u["name"] in ("業務部", "北區")]) == 2


# ── 改名：冪等更新 ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_updates_name(client, admin_token, monkeypatch):
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=財務,DC=corp,DC=test", name="財務")])
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    # AD 改名（同 DN 不同 name）→ updated
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=財務,DC=corp,DC=test", name="財務部")])
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["updated"] == 1
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    assert any(u["name"] == "財務部" for u in units)
    assert not any(u["name"] == "財務" for u in units)


# ── OU 消失 → 標停用，不刪 ────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_deactivates_vanished(client, admin_token, monkeypatch):
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="OU=A,DC=corp,DC=test", name="A"),
            LdapOu(dn="OU=B,DC=corp,DC=test", name="B"),
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    # B 從 AD 消失
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=A,DC=corp,DC=test", name="A")])
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["deactivated"] == 1
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    b = next(u for u in units if u["name"] == "B")
    assert b["is_active"] is False  # 保留但停用，未刪除

    # B 在 AD 復活 → 重新啟用
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=A,DC=corp,DC=test", name="A"), LdapOu(dn="OU=B,DC=corp,DC=test", name="B")],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["updated"] == 1
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    assert next(u for u in units if u["name"] == "B")["is_active"] is True


# ── 手動單位不被同步動 ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_leaves_manual_untouched(client, admin_token, monkeypatch):
    # 先手動建一個單位
    mr = await client.post(f"{API}/org-units/", json={"name": "手動部門"}, headers=auth(admin_token))
    manual_id = mr.json()["id"]

    _patch_ldap(monkeypatch, [LdapOu(dn="OU=AD部,DC=corp,DC=test", name="AD部")])
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))

    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    manual = next(u for u in units if u["id"] == manual_id)
    assert manual["source"] == "manual" and manual["is_active"] is True

    # 第二次同步只有 AD部，手動部門不應被標停用
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=AD部,DC=corp,DC=test", name="AD部")])
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    manual = next(u for u in units if u["id"] == manual_id)
    assert manual["is_active"] is True  # 手動的永遠不被同步停用


# ── 權限：sync 僅 admin ────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_requires_admin(client, member_token):
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(member_token))
    assert r.status_code == 403


# ── bind 失敗 → fail-safe 不動資料 ────────────────────────────
@pytest.mark.asyncio
async def test_sync_bind_failure_no_change(client, admin_token, monkeypatch):
    # 先建一個 AD 單位
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=X,DC=corp,DC=test", name="X")])
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))

    # list_ous 回 None（連線失敗）→ 不動既有資料
    def fail_list_ous(**kwargs):
        return None

    monkeypatch.setattr(ad_sync_mod, "list_ous", fail_list_ous)
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["created"] == 0 and "失敗" in r.json()["message"]
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    assert any(u["name"] == "X" and u["is_active"] for u in units)  # 既有資料完好


# ── 未啟用 LDAP → 略過 ────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_skips_when_not_ldap(client, admin_token, monkeypatch):
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=Y,DC=corp,DC=test", name="Y")], config_backend="local")
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["created"] == 0 and "略過" in r.json()["message"]


# ── DN 解析純函式（各版本 AD 相容） ───────────────────────────
def test_dn_utils_name_and_split():
    from app.core.dn_utils import name_from_dn, parent_dn, split_rdns

    assert name_from_dn("OU=後端課,OU=工程部,DC=corp,DC=test") == "後端課"
    assert name_from_dn("plainname") == "plainname"
    assert parent_dn("OU=後端課,OU=工程部,DC=x") == "OU=工程部,DC=x"
    assert parent_dn("OU=頂層,DC=x") == "DC=x"  # 父含 DC，但 ou_depth 才決定是否視為頂層
    assert split_rdns("OU=工程部,DC=x") == ["OU=工程部", "DC=x"]


def test_dn_utils_escaped_comma():
    r"""OU 名含逗號（DN 跳脫成 \,）時，不可被當分隔切錯。"""
    from app.core.dn_utils import name_from_dn, parent_dn, split_rdns

    dn = "OU=研發\\,測試,OU=工程部,DC=x"
    assert split_rdns(dn) == ["OU=研發\\,測試", "OU=工程部", "DC=x"]
    assert name_from_dn(dn) == "研發,測試"  # 解跳脫後還原逗號
    assert parent_dn(dn) == "OU=工程部,DC=x"


def test_dn_utils_case_insensitive_normalize():
    """大小寫不同的同一 DN 正規化後相等（父子比對才接得起來）。"""
    from app.core.dn_utils import normalize_dn, ou_depth

    a = normalize_dn("OU=後端課,OU=工程部,DC=Corp,DC=Test")
    b = normalize_dn("ou=後端課,ou=工程部,dc=corp,dc=test")
    assert a == b
    assert ou_depth("ou=後端課,OU=工程部,DC=x") == 2  # 大小寫混用仍正確算深度


# ── 相容性整合：大小寫不一仍正確建樹 + 冪等 ──────────────────
@pytest.mark.asyncio
async def test_sync_mixed_case_parent_links(client, admin_token, monkeypatch):
    """父 DN 與子 DN 的 OU 段大小寫不一致時，父子仍要接得起來（修正的 bug）。"""
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部"),
            # 子的父段寫成小寫 ou=工程部
            LdapOu(dn="OU=後端課,ou=工程部,DC=corp,DC=test", name="後端課"),
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["created"] == 2
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    by_name = {u["name"]: u for u in units}
    # 即使大小寫不一，後端課仍應掛在工程部下（而非變成兩個頂層）
    assert by_name["後端課"]["parent_id"] == by_name["工程部"]["id"]

    # 重跑：AD 整體 DN 改大小寫，不可重複建（冪等以正規化 DN 比對）
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="ou=工程部,dc=corp,dc=test", name="工程部"),
            LdapOu(dn="ou=後端課,ou=工程部,dc=corp,dc=test", name="後端課"),
        ],
    )
    r2 = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r2.json()["created"] == 0  # 大小寫變不算新建
    units2 = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    assert len([u for u in units2 if u["name"] in ("工程部", "後端課")]) == 2


def test_list_ous_connection_failure_returns_none():
    """無法連線的主機 → list_ous 回 None（不拋例外）。"""
    from app.core.auth_backends.ldap_auth import list_ous

    result = list_ous(
        host="127.0.0.1",
        port=1,  # 必定拒絕連線
        use_ssl=False,
        use_tls=False,
        bind_dn="cn=svc",
        bind_password="x",
        search_base="DC=corp,DC=test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_sync_real_config_path_no_ldap(client, admin_token):
    """不 mock _load_ldap_config，走真實設定讀取路徑：未設 auth_backend → 略過。

    驗證 _load_ldap_config 真實執行（含 secret 解密分支）而非僅靠 mock。
    透過系統設定寫入一筆 secret，確保解密分支被執行。
    """
    await client.put(
        f"{API}/system-settings/",
        json={"settings": {"ldap_bind_password": "s3cret-pw"}},
        headers=auth(admin_token),
    )
    # 不 patch list_ous / _load_ldap_config；auth_backend 預設非 ldap → 走略過分支
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.status_code == 200
    assert "略過" in r.json()["message"]


# ── G11：AD 使用者同步 ────────────────────────────────────────
async def _find_user(client, admin_token, username):
    users = (await client.get(f"{API}/users/", headers=auth(admin_token))).json()
    return next((u for u in users if u["username"] == username), None)


@pytest.mark.asyncio
async def test_user_prebuilt_and_assigned_by_dn(client, admin_token, monkeypatch):
    """有 DN 且父 OU 對應到同步單位 → 預建使用者並自動歸該 OU。"""
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(
                dn="CN=王小明,OU=工程部,DC=corp,DC=test",
                username="ming",
                display_name="王小明",
                email="ming@corp.test",
                title="資深工程師",
            )
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    body = r.json()
    assert body["users_created"] == 1 and body["members_assigned"] == 1

    u = await _find_user(client, admin_token, "ming")
    assert u is not None
    assert u["display_name"] == "王小明" and u["email"] == "ming@corp.test"
    assert u["position"] == "資深工程師"
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    eng = next(x for x in units if x["name"] == "工程部")
    assert u["org_unit_id"] == eng["id"]


@pytest.mark.asyncio
async def test_user_no_matching_ou_synced_without_unit(client, admin_token, monkeypatch):
    """無對應 OU（掛在 container）→ 只同步使用者、不指派單位。"""
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(
                dn="CN=陳大同,CN=Users,DC=corp,DC=test",  # 在 Users container 而非 OU
                username="datong",
                display_name="陳大同",
                email="datong@corp.test",
                title="",
            )
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["users_created"] == 1 and r.json()["members_assigned"] == 0
    u = await _find_user(client, admin_token, "datong")
    assert u is not None and u["org_unit_id"] is None  # 同步進來但不指派


@pytest.mark.asyncio
async def test_user_manual_assignment_not_overwritten(client, admin_token, monkeypatch):
    """已手動指派到 manual 單位的使用者，同步不覆蓋其歸屬。"""
    # 手動建單位 + 預建 AD 使用者
    manual = (await client.post(f"{API}/org-units/", json={"name": "特勤組"}, headers=auth(admin_token))).json()
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(dn="CN=安,OU=工程部,DC=corp,DC=test", username="an", display_name="安", email="", title="")
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    u = await _find_user(client, admin_token, "an")
    # admin 手動把 an 改到 manual 單位
    await client.patch(
        f"{API}/users/{u['id']}/org",
        json={"set_org_unit": True, "org_unit_id": manual["id"]},
        headers=auth(admin_token),
    )

    # 再同步：an 的 DN 父 OU=工程部，但因已手動指派 manual 單位 → 不覆蓋
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    u2 = await _find_user(client, admin_token, "an")
    assert u2["org_unit_id"] == manual["id"]  # 維持手動指派


@pytest.mark.asyncio
async def test_user_vanished_deactivated(client, admin_token, monkeypatch):
    """AD 中消失的預建帳號 → 本地停用、不刪。"""
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(dn="CN=甲,OU=工程部,DC=corp,DC=test", username="jia", display_name="甲", email="", title="")
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert await _find_user(client, admin_token, "jia") is not None

    # jia 從 AD 消失
    _patch_ldap(monkeypatch, [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")], users=[])
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["users_deactivated"] == 1
    # list_users 預設只回 active → 停用後查不到（驗證已停用）
    assert await _find_user(client, admin_token, "jia") is None


@pytest.mark.asyncio
async def test_user_sync_does_not_touch_local(client, admin_token, monkeypatch):
    """同名 local 帳號 → 同步不接管（來源互斥）。"""
    # 註冊一個 local 帳號
    await client.post(
        f"{API}/auth/register",
        json={"username": "shared", "display_name": "本地帳號", "password": "Local1234"},
    )
    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(
                dn="CN=shared,OU=工程部,DC=corp,DC=test",
                username="shared",
                display_name="AD搶名",
                email="x@corp.test",
                title="",
            )
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    u = await _find_user(client, admin_token, "shared")
    # 仍是 local 帳號、未被 AD 接管（display_name 沒被改、未指派單位）
    assert u["display_name"] == "本地帳號" and u["org_unit_id"] is None


@pytest.mark.asyncio
async def test_user_idempotent_update(client, admin_token, monkeypatch):
    """重跑同步：既有 AD 使用者只更新、不重建。"""
    ou = [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")]
    _patch_ldap(
        monkeypatch,
        ou,
        users=[
            LdapUserEntry(dn="CN=乙,OU=工程部,DC=corp,DC=test", username="yi", display_name="乙", email="", title="")
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    # 改 email 後重跑 → users_created=0、users_updated=1
    _patch_ldap(
        monkeypatch,
        ou,
        users=[
            LdapUserEntry(
                dn="CN=乙,OU=工程部,DC=corp,DC=test", username="yi", display_name="乙", email="yi@corp.test", title=""
            )
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["users_created"] == 0 and r.json()["users_updated"] == 1


@pytest.mark.asyncio
async def test_user_update_fields_and_reassign_between_ad_units(client, admin_token, monkeypatch):
    """既有 AD 使用者：更新姓名/職位/DN，且 AD 換 OU 時自動改歸新 ad 單位。"""
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部"),
            LdapOu(dn="OU=業務部,DC=corp,DC=test", name="業務部"),
        ],
        users=[
            LdapUserEntry(
                dn="CN=丁,OU=工程部,DC=corp,DC=test", username="ding", display_name="丁", email="", title="工程師"
            )
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    u1 = await _find_user(client, admin_token, "ding")
    units = (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json()
    eng = next(x for x in units if x["name"] == "工程部")
    assert u1["org_unit_id"] == eng["id"]

    # AD 端：改名、改職位、換到業務部（DN 變）
    _patch_ldap(
        monkeypatch,
        [
            LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部"),
            LdapOu(dn="OU=業務部,DC=corp,DC=test", name="業務部"),
        ],
        users=[
            LdapUserEntry(
                dn="CN=丁丁,OU=業務部,DC=corp,DC=test",
                username="ding",
                display_name="丁丁",
                email="ding@corp.test",
                title="專員",
            )
        ],
    )
    r = await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))
    assert r.json()["users_updated"] == 1
    u2 = await _find_user(client, admin_token, "ding")
    sales = next(
        x for x in (await client.get(f"{API}/org-units/", headers=auth(admin_token))).json() if x["name"] == "業務部"
    )
    assert u2["display_name"] == "丁丁" and u2["position"] == "專員"
    assert u2["org_unit_id"] == sales["id"]  # AD 換 OU → 自動改歸（原單位也是 ad，可改）


def test_list_users_connection_failure_returns_none():
    """無法連線 → list_users 回 None。"""
    from app.core.auth_backends.ldap_auth import list_users

    assert (
        list_users(
            host="127.0.0.1",
            port=1,
            use_ssl=False,
            use_tls=False,
            bind_dn="cn=svc",
            bind_password="x",
            search_base="DC=corp,DC=test",
        )
        is None
    )


@pytest.mark.asyncio
async def test_prebuilt_user_login_wiring(client, admin_token, monkeypatch):
    """預建 AD 帳號：本地密碼登不進（placeholder），遠端驗證才能登入（銜接 G05）。"""
    import app.api.v1.endpoints.auth as auth_mod

    _patch_ldap(
        monkeypatch,
        [LdapOu(dn="OU=工程部,DC=corp,DC=test", name="工程部")],
        users=[
            LdapUserEntry(
                dn="CN=丙,OU=工程部,DC=corp,DC=test",
                username="bing",
                display_name="丙",
                email="bing@corp.test",
                title="",
            )
        ],
    )
    await client.post(f"{API}/org-units/sync-ad", headers=auth(admin_token))

    # auth_backend 設為 ldap，讓 login 走 remote-first
    async def fake_backend(db):
        return "ldap"

    monkeypatch.setattr(auth_mod, "_get_auth_backend", fake_backend)

    # 1) 隨便密碼 + 遠端驗證失敗 → 401（placeholder 本地密碼不會放行）
    async def remote_fail(backend, username, password, db):
        return False, None

    monkeypatch.setattr(auth_mod, "_try_remote_auth", remote_fail)
    r = await client.post(f"{API}/auth/login", json={"username": "bing", "password": "whatever"})
    assert r.status_code == 401

    # 2) 遠端驗證成功 → 預建帳號可登入（沿用既有帳號、不重建）
    async def remote_ok(backend, username, password, db):
        return True, "bing@corp.test"

    monkeypatch.setattr(auth_mod, "_try_remote_auth", remote_ok)
    r = await client.post(f"{API}/auth/login", json={"username": "bing", "password": "ad-pw"})
    assert r.status_code == 200 and "access_token" in r.json()
