"""Add telegram_notification_config to projects for per-project compact notifications.

Revision ID: 202603120100
Revises: merge_followup_config
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "202603120100"
down_revision = "merge_followup_config"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("telegram_notification_config", sa.JSON(), nullable=True))
    # Configure Rizzult (project 22) with compact notifications per operator feedback
    op.execute("""
        UPDATE projects
        SET telegram_notification_config = '{"compact": true, "hide_fields": ["campaign", "company", "subject", "project", "inbox", "time"]}'
        WHERE id = 22 AND telegram_notification_config IS NULL
    """)


def downgrade():
    op.drop_column("projects", "telegram_notification_config")
