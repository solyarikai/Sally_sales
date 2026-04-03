"""Add pipeline tables (discovered_companies, extracted_contacts, pipeline_events)

Revision ID: f8a3b2c1d4e5
Revises: 229bf9182978
Create Date: 2026-02-09 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a3b2c1d4e5'
down_revision: Union[str, None] = '229bf9182978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create discovered_companies table
    op.create_table('discovered_companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('search_result_id', sa.Integer(), nullable=True),
        sa.Column('search_job_id', sa.Integer(), nullable=True),
        sa.Column('is_target', sa.Boolean(), nullable=True, default=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('company_info', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('NEW', 'SCRAPED', 'ANALYZED', 'CONTACTS_EXTRACTED', 'ENRICHED', 'EXPORTED', 'REJECTED', name='discoveredcompanystatus'), nullable=False, server_default='NEW'),
        sa.Column('scraped_html', sa.Text(), nullable=True),
        sa.Column('scraped_text', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('contacts_count', sa.Integer(), nullable=True, default=0),
        sa.Column('emails_found', sa.JSON(), nullable=True),
        sa.Column('phones_found', sa.JSON(), nullable=True),
        sa.Column('apollo_people_count', sa.Integer(), nullable=True, default=0),
        sa.Column('apollo_enriched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['search_result_id'], ['search_results.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['search_job_id'], ['search_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discovered_companies_id', 'discovered_companies', ['id'])
    op.create_index('ix_discovered_companies_company_id', 'discovered_companies', ['company_id'])
    op.create_index('ix_discovered_companies_project_id', 'discovered_companies', ['project_id'])
    op.create_index('ix_discovered_companies_domain', 'discovered_companies', ['domain'])
    op.create_index('ix_discovered_company_project_domain', 'discovered_companies', ['company_id', 'project_id', 'domain'], unique=True)
    op.create_index('ix_discovered_company_status', 'discovered_companies', ['company_id', 'status'])
    op.create_index('ix_discovered_company_target', 'discovered_companies', ['company_id', 'project_id', 'is_target'])

    # Create extracted_contacts table
    op.create_table('extracted_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discovered_company_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('job_title', sa.String(length=500), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('source', sa.Enum('WEBSITE_SCRAPE', 'APOLLO', 'MANUAL', name='contactsource'), nullable=False, server_default='WEBSITE_SCRAPE'),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('verification_method', sa.String(length=100), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['discovered_company_id'], ['discovered_companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_extracted_contacts_id', 'extracted_contacts', ['id'])
    op.create_index('ix_extracted_contacts_discovered_company_id', 'extracted_contacts', ['discovered_company_id'])
    op.create_index('ix_extracted_contacts_email', 'extracted_contacts', ['email'])
    op.create_index('ix_extracted_contact_email', 'extracted_contacts', ['discovered_company_id', 'email'])

    # Create pipeline_events table
    op.create_table('pipeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discovered_company_id', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Enum('SEARCH_COMPLETED', 'SCRAPE_COMPLETED', 'ANALYSIS_COMPLETED', 'CONTACT_EXTRACTED', 'APOLLO_ENRICHED', 'EXPORTED_SHEET', 'EXPORTED_CSV', 'STATUS_CHANGED', 'PROMOTED_TO_CRM', 'ERROR', name='pipelineeventtype'), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['discovered_company_id'], ['discovered_companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_events_id', 'pipeline_events', ['id'])
    op.create_index('ix_pipeline_events_discovered_company_id', 'pipeline_events', ['discovered_company_id'])
    op.create_index('ix_pipeline_events_company_id', 'pipeline_events', ['company_id'])
    op.create_index('ix_pipeline_event_company_type', 'pipeline_events', ['company_id', 'event_type'])

    # Add discovered_company_id FK to search_results
    op.add_column('search_results', sa.Column('discovered_company_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_search_results_discovered_company_id',
        'search_results', 'discovered_companies',
        ['discovered_company_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    # Drop FK from search_results
    op.drop_constraint('fk_search_results_discovered_company_id', 'search_results', type_='foreignkey')
    op.drop_column('search_results', 'discovered_company_id')

    # Drop tables in reverse order
    op.drop_table('pipeline_events')
    op.drop_table('extracted_contacts')
    op.drop_table('discovered_companies')

    # Drop enums
    sa.Enum(name='pipelineeventtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='contactsource').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='discoveredcompanystatus').drop(op.get_bind(), checkfirst=True)
