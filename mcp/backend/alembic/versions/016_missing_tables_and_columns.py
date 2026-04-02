"""Add missing tables (mcp_replies, mcp_conversation_logs) and password_hash column.

These tables/columns exist in ORM models but were never created by earlier migrations.
They exist on production servers via manual SQL — this migration makes fresh deploys work.

Revision ID: 016_missing_tables
Revises: 015_smartlead_accounts_cache
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "016_missing_tables"
down_revision = "015_smartlead_accounts_cache"


def upgrade() -> None:
    # ── password_hash column on mcp_users (IF NOT EXISTS for idempotency) ──
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_cols = [c["name"] for c in inspector.get_columns("mcp_users")]
    if "password_hash" not in existing_cols:
        op.add_column("mcp_users", sa.Column("password_hash", sa.String(255), nullable=True))

    # ── mcp_conversation_logs table ──
    existing_tables = inspector.get_table_names()
    if "mcp_conversation_logs" in existing_tables:
        return  # Tables already exist from manual SQL — skip
    op.create_table(
        "mcp_conversation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("mcp_users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("method", sa.String(100), nullable=True),
        sa.Column("message_type", sa.String(50), nullable=True),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mcp_conversation_logs_user", "mcp_conversation_logs", ["user_id"])
    op.create_index("ix_mcl_user_session", "mcp_conversation_logs", ["user_id", "session_id"])
    op.create_index("ix_mcl_created", "mcp_conversation_logs", ["created_at"])

    # ── mcp_replies table ──
    op.create_table(
        "mcp_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lead_email", sa.String(255), nullable=True),
        sa.Column("lead_name", sa.String(255), nullable=True),
        sa.Column("lead_company", sa.String(255), nullable=True),
        sa.Column("campaign_name", sa.String(500), nullable=True),
        sa.Column("campaign_external_id", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), server_default="smartlead"),
        sa.Column("channel", sa.String(50), server_default="email"),
        sa.Column("email_subject", sa.String(500), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("category_confidence", sa.String(20), nullable=True),
        sa.Column("classification_reasoning", sa.Text(), nullable=True),
        sa.Column("draft_reply", sa.Text(), nullable=True),
        sa.Column("draft_subject", sa.String(500), nullable=True),
        sa.Column("draft_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_status", sa.String(50), nullable=True),
        sa.Column("needs_reply", sa.Boolean(), server_default="true"),
        sa.Column("tracking_enabled", sa.Boolean(), server_default="true"),
        sa.Column("smartlead_lead_id", sa.String(100), nullable=True),
        sa.Column("message_hash", sa.String(32), nullable=True),
        sa.Column("telegram_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_webhook_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mcp_replies_project", "mcp_replies", ["project_id"])
    op.create_index("ix_mcp_replies_campaign", "mcp_replies", ["campaign_id"])
    op.create_index("ix_mcp_replies_lead_email", "mcp_replies", ["lead_email"])
    op.create_index("ix_mcp_replies_campaign_name", "mcp_replies", ["campaign_name"])
    op.create_index("ix_mcp_replies_category", "mcp_replies", ["category"])
    op.create_index("ix_mcp_replies_message_hash", "mcp_replies", ["message_hash"])
    op.create_index("ix_mcp_reply_project_category", "mcp_replies", ["project_id", "category"])
    op.create_index("ix_mcp_reply_needs_reply", "mcp_replies", ["project_id", "needs_reply"])
    op.create_index("uq_mcp_reply_dedup", "mcp_replies", ["lead_email", "campaign_external_id", "message_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("mcp_replies")
    op.drop_table("mcp_conversation_logs")
    op.drop_column("mcp_users", "password_hash")
