"""add tg_incoming_replies table

Revision ID: 202603250200
Revises: 202603250100
Create Date: 2026-03-25 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '202603250200'
down_revision: Union[str, None] = '202603250100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tg_incoming_replies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('tg_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('tg_recipients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('tg_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('tg_message_id', sa.Integer(), nullable=True),
        sa.Column('message_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_tg_incoming_replies_campaign', 'tg_incoming_replies', ['campaign_id'])
    op.create_index('ix_tg_incoming_replies_recipient', 'tg_incoming_replies', ['recipient_id'])
    op.create_index('ix_tg_incoming_replies_received', 'tg_incoming_replies', ['received_at'])


def downgrade() -> None:
    op.drop_table('tg_incoming_replies')
