"""Mifort reporting setup — external statuses, sheet sync, campaign routing, senders.

Copies Rizzult reporting architecture to Mifort (project_id=21):
- external_status_config: same 10-status taxonomy as Rizzult
- sheet_sync_config: Google Sheet sync to 'Replies' tab
- campaign_ownership_rules: add contains + smartlead_tags (Paul)
- getsales_senders: add 4th sender (Valeriia Mutalava)
- telegram_notification_config: compact mode

Revision ID: 202603150100
Revises: 202603120100
Create Date: 2026-03-15
"""
import json
from alembic import op
import sqlalchemy as sa

revision = "202603150100"
down_revision = "202603120100"
branch_labels = None
depends_on = None

MIFORT_EXTERNAL_STATUS_CONFIG = {
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

MIFORT_SHEET_SYNC_CONFIG = {
    "enabled": True,
    "sheet_id": "1s0BI_UclVg5DI-GkLYcNgDw5d8YlU1WO5Y634KPHcnw",
    "replies_tab": "Replies",
    "row_format": "rizzult_28col",
    "exclude_ooo": True,
    "week_epoch": "2025-11-24"
}

MIFORT_GETSALES_SENDERS = [
    "0d22a72e-5e30-4f72-bac7-0fac29fe8121",  # Anna Reisberg
    "430e90e2-adfb-47d6-a986-3b8a75f4c80e",  # Lera Yurkoits
    "c58462db-beda-44a5-ba32-12e436d55bba",   # Sophia Powell
    "d4d17541-2b69-4cc3-acd5-cb39ce9df4b6"    # Valeriia Mutalava
]


def upgrade():
    # 1. External status config (same taxonomy as Rizzult)
    config_json = json.dumps(MIFORT_EXTERNAL_STATUS_CONFIG)
    op.execute(
        sa.text(
            "UPDATE projects SET external_status_config = cast(:config as json) WHERE id = 21"
        ).bindparams(config=config_json)
    )

    # 2. Google Sheet sync config
    sheet_json = json.dumps(MIFORT_SHEET_SYNC_CONFIG)
    op.execute(
        sa.text(
            "UPDATE projects SET sheet_sync_config = cast(:config as json) WHERE id = 21"
        ).bindparams(config=sheet_json)
    )

    # 3. Campaign routing — add contains + smartlead_tags to existing prefixes
    op.execute("""
        UPDATE projects SET campaign_ownership_rules =
          '{"prefixes": ["mifort", "mft"], "contains": ["mifort", "mft"], "smartlead_tags": ["Paul"]}'
        WHERE id = 21
    """)

    # 4. GetSales senders — 4 LinkedIn accounts
    senders_json = json.dumps(MIFORT_GETSALES_SENDERS)
    op.execute(
        sa.text(
            "UPDATE projects SET getsales_senders = cast(:config as json) WHERE id = 21"
        ).bindparams(config=senders_json)
    )

    # 5. Telegram notifications — compact mode
    op.execute("""
        UPDATE projects SET telegram_notification_config =
          '{"compact": true, "hide_fields": ["campaign", "company", "subject", "project", "inbox", "time"]}'
        WHERE id = 21
    """)


def downgrade():
    # Restore previous state: prefixes-only routing, 3 senders, no other configs
    op.execute("UPDATE projects SET external_status_config = NULL WHERE id = 21")
    op.execute("UPDATE projects SET sheet_sync_config = NULL WHERE id = 21")
    op.execute("""
        UPDATE projects SET campaign_ownership_rules =
          '{"prefixes": ["mifort", "mft"]}'
        WHERE id = 21
    """)
    op.execute("""
        UPDATE projects SET getsales_senders = '[
          "0d22a72e-5e30-4f72-bac7-0fac29fe8121",
          "430e90e2-adfb-47d6-a986-3b8a75f4c80e",
          "c58462db-beda-44a5-ba32-12e436d55bba"
        ]' WHERE id = 21
    """)
    op.execute("UPDATE projects SET telegram_notification_config = NULL WHERE id = 21")
