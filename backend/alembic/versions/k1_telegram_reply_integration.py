"""Telegram reply integration — extend ProcessedReply for Telegram identity.

- Add telegram_peer_id, telegram_account_id to processed_replies
- Add last_processed_at to telegram_dm_accounts (polling cursor)
- Recreate dedup index with 3-way COALESCE (email, getsales_uuid, telegram_peer_id)

Revision ID: k1_telegram_reply_integration
Revises: 202603260100
"""
from alembic import op
import sqlalchemy as sa

revision = "k1_telegram_reply_integration"
down_revision = "202603260100"


def upgrade():
    # 1. Add Telegram identity columns to processed_replies
    op.add_column("processed_replies",
        sa.Column("telegram_peer_id", sa.String(50), nullable=True))
    op.add_column("processed_replies",
        sa.Column("telegram_account_id", sa.Integer(),
                  sa.ForeignKey("telegram_dm_accounts.id"), nullable=True))
    op.create_index("ix_processed_replies_telegram_peer_id",
                    "processed_replies", ["telegram_peer_id"])

    # 2. Add polling cursor to telegram_dm_accounts
    op.add_column("telegram_dm_accounts",
        sa.Column("last_processed_at", sa.DateTime(), nullable=True))

    # 3. Recreate dedup index with 3-way COALESCE
    # Drop old index (may not exist in all environments — ignore if missing)
    try:
        op.drop_index("uq_reply_dedup", table_name="processed_replies")
    except Exception:
        pass

    op.execute("""
        CREATE UNIQUE INDEX uq_reply_dedup ON processed_replies (
            COALESCE(lead_email, getsales_lead_uuid, telegram_peer_id),
            COALESCE(campaign_id, ''),
            message_hash
        ) WHERE message_hash IS NOT NULL
    """)


def downgrade():
    try:
        op.drop_index("uq_reply_dedup", table_name="processed_replies")
    except Exception:
        pass

    op.execute("""
        CREATE UNIQUE INDEX uq_reply_dedup ON processed_replies (
            COALESCE(lead_email, getsales_lead_uuid),
            COALESCE(campaign_id, ''),
            message_hash
        ) WHERE message_hash IS NOT NULL
    """)

    op.drop_column("telegram_dm_accounts", "last_processed_at")
    op.drop_index("ix_processed_replies_telegram_peer_id", table_name="processed_replies")
    op.drop_column("processed_replies", "telegram_account_id")
    op.drop_column("processed_replies", "telegram_peer_id")
