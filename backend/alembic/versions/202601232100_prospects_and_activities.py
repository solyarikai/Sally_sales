"""Create prospects and prospect_activities tables

Revision ID: 202601232100
Revises: 202601232000
Create Date: 2026-01-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '202601232100'
down_revision: Union[str, None] = '202601232000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename master_leads to prospects
    op.rename_table('master_leads', 'prospects')
    
    # Add new columns
    op.add_column('prospects', sa.Column('sent_to_instantly', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('prospects', sa.Column('sent_to_instantly_at', sa.DateTime(), nullable=True))
    op.add_column('prospects', sa.Column('instantly_campaign_id', sa.String(255), nullable=True))
    op.add_column('prospects', sa.Column('instantly_campaign_name', sa.String(255), nullable=True))
    op.add_column('prospects', sa.Column('sent_to_smartlead', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('prospects', sa.Column('sent_to_smartlead_at', sa.DateTime(), nullable=True))
    op.add_column('prospects', sa.Column('smartlead_campaign_id', sa.String(255), nullable=True))
    op.add_column('prospects', sa.Column('smartlead_campaign_name', sa.String(255), nullable=True))
    op.add_column('prospects', sa.Column('response_status', sa.String(50), nullable=True))
    op.add_column('prospects', sa.Column('response_at', sa.DateTime(), nullable=True))
    op.add_column('prospects', sa.Column('tags', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('prospects', sa.Column('notes', sa.Text(), nullable=True))
    
    # Create new indexes
    op.create_index('ix_prospects_sent_instantly', 'prospects', ['sent_to_instantly', 'sent_to_instantly_at'], unique=False)
    op.create_index('ix_prospects_created', 'prospects', ['created_at'], unique=False)
    
    # Create prospect_activities table
    op.create_table(
        'prospect_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('activity_data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE')
    )
    
    op.create_index('ix_prospect_activities_id', 'prospect_activities', ['id'], unique=False)
    op.create_index('ix_prospect_activities_prospect_id', 'prospect_activities', ['prospect_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_prospect_activities_prospect_id', table_name='prospect_activities')
    op.drop_index('ix_prospect_activities_id', table_name='prospect_activities')
    op.drop_table('prospect_activities')
    
    op.drop_index('ix_prospects_created', table_name='prospects')
    op.drop_index('ix_prospects_sent_instantly', table_name='prospects')
    
    # Remove new columns
    op.drop_column('prospects', 'notes')
    op.drop_column('prospects', 'tags')
    op.drop_column('prospects', 'response_at')
    op.drop_column('prospects', 'response_status')
    op.drop_column('prospects', 'smartlead_campaign_name')
    op.drop_column('prospects', 'smartlead_campaign_id')
    op.drop_column('prospects', 'sent_to_smartlead_at')
    op.drop_column('prospects', 'sent_to_smartlead')
    op.drop_column('prospects', 'instantly_campaign_name')
    op.drop_column('prospects', 'instantly_campaign_id')
    op.drop_column('prospects', 'sent_to_instantly_at')
    op.drop_column('prospects', 'sent_to_instantly')
    
    # Rename back
    op.rename_table('prospects', 'master_leads')
