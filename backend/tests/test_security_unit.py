"""Unit tests for app.core.security and auth backends (no DB)."""

import sys
import types
from unittest.mock import MagicMock

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ── security ──────────────────────────────────────────────────────
def test_password_hash_and_verify():
    h = hash_password("mypassword")
    assert h != "mypassword"
    assert verify_password("mypassword", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    assert decode_token(token) == "user-123"


def test_refresh_token_type():
    token = create_refresh_token("user-456")
    assert decode_token(token, expected_type="refresh") == "user-456"
    # access token has no refresh type
    access = create_access_token("user-456")
    assert decode_token(access, expected_type="refresh") is None


def test_decode_invalid_token():
    assert decode_token("not.a.jwt") is None


# ── ldap (mock ldap3) ─────────────────────────────────────────────
def test_authenticate_ldap_no_library(monkeypatch):
    # ldap3 not importable -> returns None gracefully
    monkeypatch.setitem(sys.modules, "ldap3", None)
    from app.core.auth_backends.ldap_auth import authenticate_ldap

    result = authenticate_ldap(
        host="h",
        port=389,
        use_ssl=False,
        use_tls=False,
        bind_dn="cn=admin",
        bind_password="pw",
        search_base="dc=x",
        search_filter="(uid={username})",
        display_name_attr="cn",
        email_attr="mail",
        username="bob",
        password="secret",
    )
    assert result is None


def test_authenticate_ldap_success(monkeypatch):
    """Mock ldap3 so the full success path runs."""
    fake_ldap3 = types.ModuleType("ldap3")

    class FakeEntry:
        entry_dn = "cn=bob,dc=x"

        def __getattr__(self, name):
            v = MagicMock()
            v.value = "Bob Example" if name == "cn" else "bob@example.com"
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

    from app.core.auth_backends.ldap_auth import authenticate_ldap

    result = authenticate_ldap(
        host="h",
        port=389,
        use_ssl=False,
        use_tls=True,
        bind_dn="cn=admin",
        bind_password="pw",
        search_base="dc=x",
        search_filter="(cn={username})",
        display_name_attr="cn",
        email_attr="mail",
        username="bob",
        password="secret",
    )
    assert result is not None
    assert result.username == "bob"


def test_authenticate_ldap_user_not_found(monkeypatch):
    fake_ldap3 = types.ModuleType("ldap3")

    class FakeConn:
        def __init__(self, *a, **k):
            self.entries = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def search(self, **k):
            return True

    fake_ldap3.Connection = FakeConn
    fake_ldap3.Server = lambda *a, **k: MagicMock()
    fake_ldap3.Tls = lambda *a, **k: MagicMock()
    monkeypatch.setitem(sys.modules, "ldap3", fake_ldap3)

    from app.core.auth_backends.ldap_auth import authenticate_ldap

    result = authenticate_ldap(
        host="h",
        port=389,
        use_ssl=False,
        use_tls=False,
        bind_dn="cn=admin",
        bind_password="pw",
        search_base="dc=x",
        search_filter="(cn={username})",
        display_name_attr="cn",
        email_attr="mail",
        username="ghost",
        password="secret",
    )
    assert result is None


# ── radius (mock pyrad) ───────────────────────────────────────────
def test_authenticate_radius_no_library(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrad.client", None)
    from app.core.auth_backends.radius_auth import authenticate_radius

    assert authenticate_radius("h", 1812, "secret", 5, "u", "p") is False


def test_authenticate_radius_accept(monkeypatch):
    pyrad = types.ModuleType("pyrad")
    client_mod = types.ModuleType("pyrad.client")
    dict_mod = types.ModuleType("pyrad.dictionary")

    class FakePacket(dict):
        def PwCrypt(self, pw):
            return pw

    class FakeClient:
        def __init__(self, *a, **k):
            self.timeout = 5

        def CreateAuthPacket(self, code):
            return FakePacket()

        def SendPacket(self, req):
            reply = MagicMock()
            reply.code = 2  # Access-Accept
            return reply

    client_mod.Client = FakeClient
    dict_mod.Dictionary = lambda *a, **k: MagicMock()
    monkeypatch.setitem(sys.modules, "pyrad", pyrad)
    monkeypatch.setitem(sys.modules, "pyrad.client", client_mod)
    monkeypatch.setitem(sys.modules, "pyrad.dictionary", dict_mod)

    from app.core.auth_backends.radius_auth import authenticate_radius

    assert authenticate_radius("h", 1812, "secret", 5, "u", "p") is True


def test_authenticate_radius_reject(monkeypatch):
    pyrad = types.ModuleType("pyrad")
    client_mod = types.ModuleType("pyrad.client")
    dict_mod = types.ModuleType("pyrad.dictionary")

    class FakePacket(dict):
        def PwCrypt(self, pw):
            return pw

    class FakeClient:
        def __init__(self, *a, **k):
            self.timeout = 5

        def CreateAuthPacket(self, code):
            return FakePacket()

        def SendPacket(self, req):
            reply = MagicMock()
            reply.code = 3  # Access-Reject
            return reply

    client_mod.Client = FakeClient
    dict_mod.Dictionary = lambda *a, **k: MagicMock()
    monkeypatch.setitem(sys.modules, "pyrad", pyrad)
    monkeypatch.setitem(sys.modules, "pyrad.client", client_mod)
    monkeypatch.setitem(sys.modules, "pyrad.dictionary", dict_mod)

    from app.core.auth_backends.radius_auth import authenticate_radius

    assert authenticate_radius("h", 1812, "secret", 5, "u", "p") is False
