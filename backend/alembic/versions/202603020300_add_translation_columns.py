"""Add translation columns to processed_replies

Revision ID: 202603020300
Revises: 202603020200
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "202603020300"
down_revision = "202603020200"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("processed_replies", sa.Column("detected_language", sa.String(10), nullable=True))
    op.add_column("processed_replies", sa.Column("translated_body", sa.Text(), nullable=True))
    op.add_column("processed_replies", sa.Column("translated_draft", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("processed_replies", "translated_draft")
    op.drop_column("processed_replies", "translated_body")
    op.drop_column("processed_replies", "detected_language")
