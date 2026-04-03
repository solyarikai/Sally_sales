"""Add telegram_subscriptions table for multi-operator notifications.

Revision ID: 202602251200
Revises: f2a3b4c5d6e7
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = "202602251200"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS telegram_subscriptions (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            chat_id VARCHAR(100) NOT NULL,
            username VARCHAR(100),
            first_name VARCHAR(100),
            subscribed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tg_sub_project_chat
        ON telegram_subscriptions (project_id, chat_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_telegram_subscriptions_project_id
        ON telegram_subscriptions (project_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_telegram_subscriptions_chat_id
        ON telegram_subscriptions (chat_id)
    """)

    # Migrate existing project-level Telegram connections into subscriptions
    op.execute("""
        INSERT INTO telegram_subscriptions (project_id, chat_id, username, first_name, subscribed_at)
        SELECT id, telegram_chat_id, telegram_username, telegram_first_name, NOW()
        FROM projects
        WHERE telegram_chat_id IS NOT NULL AND deleted_at IS NULL
        ON CONFLICT (project_id, chat_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telegram_subscriptions")
