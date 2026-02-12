"""Add telegram notification and event recovery fields.

- projects.telegram_chat_id: Per-project Telegram routing for operators
- processed_replies.telegram_sent_at: Track Telegram notification delivery (dedup)
- webhook_events.retry_count: Track processing retry attempts
- webhook_events.next_retry_at: Exponential backoff for retries
- webhook_events: index on processed for recovery loop queries

Revision ID: 202602121200
Revises: 202602121000
Create Date: 2026-02-12 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '202602121200'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Projects: per-project Telegram routing
    op.add_column('projects', sa.Column('telegram_chat_id', sa.String(100), nullable=True))
    
    # ProcessedReply: Telegram notification tracking
    op.add_column('processed_replies', sa.Column('telegram_sent_at', sa.DateTime(), nullable=True))
    
    # WebhookEventModel: retry/recovery fields
    op.add_column('webhook_events', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=True))
    op.add_column('webhook_events', sa.Column('next_retry_at', sa.DateTime(), nullable=True))
    
    # Index for recovery loop queries (find unprocessed events)
    op.create_index('ix_webhook_events_recovery', 'webhook_events', ['processed', 'created_at'], 
                     postgresql_where=sa.text('processed = false'))


def downgrade() -> None:
    op.drop_index('ix_webhook_events_recovery', table_name='webhook_events')
    op.drop_column('webhook_events', 'next_retry_at')
    op.drop_column('webhook_events', 'retry_count')
    op.drop_column('processed_replies', 'telegram_sent_at')
    op.drop_column('projects', 'telegram_chat_id')
