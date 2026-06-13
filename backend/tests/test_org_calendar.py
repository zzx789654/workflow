"""G09 組織階層 + 主管部門日曆堆疊檢視 + 多欄位編輯 測試。

涵蓋：org CRUD、成環防護、SET NULL、admin 改使用者欄位、日曆可視範圍
（自管子樹 ∪ grant 子樹）、越權（IDOR / 一般使用者不可改歸屬 / 非主管看不到他人）。
"""

import uuid

import pytest

API = "/api/v1"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, prefix: str, password="Passw0rd1"):
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    r = await client.post(
        f"{API}/auth/register",
        json={"username": username, "display_name": prefix, "password": password},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    lr = await client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert lr.status_code == 200
    return uid, lr.json()["access_token"]


async def _make_unit(client, admin_token, name, parent_id=None, manager_user_id=None):
    body = {"name": name}
    if parent_id is not None:
        body["parent_id"] = parent_id
    if manager_user_id is not None:
        body["manager_user_id"] = manager_user_id
    r = await client.post(f"{API}/org-units/", json=body, headers=auth(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


async def _make_daily(client, token, title, date="2026-06-15"):
    r = await client.post(
        f"{API}/daily-tasks/",
        json={"title": title, "date": date},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── 組織單位 CRUD ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_org_crud_admin(client, admin_token):
    dept = await _make_unit(client, admin_token, "工程部")
    sect = await _make_unit(client, admin_token, "後端課", parent_id=dept["id"])
    assert sect["parent_id"] == dept["id"]

    # list
    r = await client.get(f"{API}/org-units/", headers=auth(admin_token))
    assert r.status_code == 200
    assert {u["name"] for u in r.json()} >= {"工程部", "後端課"}

    # rename
    r = await client.patch(f"{API}/org-units/{sect['id']}", json={"name": "平台課"}, headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["name"] == "平台課"


@pytest.mark.asyncio
async def test_org_create_requires_admin(client, member_token):
    r = await client.post(f"{API}/org-units/", json={"name": "X"}, headers=auth(member_token))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_org_member_can_list(client, admin_token, member_token):
    await _make_unit(client, admin_token, "業務部")
    r = await client.get(f"{API}/org-units/", headers=auth(member_token))
    assert r.status_code == 200  # 任何登入者可讀（下拉用）


@pytest.mark.asyncio
async def test_org_parent_not_found(client, admin_token):
    r = await client.post(
        f"{API}/org-units/", json={"name": "X", "parent_id": str(uuid.uuid4())}, headers=auth(admin_token)
    )
    assert r.status_code == 404


# ── 成環防護 ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_org_cycle_self_parent(client, admin_token):
    a = await _make_unit(client, admin_token, "A")
    r = await client.patch(f"{API}/org-units/{a['id']}", json={"parent_id": a["id"]}, headers=auth(admin_token))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_org_cycle_descendant_parent(client, admin_token):
    a = await _make_unit(client, admin_token, "A")
    b = await _make_unit(client, admin_token, "B", parent_id=a["id"])
    c = await _make_unit(client, admin_token, "C", parent_id=b["id"])
    # 把 A 的 parent 設成其孫 C → 成環，應擋
    r = await client.patch(f"{API}/org-units/{a['id']}", json={"parent_id": c["id"]}, headers=auth(admin_token))
    assert r.status_code == 400


# ── SET NULL 刪除 ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_org_delete_orphans_to_null(client, admin_token):
    dept = await _make_unit(client, admin_token, "母單位")
    child = await _make_unit(client, admin_token, "子單位", parent_id=dept["id"])
    uid, _ = await _register(client, "emp")
    # 指派使用者到子單位
    r = await client.patch(
        f"{API}/users/{uid}/org", json={"set_org_unit": True, "org_unit_id": child["id"]}, headers=auth(admin_token)
    )
    assert r.status_code == 200 and r.json()["org_unit_id"] == child["id"]

    # 刪母單位 → 子單位升頂層（parent_id 變 null），使用者仍在子單位
    r = await client.delete(f"{API}/org-units/{dept['id']}", headers=auth(admin_token))
    assert r.status_code == 204
    r = await client.get(f"{API}/org-units/", headers=auth(admin_token))
    names = {u["id"]: u for u in r.json()}
    assert child["id"] in names and names[child["id"]]["parent_id"] is None


# ── admin 改使用者欄位 ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_set_position_and_unit(client, admin_token):
    unit = await _make_unit(client, admin_token, "財務部")
    uid, _ = await _register(client, "fin")
    r = await client.patch(
        f"{API}/users/{uid}/org",
        json={"set_org_unit": True, "org_unit_id": unit["id"], "set_position": True, "position": "會計"},
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["org_unit_id"] == unit["id"] and body["position"] == "會計"


@pytest.mark.asyncio
async def test_admin_clear_unit_with_null(client, admin_token):
    unit = await _make_unit(client, admin_token, "暫存部")
    uid, _ = await _register(client, "tmp")
    await client.patch(
        f"{API}/users/{uid}/org", json={"set_org_unit": True, "org_unit_id": unit["id"]}, headers=auth(admin_token)
    )
    # set_org_unit True + org_unit_id None → 清空
    r = await client.patch(
        f"{API}/users/{uid}/org", json={"set_org_unit": True, "org_unit_id": None}, headers=auth(admin_token)
    )
    assert r.status_code == 200 and r.json()["org_unit_id"] is None


@pytest.mark.asyncio
async def test_member_cannot_set_org_fields(client, member_token):
    # 一般使用者打 admin 端點 → 403
    other = uuid.uuid4()
    r = await client.patch(
        f"{API}/users/{other}/org", json={"set_position": True, "position": "X"}, headers=auth(member_token)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_tamper_own_org_via_update_me(client, member_token):
    # /users/me 的 UserUpdate schema 不含 org_unit_id/position → 即使送了也被忽略
    r = await client.patch(
        f"{API}/users/me",
        json={"display_name": "Hax", "org_unit_id": str(uuid.uuid4()), "position": "CEO"},
        headers=auth(member_token),
    )
    assert r.status_code == 200
    assert r.json()["org_unit_id"] is None and r.json()["position"] is None


@pytest.mark.asyncio
async def test_set_unit_nonexistent_404(client, admin_token):
    uid, _ = await _register(client, "u")
    r = await client.patch(
        f"{API}/users/{uid}/org",
        json={"set_org_unit": True, "org_unit_id": str(uuid.uuid4())},
        headers=auth(admin_token),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_set_org_user_not_found(client, admin_token):
    r = await client.patch(
        f"{API}/users/{uuid.uuid4()}/org", json={"set_position": True, "position": "X"}, headers=auth(admin_token)
    )
    assert r.status_code == 404


# ── 日曆可視範圍：自動繼承（manager） ─────────────────────────
@pytest.mark.asyncio
async def test_manager_sees_subordinate_daily(client, admin_token):
    dept = await _make_unit(client, admin_token, "研發部")
    sect = await _make_unit(client, admin_token, "AI課", parent_id=dept["id"])
    # 部屬在子單位
    sub_id, sub_token = await _register(client, "sub")
    await client.patch(
        f"{API}/users/{sub_id}/org", json={"set_org_unit": True, "org_unit_id": sect["id"]}, headers=auth(admin_token)
    )
    await _make_daily(client, sub_token, "部屬的日常")

    # 主管管理「研發部」（含子單位 AI課）
    mgr_id, mgr_token = await _register(client, "mgr")
    r = await client.patch(f"{API}/org-units/{dept['id']}", json={"manager_user_id": mgr_id}, headers=auth(admin_token))
    assert r.status_code == 200

    # include_team=true → 主管看得到部屬的日常，且帶 user 與 color
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(mgr_token))
    assert r.status_code == 200
    dailies = [e for e in r.json() if e["type"] == "daily"]
    titles = {e["title"] for e in dailies}
    assert "部屬的日常" in titles
    owned = next(e for e in dailies if e["title"] == "部屬的日常")
    assert owned["user_id"] == sub_id and owned["user_name"] and owned["color"]


@pytest.mark.asyncio
async def test_manager_without_team_flag_only_self(client, admin_token):
    dept = await _make_unit(client, admin_token, "行銷部")
    sub_id, sub_token = await _register(client, "sub2")
    await client.patch(
        f"{API}/users/{sub_id}/org", json={"set_org_unit": True, "org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    await _make_daily(client, sub_token, "他人日常")
    mgr_id, mgr_token = await _register(client, "mgr2")
    await client.patch(f"{API}/org-units/{dept['id']}", json={"manager_user_id": mgr_id}, headers=auth(admin_token))

    # 預設 include_team=false → 只看自己（空）
    r = await client.get(f"{API}/calendar/?year=2026&month=6", headers=auth(mgr_token))
    assert r.status_code == 200
    assert all(e["title"] != "他人日常" for e in r.json())


@pytest.mark.asyncio
async def test_non_manager_cannot_see_others(client, admin_token):
    dept = await _make_unit(client, admin_token, "客服部")
    sub_id, sub_token = await _register(client, "csr")
    await client.patch(
        f"{API}/users/{sub_id}/org", json={"set_org_unit": True, "org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    await _make_daily(client, sub_token, "客服日常")

    # 同部門但非主管、無 grant 的人 → include_team 也只看到自己
    peer_id, peer_token = await _register(client, "peer")
    await client.patch(
        f"{API}/users/{peer_id}/org", json={"set_org_unit": True, "org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(peer_token))
    assert r.status_code == 200
    assert all(e["title"] != "客服日常" for e in r.json())


# ── 日曆可視範圍：admin grant ─────────────────────────────────
@pytest.mark.asyncio
async def test_grant_grants_visibility(client, admin_token):
    dept = await _make_unit(client, admin_token, "稽核部")
    sub_id, sub_token = await _register(client, "aud")
    await client.patch(
        f"{API}/users/{sub_id}/org", json={"set_org_unit": True, "org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    await _make_daily(client, sub_token, "稽核日常")

    viewer_id, viewer_token = await _register(client, "viewer")
    # 先確認沒授權看不到
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(viewer_token))
    assert all(e["title"] != "稽核日常" for e in r.json())

    # admin 授權 viewer 可看稽核部
    gr = await client.post(
        f"{API}/users/{viewer_id}/calendar-grants", json={"org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    assert gr.status_code == 201
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(viewer_token))
    assert any(e["title"] == "稽核日常" for e in r.json())

    # 重複授權 → 回既有（仍 201，幂等）
    gr2 = await client.post(
        f"{API}/users/{viewer_id}/calendar-grants", json={"org_unit_id": dept["id"]}, headers=auth(admin_token)
    )
    assert gr2.status_code == 201

    # list + remove
    lr = await client.get(f"{API}/users/{viewer_id}/calendar-grants", headers=auth(admin_token))
    assert lr.status_code == 200 and len(lr.json()) == 1
    grant_id = lr.json()[0]["id"]
    dr = await client.delete(f"{API}/users/{viewer_id}/calendar-grants/{grant_id}", headers=auth(admin_token))
    assert dr.status_code == 204
    # 移除後看不到
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(viewer_token))
    assert all(e["title"] != "稽核日常" for e in r.json())


@pytest.mark.asyncio
async def test_grant_requires_admin(client, member_token):
    r = await client.post(
        f"{API}/users/{uuid.uuid4()}/calendar-grants",
        json={"org_unit_id": str(uuid.uuid4())},
        headers=auth(member_token),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_grant_unit_not_found(client, admin_token):
    uid, _ = await _register(client, "g")
    r = await client.post(
        f"{API}/users/{uid}/calendar-grants", json={"org_unit_id": str(uuid.uuid4())}, headers=auth(admin_token)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_grant_user_not_found(client, admin_token):
    unit = await _make_unit(client, admin_token, "X部")
    r = await client.post(
        f"{API}/users/{uuid.uuid4()}/calendar-grants", json={"org_unit_id": unit["id"]}, headers=auth(admin_token)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_remove_grant_not_found(client, admin_token):
    uid, _ = await _register(client, "g2")
    r = await client.delete(f"{API}/users/{uid}/calendar-grants/{uuid.uuid4()}", headers=auth(admin_token))
    assert r.status_code == 404


# ── admin 可見全體 ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_sees_all_daily(client, admin_token):
    sub_id, sub_token = await _register(client, "anyone")
    await _make_daily(client, sub_token, "任意人日常")
    r = await client.get(f"{API}/calendar/?year=2026&month=6&include_team=true", headers=auth(admin_token))
    assert r.status_code == 200
    assert any(e["title"] == "任意人日常" for e in r.json())


# ── manager 指派不存在使用者 ──────────────────────────────────
@pytest.mark.asyncio
async def test_assign_nonexistent_manager(client, admin_token):
    r = await client.post(
        f"{API}/org-units/", json={"name": "Y部", "manager_user_id": str(uuid.uuid4())}, headers=auth(admin_token)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_org_unit_not_found(client, admin_token):
    r = await client.patch(f"{API}/org-units/{uuid.uuid4()}", json={"name": "Z"}, headers=auth(admin_token))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_org_unit_not_found(client, admin_token):
    r = await client.delete(f"{API}/org-units/{uuid.uuid4()}", headers=auth(admin_token))
    assert r.status_code == 404
