"""create daily_tasks_archive table

Revision ID: 015
Revises: 014
Create Date: 2026-06-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# Reference existing enum type — do NOT create/drop it
_dailytaskstatus = ENUM(
    "pending", "in_progress", "done", "cancelled",
    name="dailytaskstatus",
    create_type=False,
)


def upgrade():
    op.create_table(
        "daily_tasks_archive",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", _dailytaskstatus, nullable=False),
        sa.Column("progress", sa.Integer, server_default="0", nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notify_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("work_minutes", sa.Integer, server_default="0", nullable=False),
        sa.Column("linked_task_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_daily_tasks_archive_user_id", "daily_tasks_archive", ["user_id"])
    op.create_index("ix_daily_tasks_archive_date", "daily_tasks_archive", ["date"])


def downgrade():
    op.drop_index("ix_daily_tasks_archive_date", table_name="daily_tasks_archive")
    op.drop_index("ix_daily_tasks_archive_user_id", table_name="daily_tasks_archive")
    op.drop_table("daily_tasks_archive")
