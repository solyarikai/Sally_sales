"""Add TG outreach notification bot tables.

- tg_outreach_notif_subs: manager subscriptions for reply notifications
- tg_outreach_notif_log: tracks sent notifications for quick-reply routing

Revision ID: l1_tg_outreach_notif_bot
Revises: k1_meeting_reminders
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "l1_tg_outreach_notif_bot"
down_revision = "k1_meeting_reminders"


def upgrade() -> None:
    op.create_table(
        "tg_outreach_notif_subs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("chat_id", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("first_name", sa.String(200), nullable=True),
        sa.Column("notify_mode", sa.String(20), nullable=False, server_default="all"),
        sa.Column("daily_digest", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("digest_hour", sa.Integer, nullable=False, server_default="9"),
        sa.Column("campaign_ids", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "tg_outreach_notif_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("bot_message_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("chat_id", sa.String(100), nullable=False, index=True),
        sa.Column("recipient_id", sa.Integer, sa.ForeignKey("tg_recipients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_username", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Index("ix_notif_log_chat_msg", "chat_id", "bot_message_id"),
    )


def downgrade() -> None:
    op.drop_table("tg_outreach_notif_log")
    op.drop_table("tg_outreach_notif_subs")
