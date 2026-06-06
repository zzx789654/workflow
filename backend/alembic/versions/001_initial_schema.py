"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-01

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create all ENUM types first (pure SQL — no SQLAlchemy Enum object involved)
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'member', 'viewer')")
    op.execute("CREATE TYPE projectrole AS ENUM ('owner', 'manager', 'member', 'viewer')")
    op.execute("CREATE TYPE milestonestatus AS ENUM ('planned', 'in_progress', 'completed', 'cancelled')")
    op.execute("CREATE TYPE taskstatus AS ENUM ('todo', 'in_progress', 'review', 'done')")
    op.execute("CREATE TYPE taskpriority AS ENUM ('low', 'medium', 'high', 'urgent')")

    # Use raw SQL for all tables to avoid SQLAlchemy Enum type auto-create triggers
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email VARCHAR(254) NOT NULL UNIQUE,
            display_name VARCHAR(100) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role userrole NOT NULL DEFAULT 'member',
            is_active BOOLEAN NOT NULL DEFAULT true,
            avatar_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_users_email ON users (email)")

    op.execute("""
        CREATE TABLE projects (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            color VARCHAR(7) NOT NULL DEFAULT '#6366f1',
            is_archived BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE project_members (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role projectrole NOT NULL DEFAULT 'member',
            joined_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE milestones (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            status milestonestatus NOT NULL DEFAULT 'planned',
            due_date DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE tasks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            milestone_id UUID REFERENCES milestones(id) ON DELETE SET NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            status taskstatus NOT NULL DEFAULT 'todo',
            priority taskpriority NOT NULL DEFAULT 'medium',
            position INTEGER NOT NULL DEFAULT 0,
            due_date DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_tasks_project_status ON tasks (project_id, status)")

    op.execute("""
        CREATE TABLE task_assignees (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE task_comments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Alembic version tracking
    op.execute(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_comments")
    op.execute("DROP TABLE IF EXISTS task_assignees")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TABLE IF EXISTS milestones")
    op.execute("DROP TABLE IF EXISTS project_members")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS taskpriority")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS milestonestatus")
    op.execute("DROP TYPE IF EXISTS projectrole")
    op.execute("DROP TYPE IF EXISTS userrole")
