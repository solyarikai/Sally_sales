"""Add auto_enrich_config to projects

Revision ID: 202602111000
Revises: 202602091900
Create Date: 2026-02-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '202602111000'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('auto_enrich_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'auto_enrich_config')
