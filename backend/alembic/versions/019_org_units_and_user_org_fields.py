"""create org_units + user_calendar_grants, add org fields to users

Revision ID: 019
Revises: 018
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "org_units",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "manager_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_org_units_parent_id", "org_units", ["parent_id"])
    op.create_index("ix_org_units_manager_user_id", "org_units", ["manager_user_id"])

    op.create_table(
        "user_calendar_grants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_unit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_calendar_grants_user_id", "user_calendar_grants", ["user_id"])
    op.create_index("ix_user_calendar_grants_org_unit_id", "user_calendar_grants", ["org_unit_id"])
    # 同一使用者對同一單位不重複授權
    op.create_unique_constraint("uq_user_calendar_grant", "user_calendar_grants", ["user_id", "org_unit_id"])

    op.add_column(
        "users",
        sa.Column(
            "org_unit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("users", sa.Column("position", sa.String(100), nullable=True))
    op.create_index("ix_users_org_unit_id", "users", ["org_unit_id"])


def downgrade():
    op.drop_index("ix_users_org_unit_id", table_name="users")
    op.drop_column("users", "position")
    op.drop_column("users", "org_unit_id")
    op.drop_constraint("uq_user_calendar_grant", "user_calendar_grants", type_="unique")
    op.drop_index("ix_user_calendar_grants_org_unit_id", table_name="user_calendar_grants")
    op.drop_index("ix_user_calendar_grants_user_id", table_name="user_calendar_grants")
    op.drop_table("user_calendar_grants")
    op.drop_index("ix_org_units_manager_user_id", table_name="org_units")
    op.drop_index("ix_org_units_parent_id", table_name="org_units")
    op.drop_table("org_units")
