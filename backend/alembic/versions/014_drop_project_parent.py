"""drop parent_id from projects

Revision ID: 014
Revises: 013
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_projects_parent_id", table_name="projects")
    op.drop_column("projects", "parent_id")


def downgrade():
    op.add_column(
        "projects",
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_projects_parent_id", "projects", ["parent_id"])
