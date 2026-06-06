"""add depends_on_position to template_tasks

Revision ID: 009
Revises: 008
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'template_tasks',
        sa.Column('depends_on_position', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('template_tasks', 'depends_on_position')
