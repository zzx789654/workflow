"""v3 p1 features: subtasks, time_logs, notifications, custom fields, task_dependencies

Revision ID: 003
Revises: 002
Create Date: 2026-06-02
"""
from typing import Sequence, Union
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── F02: Subtasks ──────────────────────────────────────────
    op.execute("""
        ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS parent_task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
            ADD COLUMN IF NOT EXISTS subtask_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS subtask_done_count INTEGER NOT NULL DEFAULT 0
    """)

    # ── F07: Time logs ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS time_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            minutes INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_logs_task_id ON time_logs (task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_logs_user_id ON time_logs (user_id)")

    # ── F03: Notifications ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            actor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            ref_id UUID,
            ref_type VARCHAR(50),
            message TEXT NOT NULL,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)")

    # ── F05: Custom fields ─────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_fields (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            field_type VARCHAR(20) NOT NULL DEFAULT 'text',
            options JSONB,
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_field_values (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            field_id UUID NOT NULL REFERENCES project_fields(id) ON DELETE CASCADE,
            value TEXT,
            UNIQUE (task_id, field_id)
        )
    """)

    # ── F06: Task dependencies ────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            from_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            to_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            dep_type VARCHAR(20) NOT NULL DEFAULT 'finish_to_start',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (from_task_id, to_task_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_dependencies")
    op.execute("DROP TABLE IF EXISTS task_field_values")
    op.execute("DROP TABLE IF EXISTS project_fields")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS time_logs")
    op.execute("""
        ALTER TABLE tasks
            DROP COLUMN IF EXISTS parent_task_id,
            DROP COLUMN IF EXISTS subtask_count,
            DROP COLUMN IF EXISTS subtask_done_count
    """)
