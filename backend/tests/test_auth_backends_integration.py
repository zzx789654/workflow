"""Integration tests for auth remote-backend and registration gating."""

import sys
import types
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_registration_disabled(client: AsyncClient, admin_token: str):
    # admin disables registration
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"allow_registration": "false"}},
        headers=_auth(admin_token),
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "blocked", "email": "blocked@test.com", "display_name": "B", "password": "Secure1234"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_ldap_backend_autoprovision(client: AsyncClient, admin_token: str, monkeypatch):
    # configure ldap backend
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "ldap", "ldap_host": "ldap.example.com"}},
        headers=_auth(admin_token),
    )

    # mock ldap3 so authenticate_ldap succeeds for any creds
    fake_ldap3 = types.ModuleType("ldap3")

    class FakeEntry:
        entry_dn = "cn=newldap,dc=x"

        def __getattr__(self, name):
            v = MagicMock()
            v.value = "LDAP User" if "name" in name.lower() or name == "cn" else "newldap@example.com"
            return v

    class FakeConn:
        def __init__(self, *a, **k):
            self.entries = [FakeEntry()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def search(self, **k):
            return True

        def bind(self):
            return True

    fake_ldap3.Connection = FakeConn
    fake_ldap3.Server = lambda *a, **k: MagicMock()
    fake_ldap3.Tls = lambda *a, **k: MagicMock()
    monkeypatch.setitem(sys.modules, "ldap3", fake_ldap3)

    # new user (not in DB) authenticates via LDAP -> auto-provisioned with username
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "newldap", "password": "ldappass"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    # verify auto-provisioned account: auth_source=ldap, remote email pulled in
    token = resp.json()["access_token"]
    me = await client.get("/api/v1/users/me", headers=_auth(token))
    assert me.json()["auth_source"] == "ldap"
    assert me.json()["email"] == "newldap@example.com"


@pytest.mark.asyncio
async def test_login_ldap_failure(client: AsyncClient, admin_token: str, monkeypatch):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"auth_backend": "ldap", "ldap_host": "ldap.example.com"}},
        headers=_auth(admin_token),
    )

    # ldap3 missing -> authenticate_ldap returns None -> fallback local fails (no such user) -> 401
    monkeypatch.setitem(sys.modules, "ldap3", None)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "x"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_test_radius_endpoint_no_host(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/system-settings/test-radius",
        json={"username": "u", "password": "p"},
        headers=_auth(admin_token),
    )
    # radius host not configured -> 400
    assert resp.status_code == 400
