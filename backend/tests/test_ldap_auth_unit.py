"""ldap_auth 內部分支單元測試（純單元，mock ldap3，不碰 DB/HTTP）。

涵蓋 authenticate_ldap / list_users / list_ous 的成功與各失敗分支，
以及 _first_value / _build_user_dn 純函式，補足遠端目錄連線路徑的覆蓋率。
"""

import sys
import types
from unittest.mock import MagicMock

from app.core.auth_backends import ldap_auth
from app.core.auth_backends.ldap_auth import (
    LdapOu,
    LdapUserEntry,
    LdapUserInfo,
    _build_user_dn,
    _first_value,
    authenticate_ldap,
    list_ous,
    list_users,
)

# ── 通用假 ldap3 模組工廠 ──────────────────────────────────────


def _install_fake_ldap3(monkeypatch, conn_cls):
    """把假 ldap3 模組塞進 sys.modules，讓被測函式 import 到它。

    conn_cls 是要當成 ldap3.Connection 的類別；Server/Tls/SUBTREE 用 stub。
    """
    fake = types.ModuleType("ldap3")
    fake.Connection = conn_cls
    fake.Server = lambda *a, **k: MagicMock()
    fake.Tls = lambda *a, **k: MagicMock()
    fake.SUBTREE = "SUBTREE"
    monkeypatch.setitem(sys.modules, "ldap3", fake)
    return fake


def _auth_args(**over):
    base = dict(
        host="ldap.example.com",
        port=389,
        use_ssl=False,
        use_tls=False,
        bind_dn="cn=svc,dc=corp,dc=test",
        bind_password="svcpass",
        search_base="dc=corp,dc=test",
        search_filter="(sAMAccountName={username})",
        display_name_attr="displayName",
        email_attr="mail",
        username="alice",
        password="alicepass",
    )
    base.update(over)
    return base


def _list_args(**over):
    base = dict(
        host="ldap.example.com",
        port=389,
        use_ssl=False,
        use_tls=False,
        bind_dn="cn=svc,dc=corp,dc=test",
        bind_password="svcpass",
        search_base="dc=corp,dc=test",
    )
    base.update(over)
    return base


# ══ 純函式 ════════════════════════════════════════════════════


class TestFirstValue:
    def test_none_returns_empty(self):
        assert _first_value(None) == ""

    def test_empty_string_returns_empty(self):
        assert _first_value("") == ""

    def test_empty_list_returns_empty(self):
        assert _first_value([]) == ""

    def test_list_returns_first_as_str(self):
        assert _first_value(["a", "b"]) == "a"

    def test_list_with_non_str_coerced(self):
        assert _first_value([123]) == "123"

    def test_scalar_string_returned(self):
        assert _first_value("hello") == "hello"

    def test_scalar_non_str_coerced(self):
        assert _first_value(42) == "42"


class TestBuildUserDn:
    def test_template_substitutes_username(self):
        assert _build_user_dn("uid={username},dc=x", "bob", "dc=x") == "uid=bob,dc=x"

    def test_template_without_placeholder_returned_asis(self):
        assert _build_user_dn("cn=fixed,dc=x", "bob", "dc=x") == "cn=fixed,dc=x"


# ══ authenticate_ldap ════════════════════════════════════════


class TestAuthenticateLdap:
    def test_success_returns_userinfo(self, monkeypatch):
        class FakeEntry:
            entry_dn = "cn=alice,dc=corp,dc=test"

            def __getattr__(self, name):
                v = MagicMock()
                v.value = "Alice Wang" if name == "displayName" else "alice@corp.test"
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

        _install_fake_ldap3(monkeypatch, FakeConn)
        info = authenticate_ldap(**_auth_args())
        assert isinstance(info, LdapUserInfo)
        assert info.username == "alice"
        assert info.display_name == "Alice Wang"
        assert info.email == "alice@corp.test"

    def test_user_not_found_returns_none(self, monkeypatch):
        class FakeConn:
            def __init__(self, *a, **k):
                self.entries = []  # 找不到使用者

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def search(self, **k):
                return True

        _install_fake_ldap3(monkeypatch, FakeConn)
        assert authenticate_ldap(**_auth_args()) is None

    def test_password_bind_failure_returns_none(self, monkeypatch):
        class FakeEntry:
            entry_dn = "cn=alice,dc=corp,dc=test"

            def __getattr__(self, name):
                v = MagicMock()
                v.value = "x"
                return v

        class FakeConn:
            """service-account bind 成功（有 entries）；user bind 失敗。"""

            calls = {"n": 0}

            def __init__(self, *a, **k):
                FakeConn.calls["n"] += 1
                self._is_user_bind = FakeConn.calls["n"] >= 2
                self.entries = [] if self._is_user_bind else [FakeEntry()]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def search(self, **k):
                return True

            def bind(self):
                return False  # 密碼錯：user bind 失敗

        FakeConn.calls["n"] = 0
        _install_fake_ldap3(monkeypatch, FakeConn)
        assert authenticate_ldap(**_auth_args()) is None

    def test_attr_extraction_handles_exception_fallback(self, monkeypatch):
        """getattr 取屬性丟例外時，_attr 應吞掉並回 fallback（不整體爆掉）。"""

        class FakeEntry:
            entry_dn = "cn=alice,dc=corp,dc=test"

            def __getattr__(self, name):
                raise RuntimeError("attribute backend exploded")

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

        _install_fake_ldap3(monkeypatch, FakeConn)
        info = authenticate_ldap(**_auth_args())
        assert isinstance(info, LdapUserInfo)
        # display_name 取不到 → fallback 為 username；email 取不到 → ""
        assert info.display_name == "alice"
        assert info.email == ""

    def test_ldap3_missing_returns_none(self, monkeypatch):
        # import ldap3 失敗 → 整體 except → None
        monkeypatch.setitem(sys.modules, "ldap3", None)
        assert authenticate_ldap(**_auth_args()) is None

    def test_connection_raises_returns_none(self, monkeypatch):
        class FakeConn:
            def __init__(self, *a, **k):
                raise OSError("connection refused")

        _install_fake_ldap3(monkeypatch, FakeConn)
        assert authenticate_ldap(**_auth_args()) is None


