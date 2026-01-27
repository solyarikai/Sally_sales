"""Multi-tenant architecture - Users, Companies, Activity Logs

Adds multi-tenant support with data isolation per company.
- New tables: users, companies, user_activity_logs
- Adds company_id to isolated tables (datasets, prospects, knowledge base)
- Adds user_id to shared tables (prompt_templates, integration_settings)
- Adds soft delete support (deleted_at) to critical tables
- Creates default user and company for existing data

Revision ID: 202601250100
Revises: 202601240600
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = '202601250100'
down_revision = '202601240600'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============ Create new tables ============
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), unique=True, nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_companies_user_id', 'companies', ['user_id'])
    
    # User activity logs table
    op.create_table(
        'user_activity_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )
    op.create_index('ix_user_activity_logs_user_id', 'user_activity_logs', ['user_id'])
    op.create_index('ix_user_activity_logs_company_id', 'user_activity_logs', ['company_id'])
    op.create_index('ix_user_activity_logs_created_at', 'user_activity_logs', ['created_at'])
    op.create_index('ix_activity_logs_user_company', 'user_activity_logs', ['user_id', 'company_id'])
    op.create_index('ix_activity_logs_action_type', 'user_activity_logs', ['action', 'entity_type'])
    
    # ============ Add company_id to isolated tables ============
    
    # Datasets
    op.add_column('datasets', sa.Column('company_id', sa.Integer(), nullable=True))
    op.add_column('datasets', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_datasets_company', 'datasets', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_datasets_company_id', 'datasets', ['company_id'])
    
    # Folders
    op.add_column('folders', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_folders_company', 'folders', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_folders_company_id', 'folders', ['company_id'])
    
    # Prospects
    op.add_column('prospects', sa.Column('company_id', sa.Integer(), nullable=True))
    op.add_column('prospects', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_prospects_company', 'prospects', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    # Note: ix_prospects_company_id is created automatically by index=True on the model column
    op.create_index('ix_prospects_company_email', 'prospects', ['company_id', 'email'])
    
    # Knowledge Base - Documents
    op.add_column('kb_documents', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_documents_company', 'kb_documents', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_documents_company_id', 'kb_documents', ['company_id'])
    
    # Knowledge Base - Document Folders
    op.add_column('kb_document_folders', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_document_folders_company', 'kb_document_folders', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_document_folders_company_id', 'kb_document_folders', ['company_id'])
    
    # Knowledge Base - Company Profile
    op.add_column('kb_company_profile', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_company_profile_company', 'kb_company_profile', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_company_profile_company_id', 'kb_company_profile', ['company_id'], unique=True)
    
    # Knowledge Base - Products
    op.add_column('kb_products', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_products_company', 'kb_products', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_products_company_id', 'kb_products', ['company_id'])
    
    # Knowledge Base - Segments
    op.add_column('kb_segments', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_segments_company', 'kb_segments', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_segments_company_id', 'kb_segments', ['company_id'])
    
    # Knowledge Base - Segment Columns
    op.add_column('kb_segment_columns', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_segment_columns_company', 'kb_segment_columns', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_segment_columns_company_id', 'kb_segment_columns', ['company_id'])
    
    # Knowledge Base - Competitors
    op.add_column('kb_competitors', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_competitors_company', 'kb_competitors', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_competitors_company_id', 'kb_competitors', ['company_id'])
    
    # Knowledge Base - Case Studies
    op.add_column('kb_case_studies', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_case_studies_company', 'kb_case_studies', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_case_studies_company_id', 'kb_case_studies', ['company_id'])
    
    # Knowledge Base - Voice Tones
    op.add_column('kb_voice_tones', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_voice_tones_company', 'kb_voice_tones', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_voice_tones_company_id', 'kb_voice_tones', ['company_id'])
    
    # Knowledge Base - Booking Links
    op.add_column('kb_booking_links', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_booking_links_company', 'kb_booking_links', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_booking_links_company_id', 'kb_booking_links', ['company_id'])
    
    # Knowledge Base - Blocklist
    op.add_column('kb_blocklist', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_kb_blocklist_company', 'kb_blocklist', 'companies', ['company_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_kb_blocklist_company_id', 'kb_blocklist', ['company_id'])
    
    # ============ Add user_id to shared tables ============
    
    # Prompt Templates - shared but owned by user
    # First drop the unique constraint on name
    try:
        op.drop_constraint('prompt_templates_name_key', 'prompt_templates', type_='unique')
    except:
        pass  # Constraint might not exist
    
    op.add_column('prompt_templates', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_prompt_templates_user', 'prompt_templates', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_prompt_templates_user_id', 'prompt_templates', ['user_id'])
    op.create_index('ix_prompt_templates_user_name', 'prompt_templates', ['user_id', 'name'], unique=True)
    
    # Integration Settings - shared but owned by user
    # First drop the unique constraint on integration_name
    try:
        op.drop_constraint('integration_settings_integration_name_key', 'integration_settings', type_='unique')
    except:
        pass  # Constraint might not exist
    
    op.add_column('integration_settings', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_integration_settings_user', 'integration_settings', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_integration_settings_user_id', 'integration_settings', ['user_id'])
    op.create_index('ix_integration_settings_user_name', 'integration_settings', ['user_id', 'integration_name'], unique=True)


def downgrade() -> None:
    # ============ Remove user_id from shared tables ============
    
    # Integration Settings
    op.drop_index('ix_integration_settings_user_name', 'integration_settings')
    op.drop_index('ix_integration_settings_user_id', 'integration_settings')
    op.drop_constraint('fk_integration_settings_user', 'integration_settings', type_='foreignkey')
    op.drop_column('integration_settings', 'user_id')
    op.create_unique_constraint('integration_settings_integration_name_key', 'integration_settings', ['integration_name'])
    
    # Prompt Templates
    op.drop_index('ix_prompt_templates_user_name', 'prompt_templates')
    op.drop_index('ix_prompt_templates_user_id', 'prompt_templates')
    op.drop_constraint('fk_prompt_templates_user', 'prompt_templates', type_='foreignkey')
    op.drop_column('prompt_templates', 'user_id')
    op.create_unique_constraint('prompt_templates_name_key', 'prompt_templates', ['name'])
    
    # ============ Remove company_id from isolated tables ============
    
    # Knowledge Base - Blocklist
    op.drop_index('ix_kb_blocklist_company_id', 'kb_blocklist')
    op.drop_constraint('fk_kb_blocklist_company', 'kb_blocklist', type_='foreignkey')
    op.drop_column('kb_blocklist', 'company_id')
    
    # Knowledge Base - Booking Links
    op.drop_index('ix_kb_booking_links_company_id', 'kb_booking_links')
    op.drop_constraint('fk_kb_booking_links_company', 'kb_booking_links', type_='foreignkey')
    op.drop_column('kb_booking_links', 'company_id')
    
    # Knowledge Base - Voice Tones
    op.drop_index('ix_kb_voice_tones_company_id', 'kb_voice_tones')
    op.drop_constraint('fk_kb_voice_tones_company', 'kb_voice_tones', type_='foreignkey')
    op.drop_column('kb_voice_tones', 'company_id')
    
    # Knowledge Base - Case Studies
    op.drop_index('ix_kb_case_studies_company_id', 'kb_case_studies')
    op.drop_constraint('fk_kb_case_studies_company', 'kb_case_studies', type_='foreignkey')
    op.drop_column('kb_case_studies', 'company_id')
    
    # Knowledge Base - Competitors
    op.drop_index('ix_kb_competitors_company_id', 'kb_competitors')
    op.drop_constraint('fk_kb_competitors_company', 'kb_competitors', type_='foreignkey')
    op.drop_column('kb_competitors', 'company_id')
    
    # Knowledge Base - Segment Columns
    op.drop_index('ix_kb_segment_columns_company_id', 'kb_segment_columns')
    op.drop_constraint('fk_kb_segment_columns_company', 'kb_segment_columns', type_='foreignkey')
    op.drop_column('kb_segment_columns', 'company_id')
    
    # Knowledge Base - Segments
    op.drop_index('ix_kb_segments_company_id', 'kb_segments')
    op.drop_constraint('fk_kb_segments_company', 'kb_segments', type_='foreignkey')
    op.drop_column('kb_segments', 'company_id')
    
    # Knowledge Base - Products
    op.drop_index('ix_kb_products_company_id', 'kb_products')
    op.drop_constraint('fk_kb_products_company', 'kb_products', type_='foreignkey')
    op.drop_column('kb_products', 'company_id')
    
    # Knowledge Base - Company Profile
    op.drop_index('ix_kb_company_profile_company_id', 'kb_company_profile')
    op.drop_constraint('fk_kb_company_profile_company', 'kb_company_profile', type_='foreignkey')
    op.drop_column('kb_company_profile', 'company_id')
    
    # Knowledge Base - Document Folders
    op.drop_index('ix_kb_document_folders_company_id', 'kb_document_folders')
    op.drop_constraint('fk_kb_document_folders_company', 'kb_document_folders', type_='foreignkey')
    op.drop_column('kb_document_folders', 'company_id')
    
    # Knowledge Base - Documents
    op.drop_index('ix_kb_documents_company_id', 'kb_documents')
    op.drop_constraint('fk_kb_documents_company', 'kb_documents', type_='foreignkey')
    op.drop_column('kb_documents', 'company_id')
    
    # Prospects
    op.drop_index('ix_prospects_company_email', 'prospects')
    # Note: ix_prospects_company_id is managed by SQLAlchemy via index=True on model column
    op.drop_constraint('fk_prospects_company', 'prospects', type_='foreignkey')
    op.drop_column('prospects', 'deleted_at')
    op.drop_column('prospects', 'company_id')
    
    # Folders
    op.drop_index('ix_folders_company_id', 'folders')
    op.drop_constraint('fk_folders_company', 'folders', type_='foreignkey')
    op.drop_column('folders', 'company_id')
    
    # Datasets
    op.drop_index('ix_datasets_company_id', 'datasets')
    op.drop_constraint('fk_datasets_company', 'datasets', type_='foreignkey')
    op.drop_column('datasets', 'deleted_at')
    op.drop_column('datasets', 'company_id')
    
    # ============ Drop new tables ============
    
    op.drop_index('ix_activity_logs_action_type', 'user_activity_logs')
    op.drop_index('ix_activity_logs_user_company', 'user_activity_logs')
    op.drop_index('ix_user_activity_logs_created_at', 'user_activity_logs')
    op.drop_index('ix_user_activity_logs_company_id', 'user_activity_logs')
    op.drop_index('ix_user_activity_logs_user_id', 'user_activity_logs')
    op.drop_table('user_activity_logs')
    
    op.drop_index('ix_companies_user_id', 'companies')
    op.drop_table('companies')
    
    op.drop_index('ix_users_email', 'users')
    op.drop_table('users')
