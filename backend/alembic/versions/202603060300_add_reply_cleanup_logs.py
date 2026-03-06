"""Add reply_cleanup_logs table for daily needs_reply cleanup tracking.

Revision ID: 202603060300
Revises: 202603060200
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "202603060300"
down_revision = "202603060200"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reply_cleanup_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_name", sa.String(255), nullable=True),
        sa.Column("replies_checked", sa.Integer(), default=0),
        sa.Column("replies_resolved", sa.Integer(), default=0),
        sa.Column("resolved_replies", sa.JSON(), nullable=True),
        sa.Column("errors", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("reply_cleanup_logs")
