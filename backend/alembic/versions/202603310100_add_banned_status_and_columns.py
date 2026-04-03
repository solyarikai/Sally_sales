"""add banned status and columns

Revision ID: 202603310100
Revises: 202603260100
Create Date: 2026-03-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202603310100'
down_revision: Union[str, None] = '202603260100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'banned' value to tgaccountstatus enum
    op.execute("ALTER TYPE tgaccountstatus ADD VALUE IF NOT EXISTS 'banned'")
    # Add new columns
    op.add_column('tg_accounts', sa.Column('ban_reason', sa.String(255), nullable=True))
    op.add_column('tg_accounts', sa.Column('banned_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tg_accounts', 'banned_at')
    op.drop_column('tg_accounts', 'ban_reason')
    # Note: PostgreSQL does not support removing enum values
