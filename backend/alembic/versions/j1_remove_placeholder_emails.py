"""Remove placeholder emails from LinkedIn-only contacts.

Converts gs_*@linkedin.placeholder emails to NULL in both
processed_replies and contacts tables. These were synthetic emails
created for LinkedIn-only GetSales contacts; now we store NULL instead.

Revision ID: j1_remove_placeholder_emails
Revises: i1_campaign_intelligence
"""
from alembic import op

revision = "j1_remove_placeholder_emails"
down_revision = "i1_campaign_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear placeholder emails from processed_replies
    op.execute(
        "UPDATE processed_replies SET lead_email = NULL WHERE lead_email LIKE '%@linkedin.placeholder'"
    )
    # Clear placeholder emails from contacts
    op.execute(
        "UPDATE contacts SET email = NULL WHERE email LIKE '%@linkedin.placeholder'"
    )


def downgrade() -> None:
    # Cannot restore original placeholder emails — they were synthetic.
    # The getsales_lead_uuid / getsales_id columns still identify these contacts.
    pass
