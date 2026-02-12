"""Add reply tracking fields to contacts table.

- contacts.reply_category: Classification category (interested, not_interested, etc.)
- contacts.reply_sentiment: Derived sentiment (warm, cold, neutral)
- contacts.funnel_stage: Current funnel stage (lead, contacted, replied, qualified)
- contacts.smartlead_raw: Raw Smartlead webhook payloads (JSON)
- contacts.getsales_raw: Raw GetSales webhook payloads (JSON)

Revision ID: 202602121300
Revises: 202602121200
Create Date: 2026-02-12 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '202602121300'
down_revision = '202602121200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reply classification and sentiment fields
    op.add_column('contacts', sa.Column('reply_category', sa.String(50), nullable=True))
    op.add_column('contacts', sa.Column('reply_sentiment', sa.String(20), nullable=True))
    op.add_column('contacts', sa.Column('funnel_stage', sa.String(50), nullable=True))
    
    # Add raw webhook data storage
    op.add_column('contacts', sa.Column('smartlead_raw', sa.JSON(), nullable=True))
    op.add_column('contacts', sa.Column('getsales_raw', sa.JSON(), nullable=True))
    
    # Add indexes for common query patterns
    op.create_index('ix_contacts_reply_category', 'contacts', ['reply_category'])
    op.create_index('ix_contacts_reply_sentiment', 'contacts', ['reply_sentiment'])
    op.create_index('ix_contacts_funnel_stage', 'contacts', ['funnel_stage'])
    
    # Backfill funnel_stage from existing status for replied contacts
    op.execute("UPDATE contacts SET funnel_stage = status WHERE has_replied = true AND status = 'replied'")


def downgrade() -> None:
    op.drop_index('ix_contacts_funnel_stage', 'contacts')
    op.drop_index('ix_contacts_reply_sentiment', 'contacts')
    op.drop_index('ix_contacts_reply_category', 'contacts')
    
    op.drop_column('contacts', 'getsales_raw')
    op.drop_column('contacts', 'smartlead_raw')
    op.drop_column('contacts', 'funnel_stage')
    op.drop_column('contacts', 'reply_sentiment')
    op.drop_column('contacts', 'reply_category')
