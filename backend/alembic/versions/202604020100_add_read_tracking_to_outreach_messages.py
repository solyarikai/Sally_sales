"""add read_at and tg_message_id to tg_outreach_messages

Revision ID: 202604020100
Revises: 202603310100
Create Date: 2026-04-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202604020100'
down_revision: Union[str, None] = '202603310100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_outreach_messages', sa.Column('tg_message_id', sa.Integer(), nullable=True))
    op.add_column('tg_outreach_messages', sa.Column('read_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tg_outreach_messages', 'read_at')
    op.drop_column('tg_outreach_messages', 'tg_message_id')
