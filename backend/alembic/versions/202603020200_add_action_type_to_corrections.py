"""Add action_type to operator_corrections for tracking all operator actions.

Revision ID: 202603020200
Revises: 202603020100
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "202603020200"
down_revision = "202603020100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "operator_corrections",
        sa.Column("action_type", sa.String(30), nullable=True),
    )
    # Backfill: all existing records are send actions
    op.execute("UPDATE operator_corrections SET action_type = 'send' WHERE action_type IS NULL")
    op.alter_column("operator_corrections", "action_type", nullable=False, server_default="send")


def downgrade() -> None:
    op.drop_column("operator_corrections", "action_type")
