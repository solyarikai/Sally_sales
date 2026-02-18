"""add email_verifications table, DC.matched_segment, Contact verification fields

Revision ID: 202602180300
Revises: 202602180200
Create Date: 2026-02-18 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602180300'
down_revision: Union[str, None] = '202602180200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- email_verifications table ---
    op.create_table(
        'email_verifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('service', sa.String(50), nullable=False),
        sa.Column('result', sa.String(30), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.Column('provider', sa.String(100), nullable=True),
        sa.Column('raw_response', postgresql.JSONB(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=True),
        sa.Column('credits_used', sa.Integer(), server_default='1'),
        sa.Column('verified_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('extracted_contact_id', sa.Integer(), sa.ForeignKey('extracted_contacts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_email_verifications_email_verified', 'email_verifications', ['email', sa.text('verified_at DESC')])
    op.create_index('ix_email_verifications_company_project', 'email_verifications', ['company_id', 'project_id'])

    # --- DiscoveredCompany.matched_segment ---
    op.add_column('discovered_companies', sa.Column('matched_segment', sa.String(100), nullable=True))
    op.create_index('ix_discovered_companies_segment', 'discovered_companies', ['company_id', 'project_id', 'matched_segment'])

    # --- Contact verification fields ---
    op.add_column('contacts', sa.Column('is_email_verified', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('contacts', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contacts', sa.Column('email_verification_result', sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'email_verification_result')
    op.drop_column('contacts', 'email_verified_at')
    op.drop_column('contacts', 'is_email_verified')
    op.drop_index('ix_discovered_companies_segment', table_name='discovered_companies')
    op.drop_column('discovered_companies', 'matched_segment')
    op.drop_index('ix_email_verifications_company_project', table_name='email_verifications')
    op.drop_index('ix_email_verifications_email_verified', table_name='email_verifications')
    op.drop_table('email_verifications')
