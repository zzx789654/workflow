"""add parent_id to projects

Revision ID: 013
Revises: 012
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_projects_parent_id", "projects", ["parent_id"])


def downgrade():
    op.drop_index("ix_projects_parent_id", table_name="projects")
    op.drop_column("projects", "parent_id")
