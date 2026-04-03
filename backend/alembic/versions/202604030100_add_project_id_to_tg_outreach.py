"""Add project_id to tg_accounts and tg_campaigns for project-scoped outreach.

Revision ID: 202604030100
Revises: k1_telegram_reply_integration
"""
from alembic import op
import sqlalchemy as sa

revision = "202604030100"
down_revision = "k1_telegram_reply_integration"


def upgrade():
    op.add_column("tg_accounts",
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"),
                  nullable=True))
    op.create_index("ix_tg_accounts_project_id", "tg_accounts", ["project_id"])

    op.add_column("tg_campaigns",
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"),
                  nullable=True))
    op.create_index("ix_tg_campaigns_project_id", "tg_campaigns", ["project_id"])


def downgrade():
    op.drop_index("ix_tg_campaigns_project_id", table_name="tg_campaigns")
    op.drop_column("tg_campaigns", "project_id")
    op.drop_index("ix_tg_accounts_project_id", table_name="tg_accounts")
    op.drop_column("tg_accounts", "project_id")
