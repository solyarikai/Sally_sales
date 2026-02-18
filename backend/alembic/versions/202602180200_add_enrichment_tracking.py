"""add enrichment_attempts and enrichment_effectiveness tables

Revision ID: 202602180200
Revises: 202602180100
Create Date: 2026-02-18 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602180200'
down_revision: Union[str, None] = '202602180100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Expand ContactSource enum with new values --
    # Alembic enums in this project use UPPERCASE values
    op.execute("ALTER TYPE contactsource ADD VALUE IF NOT EXISTS 'SUBPAGE_SCRAPE'")
    op.execute("ALTER TYPE contactsource ADD VALUE IF NOT EXISTS 'APOLLO_ORG'")
    op.execute("ALTER TYPE contactsource ADD VALUE IF NOT EXISTS 'LINKEDIN'")
    op.execute("ALTER TYPE contactsource ADD VALUE IF NOT EXISTS 'CLAY'")

    # -- enrichment_attempts table --
    op.create_table(
        'enrichment_attempts',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('discovered_company_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('method', sa.String(100), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('credits_used', sa.Integer(), server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 4), server_default='0'),
        sa.Column('contacts_found', sa.Integer(), server_default='0'),
        sa.Column('emails_found', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='SUCCESS'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(), nullable=True),
        sa.Column('result_summary', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['discovered_company_id'], ['discovered_companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enrichment_attempts_dc_id', 'enrichment_attempts', ['discovered_company_id'])
    op.create_index('ix_enrichment_attempts_source', 'enrichment_attempts', ['source_type', 'status'])
    op.create_index('ix_enrichment_attempts_attempted_at', 'enrichment_attempts', ['attempted_at'])

    # -- enrichment_effectiveness table --
    op.create_table(
        'enrichment_effectiveness',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('segment', sa.String(255), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('total_attempts', sa.Integer(), server_default='0'),
        sa.Column('successful_attempts', sa.Integer(), server_default='0'),
        sa.Column('total_contacts_found', sa.Integer(), server_default='0'),
        sa.Column('total_credits_used', sa.Integer(), server_default='0'),
        sa.Column('success_rate', sa.Numeric(5, 4), server_default='0'),
        sa.Column('cost_per_contact', sa.Numeric(10, 4), server_default='0'),
        sa.Column('priority_rank', sa.Integer(), server_default='99'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_enrichment_effectiveness_project_seg_source',
        'enrichment_effectiveness',
        ['project_id', 'segment', 'source_type'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_enrichment_effectiveness_project_seg_source', table_name='enrichment_effectiveness')
    op.drop_table('enrichment_effectiveness')
    op.drop_index('ix_enrichment_attempts_attempted_at', table_name='enrichment_attempts')
    op.drop_index('ix_enrichment_attempts_source', table_name='enrichment_attempts')
    op.drop_index('ix_enrichment_attempts_dc_id', table_name='enrichment_attempts')
    op.drop_table('enrichment_attempts')
    # Note: Cannot remove enum values in PostgreSQL, skip in downgrade