# ══ list_users ═══════════════════════════════════════════════


class TestListUsers:
    def _conn_returning(self, entries):
        captured = entries

        class FakeStandard:
            def paged_search(self, **k):
                return captured

        class FakeExtend:
            standard = FakeStandard()

        class FakeConn:
            def __init__(self, *a, **k):
                self.extend = FakeExtend()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return FakeConn

    def test_success_parses_entries_and_multivalue(self, monkeypatch):
        entries = [
            {
                "dn": "CN=Alice,OU=Fin,DC=corp,DC=test",
                "attributes": {
                    "sAMAccountName": "alice",
                    "displayName": ["Alice Wang"],  # 多值 → 取第一個
                    "mail": "alice@corp.test",
                    "title": "Manager",
                },
            },
            {
                "dn": "CN=NoName,OU=Fin,DC=corp,DC=test",
                # 無 displayName → fallback 用 username
                "attributes": {"sAMAccountName": "noname", "mail": "", "title": ""},
            },
        ]
        _install_fake_ldap3(monkeypatch, self._conn_returning(entries))
        users = list_users(**_list_args())
        assert users is not None
        assert len(users) == 2
        assert isinstance(users[0], LdapUserEntry)
        assert users[0].username == "alice"
        assert users[0].display_name == "Alice Wang"
        assert users[0].title == "Manager"
        assert users[1].display_name == "noname"  # fallback

    def test_skips_entries_without_username_or_dn(self, monkeypatch):
        entries = [
            {"dn": "CN=NoUser,DC=corp,DC=test", "attributes": {"sAMAccountName": ""}},  # 無帳號→跳過
            {"dn": None, "attributes": {"sAMAccountName": "ghost"}},  # 無 dn→跳過
            {"dn": "CN=Ok,DC=corp,DC=test", "attributes": {"sAMAccountName": "ok"}},
        ]
        _install_fake_ldap3(monkeypatch, self._conn_returning(entries))
        users = list_users(**_list_args())
        assert [u.username for u in users] == ["ok"]

    def test_ldap3_missing_returns_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ldap3", None)
        assert list_users(**_list_args()) is None

    def test_connection_raises_returns_none(self, monkeypatch):
        class FakeConn:
            def __init__(self, *a, **k):
                raise OSError("bind failed")

        _install_fake_ldap3(monkeypatch, FakeConn)
        assert list_users(**_list_args()) is None


# ══ list_ous ═════════════════════════════════════════════════


class TestListOus:
    def _conn_returning(self, entries):
        captured = entries

        class FakeStandard:
            def paged_search(self, **k):
                return captured

        class FakeExtend:
            standard = FakeStandard()

        class FakeConn:
            def __init__(self, *a, **k):
                self.extend = FakeExtend()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return FakeConn

    def test_success_name_priority(self, monkeypatch):
        entries = [
            {"dn": "OU=Fin,DC=corp,DC=test", "attributes": {"ou": "財務", "name": "Finance"}},  # ou 優先
            {"dn": "OU=HR,DC=corp,DC=test", "attributes": {"ou": "", "name": "人資"}},  # 退 name
            {"dn": "OU=IT,DC=corp,DC=test", "attributes": {}},  # 退 DN 第一段
        ]
        _install_fake_ldap3(monkeypatch, self._conn_returning(entries))
        ous = list_ous(**_list_args())
        assert ous is not None
        assert isinstance(ous[0], LdapOu)
        assert ous[0].name == "財務"
        assert ous[1].name == "人資"
        assert ous[2].name == "IT"  # 來自 name_from_dn(dn)

    def test_skips_entries_without_dn(self, monkeypatch):
        entries = [
            {"dn": None, "attributes": {"ou": "ghost"}},  # 無 dn→跳過
            {"dn": "OU=Keep,DC=corp,DC=test", "attributes": {"ou": "Keep"}},
        ]
        _install_fake_ldap3(monkeypatch, self._conn_returning(entries))
        ous = list_ous(**_list_args())
        assert [o.name for o in ous] == ["Keep"]

    def test_ldap3_missing_returns_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ldap3", None)
        assert list_ous(**_list_args()) is None

    def test_connection_raises_returns_none(self, monkeypatch):
        class FakeConn:
            def __init__(self, *a, **k):
                raise OSError("bind failed")

        _install_fake_ldap3(monkeypatch, FakeConn)
        assert list_ous(**_list_args()) is None


def test_module_imports_cleanly():
    # 確保 dataclass 與函式皆可匯入（防 import 期回歸）
    assert ldap_auth.LdapUserInfo is LdapUserInfo
