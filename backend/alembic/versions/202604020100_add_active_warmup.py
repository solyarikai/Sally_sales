"""Add active warm-up fields to tg_accounts and tg_warmup_log table.

Revision ID: 202604020100
Revises: 202603180200
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "202604020100"
down_revision = "202603180200"
branch_labels = None
depends_on = None


def upgrade():
    # Add active warmup columns to tg_accounts
    op.add_column("tg_accounts", sa.Column("warmup_active", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("tg_accounts", sa.Column("warmup_started_at", sa.DateTime(), nullable=True))
    op.add_column("tg_accounts", sa.Column("warmup_actions_done", sa.Integer(), nullable=False, server_default="0"))

    # Create tg_warmup_log table
    op.create_table(
        "tg_warmup_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tg_warmup_log_account_at", "tg_warmup_log", ["account_id", "performed_at"])
    op.create_index("ix_tg_warmup_log_id", "tg_warmup_log", ["id"])


def downgrade():
    op.drop_table("tg_warmup_log")
    op.drop_column("tg_accounts", "warmup_actions_done")
    op.drop_column("tg_accounts", "warmup_started_at")
    op.drop_column("tg_accounts", "warmup_active")
