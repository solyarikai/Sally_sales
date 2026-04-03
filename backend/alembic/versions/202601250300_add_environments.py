"""Add environments table and link to companies

Environments group companies for workspace isolation.
Useful for showing only relevant companies to specific clients.

Revision ID: 202601250300
Revises: 202601250200
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = '202601250300'
down_revision = '202601250200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create environments table
    op.create_table(
        'environments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_environments_user_id', 'environments', ['user_id'])
    
    # Add environment_id to companies
    op.add_column('companies', sa.Column('environment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_companies_environment',
        'companies',
        'environments',
        ['environment_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_companies_environment_id', 'companies', ['environment_id'])


def downgrade() -> None:
    # Remove environment_id from companies
    op.drop_index('ix_companies_environment_id', 'companies')
    op.drop_constraint('fk_companies_environment', 'companies', type_='foreignkey')
    op.drop_column('companies', 'environment_id')
    
    # Drop environments table
    op.drop_index('ix_environments_user_id', 'environments')
    op.drop_table('environments')
