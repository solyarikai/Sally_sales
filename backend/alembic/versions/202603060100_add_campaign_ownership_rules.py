"""Add campaign_ownership_rules to projects table.

Revision ID: 202603060100
Revises: 202603050100
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "202603060100"
down_revision = "202603050100"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("campaign_ownership_rules", sa.JSON(), nullable=True))

    # Seed ownership rules for all existing projects based on current _PROJECT_PREFIXES
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["inxy"]}' WHERE id = 48""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["easystaff"], "contains": ["- ES -", "- RU "]}' WHERE id = 40""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["mifort", "mft"]}' WHERE id = 21""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["squarefi"], "smartlead_tags": ["squarefi fedor"]}' WHERE id = 46""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["squarefi - es"]}' WHERE id = 47""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["tfp"]}' WHERE id = 13""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["rizzult"]}' WHERE id = 22""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["archistruct"]}' WHERE id = 24""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["gwc"]}' WHERE id = 17""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["onsocial"]}' WHERE id = 42""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["palark"]}' WHERE id = 16""")
    op.execute("""UPDATE projects SET campaign_ownership_rules = '{"prefixes": ["paybis"]}' WHERE id = 15""")

    # Migrate existing campaign_auto_prefixes into campaign_ownership_rules (for projects not already seeded)
    # Only projects that have campaign_auto_prefixes set but no ownership_rules yet
    op.execute("""
        UPDATE projects
        SET campaign_ownership_rules = jsonb_build_object('prefixes', campaign_auto_prefixes::jsonb)
        WHERE campaign_auto_prefixes IS NOT NULL
          AND campaign_ownership_rules IS NULL
          AND deleted_at IS NULL
    """)


def downgrade():
    op.drop_column("projects", "campaign_ownership_rules")
