"""Update company profile with summary fields

Revision ID: 202601231900
Revises: 202601231800
Create Date: 2026-01-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '202601231900'
down_revision = '202601231800'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to kb_company_profile
    op.add_column('kb_company_profile', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('kb_company_profile', sa.Column('auto_update_summary', sa.Boolean(), server_default='1', nullable=True))
    op.add_column('kb_company_profile', sa.Column('what_we_do', sa.Text(), nullable=True))
    op.add_column('kb_company_profile', sa.Column('who_we_help', sa.Text(), nullable=True))
    op.add_column('kb_company_profile', sa.Column('why_us', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('kb_company_profile', 'summary')
    op.drop_column('kb_company_profile', 'auto_update_summary')
    op.drop_column('kb_company_profile', 'what_we_do')
    op.drop_column('kb_company_profile', 'who_we_help')
    op.drop_column('kb_company_profile', 'why_us')
