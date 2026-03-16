"""add igaming tables

Revision ID: 202603150100
Revises: 32a54be7c87a
Create Date: 2026-03-15 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '202603150200'
down_revision: Union[str, None] = '202603150100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Business type enum values
business_type_values = (
    'operator', 'affiliate', 'supplier', 'platform', 'payment',
    'marketing', 'professional_services', 'media', 'regulator', 'other',
)
import_status_values = ('pending', 'processing', 'completed', 'failed')
employee_source_values = ('clay', 'apollo', 'manual', 'import')


def upgrade() -> None:
    # Create enum types
    business_type_enum = postgresql.ENUM(*business_type_values, name='businesstype', create_type=False)
    import_status_enum = postgresql.ENUM(*import_status_values, name='igamingimportstatus', create_type=False)
    employee_source_enum = postgresql.ENUM(*employee_source_values, name='employeesource', create_type=False)

    op.execute("CREATE TYPE businesstype AS ENUM ('operator', 'affiliate', 'supplier', 'platform', 'payment', 'marketing', 'professional_services', 'media', 'regulator', 'other')")
    op.execute("CREATE TYPE igamingimportstatus AS ENUM ('pending', 'processing', 'completed', 'failed')")
    op.execute("CREATE TYPE employeesource AS ENUM ('clay', 'apollo', 'manual', 'import')")

    # ── igaming_companies ──────────────────────────────────────────────
    op.create_table('igaming_companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('name_normalized', sa.String(length=500), nullable=False),
        sa.Column('name_aliases', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('business_type', business_type_enum, nullable=True),
        sa.Column('business_type_raw', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sector', sa.String(length=255), nullable=True),
        sa.Column('regions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('headquarters', sa.String(length=255), nullable=True),
        sa.Column('contacts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('employees_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enrichment_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('clay_enriched_at', sa.DateTime(), nullable=True),
        sa.Column('ai_enriched_at', sa.DateTime(), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_igaming_companies_id'), 'igaming_companies', ['id'], unique=False)
    op.create_index('ix_igaming_companies_name', 'igaming_companies', ['name'], unique=False)
    op.create_index('ix_igaming_companies_name_norm', 'igaming_companies', ['name_normalized'], unique=False)
    op.create_index('ix_igaming_companies_website', 'igaming_companies', ['website'],
                    unique=False, postgresql_where=sa.text('website IS NOT NULL'))
    op.create_index('ix_igaming_companies_type', 'igaming_companies', ['business_type'], unique=False)

    # ── igaming_imports (must be before contacts for FK) ───────────────
    op.create_table('igaming_imports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('source_conference', sa.String(length=255), nullable=True),
        sa.Column('status', import_status_enum, nullable=False, server_default='pending'),
        sa.Column('rows_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_imported', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('companies_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('column_mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_igaming_imports_id'), 'igaming_imports', ['id'], unique=False)

    # ── igaming_contacts ───────────────────────────────────────────────
    op.create_table('igaming_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=100), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('job_title', sa.String(length=500), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('other_contact', sa.String(length=500), nullable=True),
        sa.Column('organization_name', sa.String(length=500), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('business_type_raw', sa.String(length=500), nullable=True),
        sa.Column('business_type', business_type_enum, nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('source_conference', sa.String(length=255), nullable=True),
        sa.Column('source_file', sa.String(length=500), nullable=True),
        sa.Column('import_id', sa.Integer(), nullable=True),
        sa.Column('sector', sa.String(length=500), nullable=True),
        sa.Column('regions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_regions_targeting', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('channel', sa.String(length=255), nullable=True),
        sa.Column('products_services', sa.Text(), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        # SoftDeleteMixin
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        # TimestampMixin
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['igaming_companies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['import_id'], ['igaming_imports.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_igaming_contacts_id'), 'igaming_contacts', ['id'], unique=False)
    op.create_index('ix_igaming_contacts_email', 'igaming_contacts', ['email'],
                    unique=False, postgresql_where=sa.text('email IS NOT NULL'))
    op.create_index('ix_igaming_contacts_org', 'igaming_contacts', ['organization_name'], unique=False)
    op.create_index('ix_igaming_contacts_source', 'igaming_contacts', ['source_conference'], unique=False)
    op.create_index('ix_igaming_contacts_company', 'igaming_contacts', ['company_id'], unique=False)
    op.create_index('ix_igaming_contacts_name', 'igaming_contacts', ['first_name', 'last_name'], unique=False)
    op.create_index('ix_igaming_contacts_import', 'igaming_contacts', ['import_id'], unique=False)
    op.create_index('ix_igaming_contacts_type', 'igaming_contacts', ['business_type'], unique=False)
    op.create_index('ix_igaming_contacts_active', 'igaming_contacts', ['is_active'], unique=False)

    # ── igaming_employees ──────────────────────────────────────────────
    op.create_table('igaming_employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=500), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('job_title', sa.String(length=500), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=100), nullable=True),
        sa.Column('source', employee_source_enum, nullable=False, server_default='manual'),
        sa.Column('search_query', sa.Text(), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['igaming_companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_igaming_employees_id'), 'igaming_employees', ['id'], unique=False)
    op.create_index('ix_igaming_employees_company', 'igaming_employees', ['company_id'], unique=False)
    op.create_index('ix_igaming_employees_email', 'igaming_employees', ['email'],
                    unique=False, postgresql_where=sa.text('email IS NOT NULL'))

    # ── igaming_ai_columns ─────────────────────────────────────────────
    op.create_table('igaming_ai_columns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target', sa.String(length=50), nullable=False, server_default='contact'),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False, server_default='gemini-2.5-flash'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('rows_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='idle'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_igaming_ai_columns_id'), 'igaming_ai_columns', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('igaming_ai_columns')
    op.drop_table('igaming_employees')
    op.drop_table('igaming_contacts')
    op.drop_table('igaming_imports')
    op.drop_table('igaming_companies')
    op.execute("DROP TYPE IF EXISTS businesstype")
    op.execute("DROP TYPE IF EXISTS igamingimportstatus")
    op.execute("DROP TYPE IF EXISTS employeesource")
