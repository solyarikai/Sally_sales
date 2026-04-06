"""Add last_spambot_check_at to tg_accounts.

Revision ID: 202604050100
Revises: 202604040100
Create Date: 2026-04-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202604050100'
down_revision: Union[str, None] = '202604040100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_accounts', sa.Column('last_spambot_check_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tg_accounts', 'last_spambot_check_at')
