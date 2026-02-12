"""Add missing performance indexes for processed_replies

The list_replies and get_reply_stats endpoints run multiple queries against
processed_replies. With 32K+ rows, missing indexes on campaign_name and
received_at cause full table scans and timeouts.

Revision ID: 202602121400
Revises: 202602121300
Create Date: 2026-02-12 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202602121400'
down_revision = '202602121300'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # campaign_name: used in IN() filter (project campaign_filters, campaign_names param)
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_campaign_name "
        "ON processed_replies (campaign_name)"
    ))

    # received_at: used in needs_reply filter
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_received_at "
        "ON processed_replies (received_at)"
    ))

    # Composite: processed_at DESC for pagination ORDER BY (covers the main listing query)
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_processed_at_desc "
        "ON processed_replies (processed_at DESC)"
    ))

    # Composite: approval_status + processed_at for the common "pending replies" filter
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_status_processed "
        "ON processed_replies (approval_status, processed_at DESC)"
    ))

    # Ensure earlier indexes exist too (idempotent)
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_processed_at "
        "ON processed_replies (processed_at)"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_processed_replies_approval_status "
        "ON processed_replies (approval_status)"
    ))


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_status_processed"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_processed_at_desc"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_received_at"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_campaign_name"))
