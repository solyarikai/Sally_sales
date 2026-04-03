"""Add channel_view to TgWarmupActionType enum.

Revision ID: 202604030100
Revises: 202604020200
Create Date: 2026-04-03
"""
from alembic import op

revision = "202604030100"
down_revision = "202604020200"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE tgwarmupactiontype ADD VALUE IF NOT EXISTS 'channel_view'")


def downgrade():
    # PostgreSQL does not support removing enum values; safe to leave
    pass
