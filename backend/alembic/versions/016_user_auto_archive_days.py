"""add auto_archive_days to users

Revision ID: 016
Revises: 015
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auto_archive_days", sa.Integer, server_default="0", nullable=False),
    )


def downgrade():
    op.drop_column("users", "auto_archive_days")
