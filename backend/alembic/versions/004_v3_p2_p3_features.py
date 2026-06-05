"""v3 p2/p3 features: weekly_reports, view_preferences, bulk_ops, attachments,
   workload, recurring, checkins, emoji_reactions, announcements, webhooks,
   public_share, health_scores

Revision ID: 004
Revises: 003
Create Date: 2026-06-04
"""

from typing import Sequence, Union
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── F10: Recurring rules ─────────────────────────────────────
    op.execute("""
        ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS recurrence_rule VARCHAR(200),
            ADD COLUMN IF NOT EXISTS recurrence_parent_id UUID REFERENCES tasks(id) ON DELETE SET NULL
    """)

    # ── F11: Task attachments ────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_attachments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename VARCHAR(500) NOT NULL,
            content_type VARCHAR(200) NOT NULL DEFAULT 'application/octet-stream',
            file_size INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_attachments_task_id ON task_attachments(task_id)")

    # ── F14: Emoji reactions ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS comment_reactions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            comment_id UUID NOT NULL REFERENCES task_comments(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            emoji VARCHAR(10) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(comment_id, user_id, emoji)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_comment_reactions_comment_id ON comment_reactions(comment_id)")

    # ── F15: Task check-ins ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_checkins (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_checkins_task_id ON task_checkins(task_id)")

    # ── F17: Announcements ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS announcement_reads (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(announcement_id, user_id)
        )
    """)

    # ── F18: Webhooks ─────────────────────────────────────────────
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

    # ── F22: Public share links ──────────────────────────────────
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

    # ── F23: Project health scores ───────────────────────────────
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


def downgrade() -> None:
    for tbl in [
        "project_health_scores",
        "project_share_links",
        "webhook_deliveries",
        "webhook_endpoints",
        "announcement_reads",
        "announcements",
        "task_checkins",
        "comment_reactions",
        "task_attachments",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS recurrence_rule")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS recurrence_parent_id")
