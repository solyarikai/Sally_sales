"""Add master_leads table

Revision ID: 202601232000
Revises: 202601231900
Create Date: 2026-01-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202601232000'
down_revision: Union[str, None] = '202601231900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'master_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        # Primary dedup keys
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        # Name fields
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(500), nullable=True),
        # Company fields
        sa.Column('company_name', sa.String(500), nullable=True),
        sa.Column('company_domain', sa.String(255), nullable=True),
        sa.Column('company_linkedin', sa.String(500), nullable=True),
        # Professional info
        sa.Column('job_title', sa.String(500), nullable=True),
        # Contact info
        sa.Column('phone', sa.String(100), nullable=True),
        # Location
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('city', sa.String(255), nullable=True),
        # Industry & other
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('company_size', sa.String(100), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        # Dynamic fields
        sa.Column('custom_fields', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('sources', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('enrichment_history', sa.JSON(), nullable=False, server_default='[]'),
        # Status
        sa.Column('is_verified', sa.Integer(), nullable=True, server_default='0'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_master_leads_id', 'master_leads', ['id'], unique=False)
    op.create_index('ix_master_leads_email', 'master_leads', ['email'], unique=False)
    op.create_index('ix_master_leads_linkedin_url', 'master_leads', ['linkedin_url'], unique=False)
    op.create_index('ix_master_leads_name_company', 'master_leads', ['first_name', 'last_name', 'company_name'], unique=False)
    op.create_index('ix_master_leads_full_name_company', 'master_leads', ['full_name', 'company_name'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_master_leads_full_name_company', table_name='master_leads')
    op.drop_index('ix_master_leads_name_company', table_name='master_leads')
    op.drop_index('ix_master_leads_linkedin_url', table_name='master_leads')
    op.drop_index('ix_master_leads_email', table_name='master_leads')
    op.drop_index('ix_master_leads_id', table_name='master_leads')
    op.drop_table('master_leads')
