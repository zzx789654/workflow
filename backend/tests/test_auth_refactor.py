"""G05 認證重構 — 完整分支 + G3 資安確認（OWASP A07 認證失效）。

涵蓋：remote-first fallback local、來源互斥、auto-provision、email 帶入、
remote 可升 admin（升級後仍能登入、不鎖死）、email 僅 local 可改、admin 走 remote-first。
"""

import sys
import types
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _install_fake_ldap(monkeypatch, email="user@corp.com", ok=True):
    """安裝假 ldap3：ok=True 時對任何帳號驗證成功並回傳指定 email。"""
    fake_ldap3 = types.ModuleType("ldap3")

    class FakeEntry:
        entry_dn = "cn=u,dc=x"

        def __getattr__(self, name):
            v = MagicMock()
            v.value = "Dir User" if ("name" in name.lower() or name == "cn") else email
            return v

    class FakeConn:
        def __init__(self, *a, **k):
            self.entries = [FakeEntry()] if ok else []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def search(self, **k):
            return True

        def bind(self):
            return ok

    fake_ldap3.Connection = FakeConn
    fake_ldap3.Server = lambda *a, **k: MagicMock()
    fake_ldap3.Tls = lambda *a, **k: MagicMock()
    monkeypatch.setitem(sys.modules, "ldap3", fake_ldap3)


async def _set_backend_ldap(client, admin_token):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "ldap", "ldap_host": "ldap.example.com"}},
        headers=_auth(admin_token),
    )


# ── remote-first 成功 + email 帶入 ─────────────────────────────
@pytest.mark.asyncio
async def test_remote_first_autoprovision_pulls_email(client: AsyncClient, admin_token: str, monkeypatch):
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, email="alice@corp.com")
    resp = await client.post("/api/v1/auth/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 200
    me = await client.get("/api/v1/users/me", headers=_auth(resp.json()["access_token"]))
    assert me.json()["auth_source"] == "ldap"
    assert me.json()["email"] == "alice@corp.com"


@pytest.mark.asyncio
async def test_remote_email_updated_on_relogin(client: AsyncClient, admin_token: str, monkeypatch):
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, email="bob.old@corp.com")
    await client.post("/api/v1/auth/login", json={"username": "bob", "password": "pw"})
    # directory email changes -> next login updates it
    _install_fake_ldap(monkeypatch, email="bob.new@corp.com")
    resp = await client.post("/api/v1/auth/login", json={"username": "bob", "password": "pw"})
    me = await client.get("/api/v1/users/me", headers=_auth(resp.json()["access_token"]))
    assert me.json()["email"] == "bob.new@corp.com"


# ── remote 失敗 → fallback local ───────────────────────────────
@pytest.mark.asyncio
async def test_remote_fail_falls_back_to_local(client: AsyncClient, admin_token: str, monkeypatch):
    # register a local user first (backend still local at this point)
    await client.post(
        "/api/v1/auth/register",
        json={"username": "localguy", "password": "Local1234", "display_name": "L"},
    )
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, ok=False)  # remote rejects
    # local password still works via fallback
    resp = await client.post("/api/v1/auth/login", json={"username": "localguy", "password": "Local1234"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_remote_fail_and_no_local_user_rejected(client: AsyncClient, admin_token: str, monkeypatch):
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, ok=False)
    resp = await client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


# ── 來源互斥（核心資安需求）──────────────────────────────────
@pytest.mark.asyncio
async def test_source_conflict_local_user_cannot_login_via_remote(client: AsyncClient, admin_token: str, monkeypatch):
    # local account "dupe" exists with a real local password
    await client.post(
        "/api/v1/auth/register",
        json={"username": "dupe", "password": "Local1234", "display_name": "D"},
    )
    await _set_backend_ldap(client, admin_token)
    # 互斥：username 已是 local 來源 → remote 不接管，直接走 fallback local。
    # remote 密碼比對的是本地密碼 → 用遠端密碼登入失敗（401），但帳號未被鎖死。
    _install_fake_ldap(monkeypatch, email="dupe@corp.com", ok=True)
    resp = await client.post("/api/v1/auth/login", json={"username": "dupe", "password": "remotepw"})
    assert resp.status_code == 401
    # 本地密碼仍可登入（fallback），證明 local 帳號未被同名 remote 鎖死
    ok = await client.post("/api/v1/auth/login", json={"username": "dupe", "password": "Local1234"})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_register_conflicts_with_remote_username(client: AsyncClient, admin_token: str, monkeypatch):
    # provision a remote account "rmt"
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, email="rmt@corp.com")
    await client.post("/api/v1/auth/login", json={"username": "rmt", "password": "pw"})
    # now switch back to local and try to register same username -> 400 (互斥)
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "local"}},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "rmt", "password": "Local1234", "display_name": "X"},
    )
    assert resp.status_code == 400


