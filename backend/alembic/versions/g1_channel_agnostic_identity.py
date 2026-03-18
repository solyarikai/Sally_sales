"""Make lead_email nullable and fix dedup index for channel-agnostic identity.

GetSales LinkedIn contacts often have no email. The system must process replies
regardless of whether an email exists. This migration:
1. Makes lead_email nullable on processed_replies
2. Replaces the email-based dedup index with one that falls back to getsales_lead_uuid

Revision ID: g1_channel_agnostic
Revises: merge_followup_config
"""
from alembic import op
import sqlalchemy as sa

revision = "g1_channel_agnostic"
down_revision = "202603180100"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Make lead_email nullable
    op.alter_column(
        "processed_replies",
        "lead_email",
        existing_type=sa.String(255),
        nullable=True,
    )

    # 2. Drop old email-only dedup index
    op.drop_index("uq_processed_reply_content", table_name="processed_replies")

    # 3. Create new dedup index that falls back to getsales_lead_uuid when email is NULL
    # SmartLead replies: lead_email always present → dedup by email
    # GetSales replies without email: getsales_lead_uuid always present → dedup by UUID
    op.execute("""
        CREATE UNIQUE INDEX uq_reply_dedup
        ON processed_replies (
            COALESCE(lead_email, getsales_lead_uuid),
            COALESCE(campaign_id, ''),
            message_hash
        )
        WHERE message_hash IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_reply_dedup")
    op.create_index(
        "uq_processed_reply_content",
        "processed_replies",
        ["lead_email", "campaign_id", "message_hash"],
        unique=True,
    )
    op.alter_column(
        "processed_replies",
        "lead_email",
        existing_type=sa.String(255),
        nullable=False,
    )
