"""v2 features: daily tasks, project templates, task execution fields, calendar labels

Revision ID: 002
Revises: 001
Create Date: 2026-06-01

"""

from typing import Sequence, Union
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Task: 新增執行紀錄欄位 ──────────────────────────────
    op.execute("""
        ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS start_date DATE,
            ADD COLUMN IF NOT EXISTS end_date DATE,
            ADD COLUMN IF NOT EXISTS actual_end_date DATE,
            ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0
    """)

    # ── DailyTask 標籤顏色 ENUM ─────────────────────────────
    op.execute("CREATE TYPE dailytaskstatus AS ENUM ('pending', 'in_progress', 'done', 'cancelled')")

    # ── DailyTask ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE daily_tasks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            status dailytaskstatus NOT NULL DEFAULT 'pending',
            progress INTEGER NOT NULL DEFAULT 0,
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            notify_at TIMESTAMPTZ,
            work_minutes INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_daily_tasks_user_date ON daily_tasks (user_id, date)")

    # ── DailyTask 標籤 ──────────────────────────────────────
    op.execute("""
        CREATE TABLE daily_task_labels (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            daily_task_id UUID NOT NULL REFERENCES daily_tasks(id) ON DELETE CASCADE,
            label VARCHAR(50) NOT NULL
        )
    """)

    # ── ProjectTemplate ─────────────────────────────────────
    op.execute("""
        CREATE TABLE project_templates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            color VARCHAR(7) NOT NULL DEFAULT '#6366f1',
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── TemplateTask ────────────────────────────────────────
    op.execute("""
        CREATE TABLE template_tasks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            template_id UUID NOT NULL REFERENCES project_templates(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            day_offset_start INTEGER NOT NULL DEFAULT 0,
            day_offset_end INTEGER,
            position INTEGER NOT NULL DEFAULT 0
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS template_tasks")
    op.execute("DROP TABLE IF EXISTS project_templates")
    op.execute("DROP TABLE IF EXISTS daily_task_labels")
    op.execute("DROP TABLE IF EXISTS daily_tasks")
    op.execute("DROP TYPE IF EXISTS dailytaskstatus")
    op.execute("""
        ALTER TABLE tasks
            DROP COLUMN IF EXISTS start_date,
            DROP COLUMN IF EXISTS end_date,
            DROP COLUMN IF EXISTS actual_end_date,
            DROP COLUMN IF EXISTS progress
    """)
