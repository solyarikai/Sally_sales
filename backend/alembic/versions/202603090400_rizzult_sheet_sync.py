"""Rizzult sheet sync config — project 22 gets Google Sheet sync to Replies 09/03 tab.

Revision ID: 202603090400
Revises: 202603090300
Create Date: 2026-03-09
"""
from alembic import op

revision = "202603090400"
down_revision = "202603090300"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE projects SET sheet_sync_config = '{
          "enabled": true,
          "sheet_id": "1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s",
          "replies_tab": "Replies 09/03",
          "reference_tab": "Replies 10.02",
          "row_format": "rizzult_28col",
          "exclude_ooo": true,
          "week_epoch": "2025-11-24"
        }' WHERE id = 22
    """)


def downgrade():
    op.execute("UPDATE projects SET sheet_sync_config = NULL WHERE id = 22")
