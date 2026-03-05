"""Add God Panel columns to campaigns table.

Revision ID: 202603050100
Revises: 202603040100
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "202603050100"
down_revision = "202603040100"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("campaigns", sa.Column("resolution_method", sa.String(50), nullable=True))
    op.add_column("campaigns", sa.Column("resolution_detail", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("first_seen_at", sa.DateTime(), nullable=True))
    op.add_column("campaigns", sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"))

    # Backfill first_seen_at from created_at
    op.execute("UPDATE campaigns SET first_seen_at = created_at WHERE first_seen_at IS NULL")


def downgrade():
    op.drop_column("campaigns", "acknowledged")
    op.drop_column("campaigns", "first_seen_at")
    op.drop_column("campaigns", "resolution_detail")
    op.drop_column("campaigns", "resolution_method")
