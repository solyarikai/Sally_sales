"""Add lead_email and campaign_name to operator_corrections

Revision ID: 202603030100
Revises: 202603020300
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = "202603030100"
down_revision = "202603020300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operator_corrections", sa.Column("lead_email", sa.String(255), nullable=True))
    op.add_column("operator_corrections", sa.Column("campaign_name", sa.String(500), nullable=True))

    # Backfill from processed_replies
    op.execute("""
        UPDATE operator_corrections oc
        SET lead_email = pr.lead_email,
            campaign_name = pr.campaign_name
        FROM processed_replies pr
        WHERE oc.processed_reply_id = pr.id
          AND (oc.lead_email IS NULL OR oc.campaign_name IS NULL)
    """)


def downgrade() -> None:
    op.drop_column("operator_corrections", "campaign_name")
    op.drop_column("operator_corrections", "lead_email")
