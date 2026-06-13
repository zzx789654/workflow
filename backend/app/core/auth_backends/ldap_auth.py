"""LDAP/AD authentication backend.

Performs a simple bind (or search-bind) using ldap3.
Only validates credentials; does NOT create/modify local users
beyond fetching display_name and email from directory attributes.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LdapUserInfo:
    username: str
    display_name: str
    email: str


@dataclass
class LdapOu:
    dn: str  # 完整 DN，當穩定外部鍵（external_id）
    name: str  # OU 短名（ou 屬性）


@dataclass
class LdapUserEntry:
    dn: str  # 使用者物件的完整 DN（用於依父 OU 歸屬）
    username: str  # sAMAccountName（登入帳號）
    display_name: str
    email: str
    title: str  # 職位（title 屬性）


def list_users(
    host: str,
    port: int,
    use_ssl: bool,
    use_tls: bool,
    bind_dn: str,
    bind_password: str,
    search_base: str,
    username_attr: str = "sAMAccountName",
    display_name_attr: str = "displayName",
    email_attr: str = "mail",
    title_attr: str = "title",
) -> list[LdapUserEntry] | None:
    """以服務帳號列出 search_base 下所有使用者（person）。

    只讀目錄、不寫回 AD。回傳 [LdapUserEntry, ...]；連線/bind 失敗回 None。
    跳過沒有 username（sAMAccountName）的物件（如純電腦/服務帳號）。
    """
    try:
        from ldap3 import SUBTREE, Connection, Server, Tls

        tls_config = Tls() if use_tls else None
        server = Server(host, port=port, use_ssl=use_ssl, tls=tls_config, get_info=None)
        with Connection(server, user=bind_dn, password=bind_password, auto_bind=True) as conn:
            entries = conn.extend.standard.paged_search(
                search_base=search_base,
                # 人員物件：user 且非電腦（排除 computer objectClass）
                search_filter="(&(objectClass=user)(objectCategory=person))",
                search_scope=SUBTREE,
                attributes=[username_attr, display_name_attr, email_attr, title_attr],
                paged_size=500,
                generator=False,
            )
            users: list[LdapUserEntry] = []
            for entry in entries:
                dn = entry.get("dn")
                attrs = entry.get("attributes", {}) or {}
                username = _first_value(attrs.get(username_attr))
                if not dn or not username:
                    continue  # 無登入帳號者跳過
                users.append(
                    LdapUserEntry(
                        dn=dn,
                        username=username,
                        display_name=_first_value(attrs.get(display_name_attr)) or username,
                        email=_first_value(attrs.get(email_attr)),
                        title=_first_value(attrs.get(title_attr)),
                    )
                )
            return users
    except Exception as exc:
        logger.error("LDAP list_users error: %s", exc)
        return None


def list_ous(
    host: str,
    port: int,
    use_ssl: bool,
    use_tls: bool,
    bind_dn: str,
    bind_password: str,
    search_base: str,
) -> list[LdapOu] | None:
    """以服務帳號列出 search_base 下所有 organizationalUnit。

    只讀目錄、不寫回 AD。回傳 [LdapOu(dn, name), ...]；連線/bind 失敗回 None。
    DN 的父子層級由呼叫端（ad_sync）解析成樹。
    """
    try:
        from ldap3 import SUBTREE, Connection, Server, Tls

        from app.core.dn_utils import name_from_dn

        tls_config = Tls() if use_tls else None
        server = Server(host, port=port, use_ssl=use_ssl, tls=tls_config, get_info=None)
        with Connection(server, user=bind_dn, password=bind_password, auto_bind=True) as conn:
            # paged_search：>1000 OU 時 AD 預設只回 MaxPageSize 筆，需分頁迭代，
            # 否則大型目錄會被截斷。page_size=500 對各版本 AD 皆安全。
            entries = conn.extend.standard.paged_search(
                search_base=search_base,
                search_filter="(objectClass=organizationalUnit)",
                search_scope=SUBTREE,
                attributes=["ou", "name"],
                paged_size=500,
                generator=False,
            )
            ous: list[LdapOu] = []
            for entry in entries:
                dn = entry.get("dn")
                if not dn:
                    continue
                attrs = entry.get("attributes", {}) or {}
                # 取名優先序：ou 屬性 → name 屬性 → DN 第一段（已解跳脫）
                name = _first_value(attrs.get("ou")) or _first_value(attrs.get("name")) or name_from_dn(dn)
                ous.append(LdapOu(dn=dn, name=name))
            return ous
    except Exception as exc:
        logger.error("LDAP list_ous error: %s", exc)
        return None


def _first_value(v) -> str:
    """ldap3 屬性值可能是 str 或 list（多值屬性）；取第一個非空值。"""
    if not v:
        return ""
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v)


def _build_user_dn(bind_dn_template: str, username: str, search_base: str) -> str:
    """If bind_dn_template contains {username} substitute it; otherwise use as-is."""
    if "{username}" in bind_dn_template:
        return bind_dn_template.replace("{username}", username)
    return bind_dn_template


def authenticate_ldap(
    host: str,
    port: int,
    use_ssl: bool,
    use_tls: bool,
    bind_dn: str,
    bind_password: str,
    search_base: str,
    search_filter: str,
    display_name_attr: str,
    email_attr: str,
    username: str,
    password: str,
) -> LdapUserInfo | None:
    """
    Authenticate username/password against LDAP/AD.

    Flow:
      1. Bind with service account (bind_dn / bind_password).
      2. Search for the user entry using search_filter (with {username} replaced).
      3. Re-bind as the found user DN to verify their password.
      4. Return LdapUserInfo on success, None on failure.
    """
    try:
        from ldap3 import Connection, Server, Tls

        tls_config = Tls() if use_tls else None
        server = Server(host, port=port, use_ssl=use_ssl, tls=tls_config, get_info=None)

        # Service-account bind
        with Connection(server, user=bind_dn, password=bind_password, auto_bind=True) as conn:
            user_filter = search_filter.replace("{username}", username)
            conn.search(
                search_base=search_base,
                search_filter=user_filter,
                attributes=[display_name_attr, email_attr, "distinguishedName", "dn"],
            )
            if not conn.entries:
                logger.warning("LDAP: user '%s' not found in directory", username)
                return None
            entry = conn.entries[0]
            user_dn = entry.entry_dn

        # User password verification bind
        with Connection(server, user=user_dn, password=password) as user_conn:
            if not user_conn.bind():
                logger.warning("LDAP: bind failed for user DN '%s'", user_dn)
                return None

        # Extract attributes safely
        def _attr(e, name: str, fallback: str = "") -> str:
            try:
                v = getattr(e, name)
                return str(v.value) if v and v.value else fallback
            except Exception:
                return fallback

        return LdapUserInfo(
            username=username,
            display_name=_attr(entry, display_name_attr, username),
            email=_attr(entry, email_attr, ""),
        )

    except Exception as exc:
        logger.error("LDAP authentication error for '%s': %s", username, exc)
        return None
