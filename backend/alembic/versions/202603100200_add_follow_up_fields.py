"""Add follow-up tracking fields to processed_replies.

parent_reply_id links a follow-up draft to the original approved reply.
follow_up_number tracks which follow-up this is (1, 2, etc).

Revision ID: 202603100200
Revises: 202603100100
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "202603100200"
down_revision = "202603100100"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("processed_replies", sa.Column("parent_reply_id", sa.Integer(), sa.ForeignKey("processed_replies.id"), nullable=True))
    op.add_column("processed_replies", sa.Column("follow_up_number", sa.Integer(), nullable=True))
    op.create_index("ix_processed_replies_parent_reply_id", "processed_replies", ["parent_reply_id"])


def downgrade():
    op.drop_index("ix_processed_replies_parent_reply_id", "processed_replies")
    op.drop_column("processed_replies", "follow_up_number")
    op.drop_column("processed_replies", "parent_reply_id")
