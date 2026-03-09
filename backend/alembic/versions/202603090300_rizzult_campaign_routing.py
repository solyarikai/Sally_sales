"""Rizzult campaign routing — ownership rules + GetSales senders for project 22.

Revision ID: 202603090300
Revises: 202603090200
Create Date: 2026-03-09
"""
from alembic import op

revision = "202603090300"
down_revision = "202603090200"
branch_labels = None
depends_on = None


def upgrade():
    # SmartLead tag + GetSales contains matching
    op.execute("""
        UPDATE projects SET campaign_ownership_rules =
          '{"prefixes": ["rizzult"], "contains": ["rizzult"], "smartlead_tags": ["Aleksandra"]}'
        WHERE id = 22
    """)

    # 6 LinkedIn senders
    op.execute("""
        UPDATE projects SET getsales_senders = '[
          "29fd2e4e-d218-4ddc-b733-630e68a98124",
          "91fb80ab-4430-4b07-bc19-330d3f4ac8fd",
          "41b709f2-6d25-46cc-91a5-7f15ce84f5a7",
          "2529a3dd-0dd1-4fc5-b4f3-7fdae203e454",
          "94aeceb5-12ca-4ed6-92ac-18ed4b3d937f",
          "4cbc70b5-4fb6-4a76-9088-f50a4ef096e7"
        ]' WHERE id = 22
    """)


def downgrade():
    op.execute("UPDATE projects SET campaign_ownership_rules = NULL WHERE id = 22")
    op.execute("UPDATE projects SET getsales_senders = NULL WHERE id = 22")
