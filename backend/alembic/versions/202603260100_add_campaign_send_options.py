"""add campaign send options

Revision ID: 202603260100
Revises: 202603250200
Create Date: 2026-03-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202603260100'
down_revision: Union[str, None] = '202603250200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_campaigns', sa.Column('link_preview', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tg_campaigns', sa.Column('silent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tg_campaigns', sa.Column('delete_dialog_after', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('tg_campaigns', 'delete_dialog_after')
    op.drop_column('tg_campaigns', 'silent')
    op.drop_column('tg_campaigns', 'link_preview')
