"""Add telegram_first_name to projects table.

Revision ID: 202602121600
Revises: 202602121500
Create Date: 2026-02-12 22:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '202602121600'
down_revision = '202602121500'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c)"),
        {"t": table, "c": column}
    )
    return result.scalar()


def upgrade() -> None:
    if not _column_exists('projects', 'telegram_first_name'):
        op.add_column('projects', sa.Column('telegram_first_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'telegram_first_name')
