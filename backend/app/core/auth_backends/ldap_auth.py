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
