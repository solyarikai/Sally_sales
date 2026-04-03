"""Add fireflies_config column to projects table.

Revision ID: 202603162200
Revises: 202603162100
Create Date: 2026-03-16 22:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "202603162200"
down_revision = "202603162100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("fireflies_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "fireflies_config")
