"""Add soft delete fields (is_active, deleted_at) to all models

Revision ID: 202601270100
Revises: 202601250300
Create Date: 2026-01-27

This migration standardizes soft delete across all models by adding:
- is_active: Boolean column (default True)
- deleted_at: DateTime column (nullable)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '202601270100'
down_revision = '202601250300_add_environments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prospects - add is_active
    op.add_column('prospects', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.create_index('ix_prospects_is_active', 'prospects', ['is_active'])
    op.create_index('ix_prospects_deleted_at', 'prospects', ['deleted_at'])
    
    # Datasets - add is_active
    op.add_column('datasets', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.create_index('ix_datasets_is_active', 'datasets', ['is_active'])
    op.create_index('ix_datasets_deleted_at', 'datasets', ['deleted_at'])
    
    # Folders - add is_active and deleted_at
    op.add_column('folders', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('folders', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_folders_is_active', 'folders', ['is_active'])
    op.create_index('ix_folders_deleted_at', 'folders', ['deleted_at'])
    
    # KB Products - add deleted_at
    op.add_column('kb_products', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_products_is_active', 'kb_products', ['is_active'])
    op.create_index('ix_kb_products_deleted_at', 'kb_products', ['deleted_at'])
    
    # KB Segments - add deleted_at
    op.add_column('kb_segments', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_segments_is_active', 'kb_segments', ['is_active'])
    op.create_index('ix_kb_segments_deleted_at', 'kb_segments', ['deleted_at'])
    
    # KB Competitors - add is_active and deleted_at
    op.add_column('kb_competitors', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('kb_competitors', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_competitors_is_active', 'kb_competitors', ['is_active'])
    op.create_index('ix_kb_competitors_deleted_at', 'kb_competitors', ['deleted_at'])
    
    # KB Case Studies - add is_active and deleted_at
    op.add_column('kb_case_studies', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('kb_case_studies', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_case_studies_is_active', 'kb_case_studies', ['is_active'])
    op.create_index('ix_kb_case_studies_deleted_at', 'kb_case_studies', ['deleted_at'])
    
    # KB Voice Tones - add is_active and deleted_at
    op.add_column('kb_voice_tones', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('kb_voice_tones', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_voice_tones_is_active', 'kb_voice_tones', ['is_active'])
    op.create_index('ix_kb_voice_tones_deleted_at', 'kb_voice_tones', ['deleted_at'])
    
    # Update all existing records to have is_active=True
    op.execute("UPDATE prospects SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE datasets SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE folders SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE kb_competitors SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE kb_case_studies SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE kb_voice_tones SET is_active = true WHERE is_active IS NULL")
    
    # Make is_active NOT NULL after populating
    op.alter_column('prospects', 'is_active', nullable=False)
    op.alter_column('datasets', 'is_active', nullable=False)
    op.alter_column('folders', 'is_active', nullable=False)
    op.alter_column('kb_competitors', 'is_active', nullable=False)
    op.alter_column('kb_case_studies', 'is_active', nullable=False)
    op.alter_column('kb_voice_tones', 'is_active', nullable=False)


def downgrade() -> None:
    # Remove indexes and columns in reverse order
    
    # KB Voice Tones
    op.drop_index('ix_kb_voice_tones_deleted_at', 'kb_voice_tones')
    op.drop_index('ix_kb_voice_tones_is_active', 'kb_voice_tones')
    op.drop_column('kb_voice_tones', 'deleted_at')
    op.drop_column('kb_voice_tones', 'is_active')
    
    # KB Case Studies
    op.drop_index('ix_kb_case_studies_deleted_at', 'kb_case_studies')
    op.drop_index('ix_kb_case_studies_is_active', 'kb_case_studies')
    op.drop_column('kb_case_studies', 'deleted_at')
    op.drop_column('kb_case_studies', 'is_active')
    
    # KB Competitors
    op.drop_index('ix_kb_competitors_deleted_at', 'kb_competitors')
    op.drop_index('ix_kb_competitors_is_active', 'kb_competitors')
    op.drop_column('kb_competitors', 'deleted_at')
    op.drop_column('kb_competitors', 'is_active')
    
    # KB Segments
    op.drop_index('ix_kb_segments_deleted_at', 'kb_segments')
    op.drop_index('ix_kb_segments_is_active', 'kb_segments')
    op.drop_column('kb_segments', 'deleted_at')
    
    # KB Products
    op.drop_index('ix_kb_products_deleted_at', 'kb_products')
    op.drop_index('ix_kb_products_is_active', 'kb_products')
    op.drop_column('kb_products', 'deleted_at')
    
    # Folders
    op.drop_index('ix_folders_deleted_at', 'folders')
    op.drop_index('ix_folders_is_active', 'folders')
    op.drop_column('folders', 'deleted_at')
    op.drop_column('folders', 'is_active')
    
    # Datasets
    op.drop_index('ix_datasets_deleted_at', 'datasets')
    op.drop_index('ix_datasets_is_active', 'datasets')
    op.drop_column('datasets', 'is_active')
    
    # Prospects
    op.drop_index('ix_prospects_deleted_at', 'prospects')
    op.drop_index('ix_prospects_is_active', 'prospects')
    op.drop_column('prospects', 'is_active')
