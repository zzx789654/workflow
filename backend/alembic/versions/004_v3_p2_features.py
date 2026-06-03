"""v3 p2 features: weekly_reports, task_attachments, comment_reactions, task_checkins,
announcements, announcement_reads, webhooks, project_share_links

Revision ID: 004
Revises: 003
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Weekly Reports ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id),
            week_start DATE NOT NULL,
            week_end DATE NOT NULL,
            content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_weekly_reports_user_id ON weekly_reports (user_id)")

    # ── Task Attachments ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_attachments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER,
            content_type VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_attachments_task_id ON task_attachments (task_id)")

    # ── Comment Reactions ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS comment_reactions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            comment_id UUID NOT NULL REFERENCES task_comments(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            emoji VARCHAR(10) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (comment_id, user_id, emoji)
        )
    """)

    # ── Task Checkins ───────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_checkins (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_checkins_task_id ON task_checkins (task_id)")

    # ── Announcements ───────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title VARCHAR(200) NOT NULL,
            content TEXT,
            author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── Announcement Reads ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS announcement_reads (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (announcement_id, user_id)
        )
    """)

    # ── Webhooks ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100),
            url VARCHAR(500) NOT NULL,
            events JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT true,
            secret VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_webhooks_project_id ON webhooks (project_id)")

    # ── Project Share Links ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_share_links (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            token VARCHAR(64) NOT NULL UNIQUE,
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_share_links_token ON project_share_links (token)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_share_links")
    op.execute("DROP TABLE IF EXISTS webhooks")
    op.execute("DROP TABLE IF EXISTS announcement_reads")
    op.execute("DROP TABLE IF EXISTS announcements")
    op.execute("DROP TABLE IF EXISTS task_checkins")
    op.execute("DROP TABLE IF EXISTS comment_reactions")
    op.execute("DROP TABLE IF EXISTS task_attachments")
    op.execute("DROP TABLE IF EXISTS weekly_reports")
