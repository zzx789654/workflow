"""add token_version to users (token invalidation on password change / logout)

Revision ID: 018
Revises: 017
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    # server_default 留著即可（既有列回填 0）；新列由應用層 default=0 給值


def downgrade():
    op.drop_column("users", "token_version")
