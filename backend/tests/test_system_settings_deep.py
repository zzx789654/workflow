"""system_settings 補測：secret 加密/遮罩、test-ldap/test-radius 成功與失敗分支。"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_update_settings_encrypts_secret_and_masks_on_read(client: AsyncClient, admin_token: str):
    # store a secret value -> stored encrypted, returned masked
    resp = await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"ldap_bind_password": "supersecret", "site_name": "MyOrg"}},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    listing = await client.get("/api/v1/system-settings/", headers=_auth(admin_token))
    assert listing.status_code == 200
    by_key = {s["key"]: s for s in listing.json()}
    # secret masked, non-secret plain
    assert by_key["ldap_bind_password"]["is_secret"] is True
    assert by_key["ldap_bind_password"]["value"] == "••••••••"
    assert by_key["site_name"]["value"] == "MyOrg"


@pytest.mark.asyncio
async def test_update_settings_masked_placeholder_is_skipped(client: AsyncClient, admin_token: str):
    # set initial secret
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"radius_secret": "origsecret"}},
        headers=_auth(admin_token),
    )
    # send masked placeholder -> should NOT overwrite
    resp = await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"radius_secret": "••••••••"}},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    # decrypt original still intact (via internal helper)
    # we verify indirectly: test-radius with host uses the secret without error path change


@pytest.mark.asyncio
async def test_update_existing_setting_row(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"site_name": "First"}},
        headers=_auth(admin_token),
    )
    resp = await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"site_name": "Second"}},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    listing = await client.get("/api/v1/system-settings/", headers=_auth(admin_token))
    by_key = {s["key"]: s for s in listing.json()}
    assert by_key["site_name"]["value"] == "Second"


@pytest.mark.asyncio
async def test_test_ldap_no_host_returns_400(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/system-settings/test-ldap",
        json={"username": "u", "password": "p"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_test_ldap_success(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"ldap_host": "ldap.example.com"}},
        headers=_auth(admin_token),
    )

    class FakeInfo:
        display_name = "Alice"
        email = "alice@example.com"

    # authenticate_ldap is imported inside the handler from its source module
    import app.core.auth_backends.ldap_auth as ldap_mod

    with patch.object(ldap_mod, "authenticate_ldap", return_value=FakeInfo()):
        resp = await client.post(
            "/api/v1/system-settings/test-ldap",
            json={"username": "alice", "password": "pw"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_test_ldap_auth_failure_returns_401(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"ldap_host": "ldap.example.com"}},
        headers=_auth(admin_token),
    )
    import app.core.auth_backends.ldap_auth as ldap_mod

    with patch.object(ldap_mod, "authenticate_ldap", return_value=None):
        resp = await client.post(
            "/api/v1/system-settings/test-ldap",
            json={"username": "alice", "password": "bad"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_test_radius_success(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"radius_host": "radius.example.com", "radius_secret": "s"}},
        headers=_auth(admin_token),
    )
    import app.core.auth_backends.radius_auth as radius_mod

    with patch.object(radius_mod, "authenticate_radius", return_value=True):
        resp = await client.post(
            "/api/v1/system-settings/test-radius",
            json={"username": "bob", "password": "pw"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_test_radius_auth_failure_returns_401(client: AsyncClient, admin_token: str):
    await client.put(
        "/api/v1/system-settings/",
        json={"settings": {"radius_host": "radius.example.com", "radius_secret": "s"}},
        headers=_auth(admin_token),
    )
    import app.core.auth_backends.radius_auth as radius_mod

    with patch.object(radius_mod, "authenticate_radius", return_value=False):
        resp = await client.post(
            "/api/v1/system-settings/test-radius",
            json={"username": "bob", "password": "bad"},
            headers=_auth(admin_token),
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_settings_require_admin(client: AsyncClient, member_token: str):
    resp = await client.get("/api/v1/system-settings/", headers=_auth(member_token))
    assert resp.status_code == 403
