"""milestone_logs: auto-record when task is completed

Revision ID: 005
Revises: 004
Create Date: 2026-06-03
"""

from typing import Sequence, Union
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS milestone_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
            task_title VARCHAR(500) NOT NULL,
            completed_by UUID REFERENCES users(id) ON DELETE SET NULL,
            completed_by_name VARCHAR(200),
            work_minutes INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_milestone_logs_project_id ON milestone_logs (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_milestone_logs_completed_at ON milestone_logs (completed_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS milestone_logs")
