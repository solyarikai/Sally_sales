"""Add contacts and projects tables for CRM

Revision ID: 202602010100
Revises: 202601310400
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202602010100'
down_revision = '202601310400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create projects table first (contacts has FK to it)
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_industries', sa.Text(), nullable=True),
        sa.Column('target_segments', sa.Text(), nullable=True),
        sa.Column('tam_analysis', sa.Text(), nullable=True),
        sa.Column('gtm_plan', sa.Text(), nullable=True),
        sa.Column('pitch_templates', sa.Text(), nullable=True),
        # Soft delete and timestamps
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Indexes for projects
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_company_id', 'projects', ['company_id'])
    op.create_index('ix_projects_company_name', 'projects', ['company_id', 'name'])
    
    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        # Core contact info
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        # Company info
        sa.Column('company_name', sa.String(500), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('job_title', sa.String(500), nullable=True),
        # Categorization
        sa.Column('segment', sa.String(255), nullable=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        # Source tracking
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('source_id', sa.String(255), nullable=True),
        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='lead'),
        # Additional info
        sa.Column('phone', sa.String(100), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        # Soft delete and timestamps
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Indexes for contacts
    op.create_index('ix_contacts_id', 'contacts', ['id'])
    op.create_index('ix_contacts_company_id', 'contacts', ['company_id'])
    op.create_index('ix_contacts_email', 'contacts', ['email'])
    op.create_index('ix_contacts_domain', 'contacts', ['domain'])
    op.create_index('ix_contacts_segment', 'contacts', ['segment'])
    op.create_index('ix_contacts_source', 'contacts', ['source'])
    op.create_index('ix_contacts_status', 'contacts', ['status'])
    op.create_index('ix_contacts_project_id', 'contacts', ['project_id'])
    op.create_index('ix_contacts_company_email', 'contacts', ['company_id', 'email'])
    op.create_index('ix_contacts_company_status', 'contacts', ['company_id', 'status'])
    op.create_index('ix_contacts_company_segment', 'contacts', ['company_id', 'segment'])
    op.create_index('ix_contacts_company_source', 'contacts', ['company_id', 'source'])
    op.create_index('ix_contacts_company_project', 'contacts', ['company_id', 'project_id'])
    op.create_index('ix_contacts_search', 'contacts', ['first_name', 'last_name', 'company_name'])


def downgrade() -> None:
    # Drop indexes for contacts
    op.drop_index('ix_contacts_search', table_name='contacts')
    op.drop_index('ix_contacts_company_project', table_name='contacts')
    op.drop_index('ix_contacts_company_source', table_name='contacts')
    op.drop_index('ix_contacts_company_segment', table_name='contacts')
    op.drop_index('ix_contacts_company_status', table_name='contacts')
    op.drop_index('ix_contacts_company_email', table_name='contacts')
    op.drop_index('ix_contacts_project_id', table_name='contacts')
    op.drop_index('ix_contacts_status', table_name='contacts')
    op.drop_index('ix_contacts_source', table_name='contacts')
    op.drop_index('ix_contacts_segment', table_name='contacts')
    op.drop_index('ix_contacts_domain', table_name='contacts')
    op.drop_index('ix_contacts_email', table_name='contacts')
    op.drop_index('ix_contacts_company_id', table_name='contacts')
    op.drop_index('ix_contacts_id', table_name='contacts')
    
    # Drop contacts table
    op.drop_table('contacts')
    
    # Drop indexes for projects
    op.drop_index('ix_projects_company_name', table_name='projects')
    op.drop_index('ix_projects_company_id', table_name='projects')
    op.drop_index('ix_projects_id', table_name='projects')
    
    # Drop projects table
    op.drop_table('projects')
