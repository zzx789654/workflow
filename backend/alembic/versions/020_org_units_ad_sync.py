"""add source/external_id/is_active to org_units for AD sync

Revision ID: 020
Revises: 019
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    # source：manual（手動建立，預設）/ ad（AD/OU 同步而來）。同步只碰 ad，永不動 manual。
    op.add_column("org_units", sa.Column("source", sa.String(20), server_default="manual", nullable=False))
    # external_id：ad 來源存該 OU 的 DN（穩定鍵，冪等對應）；manual 為 null。
    op.add_column("org_units", sa.Column("external_id", sa.String(1000), nullable=True))
    # is_active：AD 中 OU 消失時標 false（保留可人工複核，不硬刪、不孤兒化使用者）。
    op.add_column("org_units", sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False))
    # 以 external_id 查既有 ad 單位用
    op.create_index("ix_org_units_external_id", "org_units", ["external_id"])


def downgrade():
    op.drop_index("ix_org_units_external_id", table_name="org_units")
    op.drop_column("org_units", "is_active")
    op.drop_column("org_units", "external_id")
    op.drop_column("org_units", "source")
