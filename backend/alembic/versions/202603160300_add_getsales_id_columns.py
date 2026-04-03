"""Add getsales_lead_uuid, getsales_sender_uuid, getsales_conversation_uuid columns.

Extracts operational identifiers from raw_webhook_data into proper columns.
No consumer should parse raw_webhook_data for these again.

Revision ID: 202603160300
Revises: 202603160200
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "202603160300"
down_revision = "202603160200"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("processed_replies", sa.Column("getsales_lead_uuid", sa.String(100), nullable=True))
    op.add_column("processed_replies", sa.Column("getsales_sender_uuid", sa.String(100), nullable=True))
    op.add_column("processed_replies", sa.Column("getsales_conversation_uuid", sa.String(100), nullable=True))
    op.create_index("ix_processed_replies_gs_lead", "processed_replies", ["getsales_lead_uuid"])
    op.create_index("ix_processed_replies_gs_sender", "processed_replies", ["getsales_sender_uuid"])

    # Backfill from raw_webhook_data — handles both flat and nested formats
    # Flat keys (sync path): lead_uuid, sender_profile_uuid, linkedin_conversation_uuid
    # Nested keys (webhook path): contact->uuid, sender_profile->uuid, contact->linkedin_conversation_uuid
    op.execute("""
        UPDATE processed_replies SET
            getsales_lead_uuid = COALESCE(
                raw_webhook_data::jsonb->>'lead_uuid',
                raw_webhook_data::jsonb->'contact'->>'uuid',
                raw_webhook_data::jsonb->'lead'->>'uuid'
            ),
            getsales_sender_uuid = COALESCE(
                raw_webhook_data::jsonb->>'sender_profile_uuid',
                raw_webhook_data::jsonb->'sender_profile'->>'uuid',
                raw_webhook_data::jsonb->'automation'->>'sender_profile_uuid'
            ),
            getsales_conversation_uuid = COALESCE(
                raw_webhook_data::jsonb->>'linkedin_conversation_uuid',
                raw_webhook_data::jsonb->>'conversation_uuid',
                raw_webhook_data::jsonb->'contact'->>'linkedin_conversation_uuid'
            )
        WHERE source = 'getsales'
          AND raw_webhook_data IS NOT NULL
          AND getsales_lead_uuid IS NULL
    """)


def downgrade():
    op.drop_index("ix_processed_replies_gs_sender")
    op.drop_index("ix_processed_replies_gs_lead")
    op.drop_column("processed_replies", "getsales_conversation_uuid")
    op.drop_column("processed_replies", "getsales_sender_uuid")
    op.drop_column("processed_replies", "getsales_lead_uuid")
