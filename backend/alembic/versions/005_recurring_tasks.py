"""recurring tasks: add recurrence_rule and recurrence_end_date to tasks

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
    # ── F10: Recurring Tasks ────────────────────────────────────
    op.execute("""
        ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS recurrence_rule VARCHAR(20) NULL,
            ADD COLUMN IF NOT EXISTS recurrence_end_date DATE NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tasks
            DROP COLUMN IF EXISTS recurrence_rule,
            DROP COLUMN IF EXISTS recurrence_end_date
    """)
