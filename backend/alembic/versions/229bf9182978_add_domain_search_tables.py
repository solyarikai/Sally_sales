"""Add domain search tables

Revision ID: 229bf9182978
Revises: a6b9d701ba6d
Create Date: 2026-02-09 15:52:46.394009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '229bf9182978'
down_revision: Union[str, None] = 'a6b9d701ba6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('domains',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain', sa.String(length=255), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'TRASH', name='domainstatus'), nullable=False),
    sa.Column('source', sa.Enum('SEARCH_GOOGLE', 'SEARCH_YANDEX', 'MANUAL', 'IMPORT', name='domainsource'), nullable=False),
    sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('times_seen', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domains_domain'), 'domains', ['domain'], unique=True)
    op.create_index(op.f('ix_domains_id'), 'domains', ['id'], unique=False)
    op.create_index(op.f('ix_domains_status'), 'domains', ['status'], unique=False)
    op.create_index('ix_domains_status_domain', 'domains', ['status', 'domain'], unique=False)

    op.create_table('search_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='searchjobstatus'), nullable=False),
    sa.Column('search_engine', sa.Enum('GOOGLE_SERP', 'YANDEX_API', name='searchengine'), nullable=False),
    sa.Column('queries_total', sa.Integer(), nullable=True),
    sa.Column('queries_completed', sa.Integer(), nullable=True),
    sa.Column('domains_found', sa.Integer(), nullable=True),
    sa.Column('domains_new', sa.Integer(), nullable=True),
    sa.Column('domains_trash', sa.Integer(), nullable=True),
    sa.Column('domains_duplicate', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_jobs_company_id'), 'search_jobs', ['company_id'], unique=False)
    op.create_index(op.f('ix_search_jobs_id'), 'search_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_search_jobs_project_id'), 'search_jobs', ['project_id'], unique=False)
    op.create_index(op.f('ix_search_jobs_status'), 'search_jobs', ['status'], unique=False)

    op.create_table('search_queries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('search_job_id', sa.Integer(), nullable=False),
    sa.Column('query_text', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'DONE', 'FAILED', name='searchquerystatus'), nullable=False),
    sa.Column('domains_found', sa.Integer(), nullable=True),
    sa.Column('pages_scraped', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['search_job_id'], ['search_jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_queries_id'), 'search_queries', ['id'], unique=False)
    op.create_index(op.f('ix_search_queries_search_job_id'), 'search_queries', ['search_job_id'], unique=False)

    op.create_table('search_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('search_job_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('domain', sa.String(length=255), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('is_target', sa.Boolean(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('reasoning', sa.Text(), nullable=True),
    sa.Column('company_info', sa.JSON(), nullable=True),
    sa.Column('html_snippet', sa.Text(), nullable=True),
    sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['search_job_id'], ['search_jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_results_domain'), 'search_results', ['domain'], unique=False)
    op.create_index(op.f('ix_search_results_id'), 'search_results', ['id'], unique=False)
    op.create_index('ix_search_results_job_domain', 'search_results', ['search_job_id', 'domain'], unique=False)
    op.create_index(op.f('ix_search_results_project_id'), 'search_results', ['project_id'], unique=False)
    op.create_index('ix_search_results_project_target', 'search_results', ['project_id', 'is_target'], unique=False)
    op.create_index(op.f('ix_search_results_search_job_id'), 'search_results', ['search_job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_search_results_search_job_id'), table_name='search_results')
    op.drop_index('ix_search_results_project_target', table_name='search_results')
    op.drop_index(op.f('ix_search_results_project_id'), table_name='search_results')
    op.drop_index('ix_search_results_job_domain', table_name='search_results')
    op.drop_index(op.f('ix_search_results_id'), table_name='search_results')
    op.drop_index(op.f('ix_search_results_domain'), table_name='search_results')
    op.drop_table('search_results')

    op.drop_index(op.f('ix_search_queries_search_job_id'), table_name='search_queries')
    op.drop_index(op.f('ix_search_queries_id'), table_name='search_queries')
    op.drop_table('search_queries')

    op.drop_index(op.f('ix_search_jobs_status'), table_name='search_jobs')
    op.drop_index(op.f('ix_search_jobs_project_id'), table_name='search_jobs')
    op.drop_index(op.f('ix_search_jobs_id'), table_name='search_jobs')
    op.drop_index(op.f('ix_search_jobs_company_id'), table_name='search_jobs')
    op.drop_table('search_jobs')

    op.drop_index('ix_domains_status_domain', table_name='domains')
    op.drop_index(op.f('ix_domains_status'), table_name='domains')
    op.drop_index(op.f('ix_domains_id'), table_name='domains')
    op.drop_index(op.f('ix_domains_domain'), table_name='domains')
    op.drop_table('domains')

    sa.Enum('ACTIVE', 'TRASH', name='domainstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum('SEARCH_GOOGLE', 'SEARCH_YANDEX', 'MANUAL', 'IMPORT', name='domainsource').drop(op.get_bind(), checkfirst=True)
    sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='searchjobstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum('GOOGLE_SERP', 'YANDEX_API', name='searchengine').drop(op.get_bind(), checkfirst=True)
    sa.Enum('PENDING', 'DONE', 'FAILED', name='searchquerystatus').drop(op.get_bind(), checkfirst=True)
