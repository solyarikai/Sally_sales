"""Add Google Sheets fields to reply_automations

Revision ID: 202601310400
Revises: 202601310300
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202601310400'
down_revision = '202601310300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add google_sheet_id and google_sheet_name columns to reply_automations
    op.add_column('reply_automations', sa.Column('google_sheet_id', sa.String(100), nullable=True))
    op.add_column('reply_automations', sa.Column('google_sheet_name', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('reply_automations', 'google_sheet_name')
    op.drop_column('reply_automations', 'google_sheet_id')
