"""system_settings: key-value store for admin-configurable settings

Revision ID: 007
Revises: 006
Create Date: 2026-06-05
"""

from typing import Union
from collections.abc import Sequence

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            is_secret BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Seed default values (non-secret)
    op.execute("""
        INSERT INTO system_settings (key, value, is_secret) VALUES
            ('auth_backend', 'local', FALSE),
            ('ldap_host', '', FALSE),
            ('ldap_port', '389', FALSE),
            ('ldap_use_ssl', 'false', FALSE),
            ('ldap_use_tls', 'false', FALSE),
            ('ldap_bind_dn', '', FALSE),
            ('ldap_bind_password', '', TRUE),
            ('ldap_search_base', '', FALSE),
            ('ldap_search_filter', '(sAMAccountName={username})', FALSE),
            ('ldap_display_name_attr', 'displayName', FALSE),
            ('ldap_email_attr', 'mail', FALSE),
            ('radius_host', '', FALSE),
            ('radius_port', '1812', FALSE),
            ('radius_secret', '', TRUE),
            ('radius_timeout', '5', FALSE),
            ('site_name', 'WorkFlow', FALSE),
            ('allow_registration', 'true', FALSE),
            ('session_timeout_minutes', '60', FALSE)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_settings")
