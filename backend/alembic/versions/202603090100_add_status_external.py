"""Add status_external to contacts and external_status_config to projects.

Revision ID: 202603090100
Revises: 202603070100
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "202603090100"
down_revision = "202603070100"
branch_labels = None
depends_on = None

RIZZULT_CONFIG = {
    "statuses": [
        "Recommended", "Interested", "Positive", "Meeting Booked",
        "Talks To Team", "Refuse", "Wrong Person", "Not Interested",
        "Not Qualified", "Former Positive"
    ],
    "default_status": "Recommended",
    "category_mapping": {
        "interested": "Interested",
        "meeting_request": "Positive",
        "not_interested": "Not Interested",
        "out_of_office": None,
        "wrong_person": "Wrong Person",
        "unsubscribe": "Refuse",
        "question": "Interested",
        "other": "Interested"
    },
    "internal_status_mapping": {
        "negotiating_meeting": "Positive",
        "scheduled": "Meeting Booked",
        "meeting_held": "Talks To Team",
        "qualified": "Talks To Team",
        "not_qualified": "Not Qualified"
    }
}


def upgrade():
    op.add_column("contacts", sa.Column("status_external", sa.String(100), nullable=True))
    op.create_index("ix_contacts_status_external", "contacts", ["status_external"])

    op.add_column("projects", sa.Column("external_status_config", sa.JSON(), nullable=True))

    # Seed Rizzult (project_id=22) config
    import json
    op.execute(
        sa.text(
            "UPDATE projects SET external_status_config = :config WHERE id = 22"
        ).bindparams(config=json.dumps(RIZZULT_CONFIG))
    )


def downgrade():
    op.drop_index("ix_contacts_status_external", table_name="contacts")
    op.drop_column("contacts", "status_external")
    op.drop_column("projects", "external_status_config")