# ── remote 帳號可升 admin，且升級後仍能透過 remote 登入（不鎖死）──
@pytest.mark.asyncio
async def test_remote_user_can_be_promoted_to_admin_and_still_login(client: AsyncClient, admin_token: str, monkeypatch):
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, email="carol@corp.com")
    login = await client.post("/api/v1/auth/login", json={"username": "carol", "password": "pw"})
    carol_id = (await client.get("/api/v1/users/me", headers=_auth(login.json()["access_token"]))).json()["id"]
    # admin promotes remote user to admin -> 200（已開放）
    resp = await client.patch(f"/api/v1/users/{carol_id}/role?role=admin", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    # 核心驗證：升為 admin 後，remote 帳號仍可透過目錄登入（login 不強制 admin 走 local）
    relogin = await client.post("/api/v1/auth/login", json={"username": "carol", "password": "pw"})
    assert relogin.status_code == 200
    me = await client.get("/api/v1/users/me", headers=_auth(relogin.json()["access_token"]))
    assert me.json()["role"] == "admin"
    assert me.json()["auth_source"] == "ldap"


# ── email 僅 local 可改 ────────────────────────────────────────
@pytest.mark.asyncio
async def test_local_user_can_change_email(client: AsyncClient, member_token: str):
    resp = await client.patch("/api/v1/users/me", json={"email": "new@personal.com"}, headers=_auth(member_token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@personal.com"


@pytest.mark.asyncio
async def test_remote_user_cannot_change_email(client: AsyncClient, admin_token: str, monkeypatch):
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, email="dave@corp.com")
    login = await client.post("/api/v1/auth/login", json={"username": "dave", "password": "pw"})
    resp = await client.patch(
        "/api/v1/users/me",
        json={"email": "spoof@evil.com"},
        headers=_auth(login.json()["access_token"]),
    )
    assert resp.status_code == 400


# ── admin 走 remote-first（不再 always-local）但仍可 fallback ───
@pytest.mark.asyncio
async def test_admin_login_works_via_local_fallback_under_ldap(
    client: AsyncClient, admin_user, admin_token: str, monkeypatch
):
    # backend=ldap, but admin is a local account; remote rejects -> fallback local succeeds
    await _set_backend_ldap(client, admin_token)
    _install_fake_ldap(monkeypatch, ok=False)
    resp = await client.post("/api/v1/auth/login", json={"username": admin_user.username, "password": "Admin1234"})
    assert resp.status_code == 200


# ── RADIUS backend：auto-provision 但無 email ──────────────────
@pytest.mark.asyncio
async def test_radius_autoprovision_no_email(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "radius", "radius_host": "r.example.com", "radius_secret": "s"}},
        headers=_auth(admin_token),
    )
    from unittest.mock import patch

    import app.core.auth_backends.radius_auth as radius_mod

    with patch.object(radius_mod, "authenticate_radius", return_value=True):
        resp = await client.post("/api/v1/auth/login", json={"username": "raduser", "password": "pw"})
    assert resp.status_code == 200
    me = await client.get("/api/v1/users/me", headers=_auth(resp.json()["access_token"]))
    assert me.json()["auth_source"] == "radius"
    assert me.json()["email"] is None  # RADIUS 無目錄 email


@pytest.mark.asyncio
async def test_radius_failure_rejected(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "radius", "radius_host": "r.example.com", "radius_secret": "s"}},
        headers=_auth(admin_token),
    )
    from unittest.mock import patch

    import app.core.auth_backends.radius_auth as radius_mod

    with patch.object(radius_mod, "authenticate_radius", return_value=False):
        resp = await client.post("/api/v1/auth/login", json={"username": "radghost", "password": "x"})
    assert resp.status_code == 401


# ── 防竄改：auth_source 不可由使用者透過 update_me 設定 ─────────
@pytest.mark.asyncio
async def test_user_cannot_tamper_auth_source(client: AsyncClient, member_token: str):
    # UserUpdate schema 不含 auth_source；多送的欄位被忽略，帳號仍是 local
    resp = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "X", "auth_source": "ldap"},
        headers=_auth(member_token),
    )
    assert resp.status_code == 200
    assert resp.json()["auth_source"] == "local"
