"""v4: remove webhook (F18), public_share (F22), health_scores (F23 simplified to frontend)

Revision ID: 008
Revises: 007
Create Date: 2026-06-06
"""

from typing import Sequence, Union
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove F18: Webhook tables
    op.execute("DROP TABLE IF EXISTS webhook_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS webhook_endpoints CASCADE")

    # Remove F22: Public share links
    op.execute("DROP TABLE IF EXISTS project_share_links CASCADE")

    # Remove F23: Health scores (simplified to frontend calculation in V4)
    op.execute("DROP TABLE IF EXISTS project_health_scores CASCADE")


def downgrade() -> None:
    # Restore F18: Webhooks
    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_endpoints (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            url TEXT NOT NULL,
            secret VARCHAR(200),
            events TEXT[] NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            retry_count INTEGER NOT NULL DEFAULT 0,
            last_triggered_at TIMESTAMPTZ,
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            endpoint_id UUID NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
            event_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            response_status INTEGER,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            delivered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Restore F22: Public share links
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_share_links (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            token VARCHAR(64) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ,
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_share_links_token ON project_share_links(token)")

    # Restore F23: Project health scores
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_health_scores (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            score INTEGER NOT NULL DEFAULT 100,
            overdue_ratio NUMERIC(5,2) NOT NULL DEFAULT 0,
            milestone_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
            active_member_ratio NUMERIC(5,2) NOT NULL DEFAULT 0,
            calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(project_id)
        )
    """)
