"""add external_id (AD DN) to users

Revision ID: 021
Revises: 020
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    # external_id：AD 使用者的 DN（同步帶入）；local 帳號為 null。
    # 不設唯一約束：AD 重建/搬移可能讓 DN 變動，唯一性由 username 保證。
    op.add_column("users", sa.Column("external_id", sa.String(1000), nullable=True))
    op.create_index("ix_users_external_id", "users", ["external_id"])


def downgrade():
    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_column("users", "external_id")
