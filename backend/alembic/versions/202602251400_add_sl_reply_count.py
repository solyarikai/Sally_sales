"""Add sl_reply_count to campaigns for webhook/polling coordination.

Revision ID: 202602251400
Revises: 202602251200
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = "202602251400"
down_revision = "202602251200"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "campaigns",
        sa.Column("sl_reply_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("campaigns", "sl_reply_count")
