"""Drop deprecated contact columns

Removes 12 columns that have been fully migrated to canonical fields:
  - has_replied → last_reply_at IS NOT NULL
  - reply_channel → ContactActivity.channel
  - reply_category → ProcessedReply.category
  - reply_sentiment → derived from status
  - funnel_stage → status
  - is_email_verified → email_verification_result
  - email_verified_at → email_verifications table
  - smartlead_status → platform_state["smartlead"]["status"]
  - getsales_status → platform_state["getsales"]["status"]
  - last_synced_at → platform_state[p]["last_synced"]
  - campaigns (JSON) → campaigns table + platform_state
  - gathering_details → provenance

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None

COLUMNS_TO_DROP = [
    'has_replied',
    'reply_channel',
    'reply_category',
    'reply_sentiment',
    'funnel_stage',
    'is_email_verified',
    'email_verified_at',
    'smartlead_status',
    'getsales_status',
    'last_synced_at',
    'campaigns',
    'gathering_details',
]

INDEXES_TO_DROP = [
    'ix_contacts_has_replied',
    'ix_contacts_reply_category',
    'ix_contacts_reply_sentiment',
    'ix_contacts_funnel_stage',
]


def _index_exists(name):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = :name"
    ), {"name": name})
    return result.scalar() is not None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    ), {"table": table, "column": column})
    return result.scalar() is not None


def upgrade():
    # Add partial index on last_reply_at for the has_replied replacement
    if not _index_exists('ix_contacts_replied'):
        op.create_index(
            'ix_contacts_replied', 'contacts', ['last_reply_at'],
            postgresql_where=sa.text("last_reply_at IS NOT NULL")
        )

    for idx in INDEXES_TO_DROP:
        if _index_exists(idx):
            op.drop_index(idx, table_name='contacts')

    for col in COLUMNS_TO_DROP:
        if _column_exists('contacts', col):
            op.drop_column('contacts', col)


def downgrade():
    op.add_column('contacts', sa.Column('has_replied', sa.Boolean(), server_default='false'))
    op.add_column('contacts', sa.Column('reply_channel', sa.String(50)))
    op.add_column('contacts', sa.Column('reply_category', sa.String(50)))
    op.add_column('contacts', sa.Column('reply_sentiment', sa.String(20)))
    op.add_column('contacts', sa.Column('funnel_stage', sa.String(50)))
    op.add_column('contacts', sa.Column('is_email_verified', sa.Boolean(), server_default='false'))
    op.add_column('contacts', sa.Column('email_verified_at', sa.DateTime(timezone=True)))
    op.add_column('contacts', sa.Column('smartlead_status', sa.String(50)))
    op.add_column('contacts', sa.Column('getsales_status', sa.String(50)))
    op.add_column('contacts', sa.Column('last_synced_at', sa.DateTime()))
    op.add_column('contacts', sa.Column('campaigns', sa.JSON()))
    op.add_column('contacts', sa.Column('gathering_details', sa.JSON()))

    op.execute("""
        UPDATE contacts SET
            has_replied = (last_reply_at IS NOT NULL),
            gathering_details = provenance,
            smartlead_status = platform_state->'smartlead'->>'status',
            getsales_status = platform_state->'getsales'->>'status'
        WHERE provenance IS NOT NULL OR platform_state IS NOT NULL OR last_reply_at IS NOT NULL
    """)

    op.create_index('ix_contacts_has_replied', 'contacts', ['has_replied'])
