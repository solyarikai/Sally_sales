"""Add telegram_registrations table and telegram_username to projects.

Revision ID: 202602121500
Revises: 202602121400
Create Date: 2026-02-12 21:15:00
"""
from alembic import op
import sqlalchemy as sa

revision = '202602121500'
down_revision = '202602121400'
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": table_name}
    )
    return result.scalar()


def _column_exists(table, column):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c)"),
        {"t": table, "c": column}
    )
    return result.scalar()


def upgrade() -> None:
    # Create telegram_registrations table
    if not _table_exists('telegram_registrations'):
        op.create_table(
            'telegram_registrations',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('telegram_username', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('telegram_chat_id', sa.String(100), nullable=False),
            sa.Column('telegram_first_name', sa.String(100), nullable=True),
            sa.Column('registered_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # Add telegram_username to projects table
    if not _column_exists('projects', 'telegram_username'):
        op.add_column('projects', sa.Column('telegram_username', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'telegram_username')
    op.drop_table('telegram_registrations')
