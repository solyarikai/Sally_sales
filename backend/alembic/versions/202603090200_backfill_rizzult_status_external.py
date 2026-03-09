"""Backfill status_external for Rizzult (project_id=22) contacts.

Derivation logic:
  1. Contacts with internal meeting-stage status → use internal_status_mapping
  2. Contacts with replies → use category_mapping from most recent ProcessedReply
  3. Remaining contacts → default "Recommended"

Revision ID: 202603090200
Revises: 202603090100
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "202603090200"
down_revision = "202603090100"
branch_labels = None
depends_on = None

# Rizzult mappings (must match the config seeded in 202603090100)
INTERNAL_STATUS_MAPPING = {
    "negotiating_meeting": "Positive",
    "scheduled": "Meeting Booked",
    "meeting_held": "Talks To Team",
    "qualified": "Talks To Team",
    "not_qualified": "Not Qualified",
}

CATEGORY_MAPPING = {
    "interested": "Interested",
    "meeting_request": "Positive",
    "not_interested": "Not Interested",
    "wrong_person": "Wrong Person",
    "unsubscribe": "Refuse",
    "question": "Interested",
    "other": "Interested",
    # out_of_office → NULL (don't set)
}


def upgrade():
    conn = op.get_bind()

    # Step 1: Internal status overrides (highest priority)
    for internal_status, external_status in INTERNAL_STATUS_MAPPING.items():
        conn.execute(sa.text(
            "UPDATE contacts SET status_external = :ext "
            "WHERE project_id = 22 AND status = :st AND deleted_at IS NULL"
        ), {"ext": external_status, "st": internal_status})

    # Step 2: Category mapping from most recent reply (for contacts not yet set)
    # Get the most recent reply category per contact email
    conn.execute(sa.text("""
        UPDATE contacts c
        SET status_external = CASE pr.category
            WHEN 'interested' THEN 'Interested'
            WHEN 'meeting_request' THEN 'Positive'
            WHEN 'not_interested' THEN 'Not Interested'
            WHEN 'wrong_person' THEN 'Wrong Person'
            WHEN 'unsubscribe' THEN 'Refuse'
            WHEN 'question' THEN 'Interested'
            WHEN 'other' THEN 'Interested'
        END
        FROM (
            SELECT DISTINCT ON (lead_email) lead_email, category
            FROM processed_replies
            WHERE category IS NOT NULL
              AND category != 'out_of_office'
            ORDER BY lead_email, received_at DESC
        ) pr
        WHERE c.project_id = 22
          AND c.deleted_at IS NULL
          AND c.status_external IS NULL
          AND LOWER(c.email) = LOWER(pr.lead_email)
    """))

    # Step 3: Default "Recommended" for remaining contacts without replies
    conn.execute(sa.text(
        "UPDATE contacts SET status_external = 'Recommended' "
        "WHERE project_id = 22 AND deleted_at IS NULL AND status_external IS NULL"
    ))


def downgrade():
    op.execute(sa.text(
        "UPDATE contacts SET status_external = NULL WHERE project_id = 22"
    ))
