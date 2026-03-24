"""Add telegram_dm_accounts table for Telegram DM inbox.

Revision ID: 202603260100
Revises: None (auto-detect)
"""
from alembic import op
import sqlalchemy as sa

revision = "202603260100"
down_revision = "j1_remove_placeholder_emails"


def upgrade():
    op.create_table(
        "telegram_dm_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), default=1),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("string_session", sa.Text(), nullable=True),
        sa.Column("auth_status", sa.String(30), default="active"),
        sa.Column("is_connected", sa.Boolean(), default=False),
        sa.Column("last_connected_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("proxy_config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("telegram_dm_accounts")
