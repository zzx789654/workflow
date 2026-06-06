"""add recurrence_rule to projects

Revision ID: 012
Revises: 011
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column("recurrence_rule", sa.String(20), nullable=True),
    )


def downgrade():
    op.drop_column("projects", "recurrence_rule")
