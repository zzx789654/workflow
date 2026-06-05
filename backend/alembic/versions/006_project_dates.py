"""project start_date and end_date columns

Revision ID: 006
Revises: 005
Create Date: 2026-06-05
"""

from typing import Union
from collections.abc import Sequence
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS start_date DATE,
            ADD COLUMN IF NOT EXISTS end_date DATE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS start_date")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS end_date")
