"""Add thread_messages cache table and smartlead_lead_id to processed_replies

Revision ID: d8e2f3a4b5c6
Revises: c7d1e2f3a4b5
Create Date: 2026-02-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e2f3a4b5c6'
down_revision: Union[str, None] = '202602160050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add columns to processed_replies ---
    op.add_column('processed_replies', sa.Column('smartlead_lead_id', sa.String(100), nullable=True))
    op.add_column('processed_replies', sa.Column('thread_fetched_at', sa.DateTime(), nullable=True))
    op.create_index('ix_processed_replies_smartlead_lead_id', 'processed_replies', ['smartlead_lead_id'])

    # Backfill smartlead_lead_id from raw_webhook_data JSON
    op.execute("""
        UPDATE processed_replies
        SET smartlead_lead_id = raw_webhook_data->>'sl_email_lead_id'
        WHERE smartlead_lead_id IS NULL
          AND raw_webhook_data IS NOT NULL
          AND raw_webhook_data->>'sl_email_lead_id' IS NOT NULL
          AND raw_webhook_data->>'sl_email_lead_id' != ''
    """)

    # --- Create thread_messages table ---
    op.create_table(
        'thread_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('reply_id', sa.Integer(), sa.ForeignKey('processed_replies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('channel', sa.String(50), server_default='email'),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('activity_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(50), server_default='smartlead'),
        sa.Column('activity_type', sa.String(50), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_thread_messages_reply_id', 'thread_messages', ['reply_id'])


def downgrade() -> None:
    op.drop_table('thread_messages')
    op.drop_index('ix_processed_replies_smartlead_lead_id', table_name='processed_replies')
    op.drop_column('processed_replies', 'thread_fetched_at')
    op.drop_column('processed_replies', 'smartlead_lead_id')
