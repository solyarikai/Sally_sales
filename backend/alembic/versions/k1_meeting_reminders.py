"""Add reminder tracking columns to meetings table.

Revision ID: k1
Revises: j1
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "k1"
down_revision = "j1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("meetings", sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meetings", sa.Column("reminder_2h_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("meetings", "reminder_2h_sent_at")
    op.drop_column("meetings", "reminder_24h_sent_at")
