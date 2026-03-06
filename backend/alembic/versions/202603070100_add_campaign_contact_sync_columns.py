"""Add synced_leads_count and last_contact_sync_at to campaigns table.

Revision ID: 202603070100
Revises: 202603060300
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "202603070100"
down_revision = "202603060300"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("campaigns", sa.Column("synced_leads_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("campaigns", sa.Column("last_contact_sync_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("campaigns", "last_contact_sync_at")
    op.drop_column("campaigns", "synced_leads_count")
