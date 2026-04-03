"""Add follow_up_config JSON column to projects.

Revision ID: 202603100300
Revises: 202603100200
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "202603100300"
down_revision = "202603100200"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("follow_up_config", sa.JSON(), nullable=True))
    # Seed easystaff ru (project 40) with default 3-day follow-up
    op.execute("""
        UPDATE projects
        SET follow_up_config = '{"enabled": true, "delay_days": 3}'
        WHERE id = 40 AND follow_up_config IS NULL
    """)


def downgrade():
    op.drop_column("projects", "follow_up_config")
