"""Add calendly_config JSON column to projects for Calendly time slot integration.

Revision ID: 202603100100
Revises: 202603090400
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "202603100100"
down_revision = "202603090400"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("calendly_config", sa.JSON(), nullable=True))

    # Seed EasyStaff RU (project 40) with Calendly member config.
    # PAT tokens will be set manually via DB after deploy.
    op.execute("""
        UPDATE projects SET calendly_config = '{
          "members": [
            {"id": "ekaterina", "display_name": "Екатерина", "pat_token": "", "is_default": true},
            {"id": "eleonora", "display_name": "Элеонора", "pat_token": ""},
            {"id": "alexey", "display_name": "Алексей", "pat_token": ""}
          ]
        }' WHERE id = 40 AND calendly_config IS NULL
    """)


def downgrade():
    op.drop_column("projects", "calendly_config")
