"""daily_task linked_task_id

Revision ID: 011
Revises: 010
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_tasks",
        sa.Column(
            "linked_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_daily_tasks_linked_task_id", "daily_tasks", ["linked_task_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_tasks_linked_task_id", "daily_tasks")
    op.drop_column("daily_tasks", "linked_task_id")
