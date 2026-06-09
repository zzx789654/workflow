"""add username + auth_source to users; make email nullable & non-unique

Revision ID: 017
Revises: 016
Create Date: 2026-06-09

username 成為登入鍵（全域唯一）；email 改為可空、非唯一的聯絡資訊。
既有帳號回填：username 由 email 前綴生成（衝突加尾碼），auth_source 一律 local。
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 先以可空方式加入 username + auth_source（auth_source 給 server_default 方便回填）
    op.add_column("users", sa.Column("username", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("auth_source", sa.String(20), server_default="local", nullable=False))

    # 2. 回填 username：email 前綴 → 清洗 → 去重（衝突加尾碼），無 email 用 user_<id前8碼>
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    used: set[str] = set()
    for row in rows:
        uid, email = row[0], row[1]
        base = ""
        if email and "@" in email:
            base = email.split("@")[0]
        base = re.sub(r"[^A-Za-z0-9_]", "", base or "")
        if not base:
            base = f"user_{str(uid).replace('-', '')[:8]}"
        candidate = base
        suffix = 1
        while candidate.lower() in used:
            candidate = f"{base}{suffix}"
            suffix += 1
        used.add(candidate.lower())
        conn.execute(
            sa.text("UPDATE users SET username = :u WHERE id = :id"),
            {"u": candidate, "id": uid},
        )

    # 3. username 設為 NOT NULL + 唯一索引
    op.alter_column("users", "username", existing_type=sa.String(100), nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # 4. email 去唯一、改可空。
    #    唯一性來自 migration 001 的「email VARCHAR NOT NULL UNIQUE」→ 自動產生的
    #    constraint users_email_key（非 ix_users_email，後者本就是普通 index）。
    #    用 IF EXISTS 容錯不同環境的命名差異。
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.alter_column("users", "email", existing_type=sa.String(254), nullable=True)

    # auth_source 已回填完成，移除 server_default（保持與 model 一致，由應用層給值）
    op.alter_column("users", "auth_source", existing_type=sa.String(20), server_default=None)


def downgrade():
    # email 還原為非空 + 唯一 constraint（對稱還原 001 的 users_email_key）
    op.alter_column("users", "email", existing_type=sa.String(254), nullable=False)
    op.create_unique_constraint("users_email_key", "users", ["email"])

    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "auth_source")
    op.drop_column("users", "username")
