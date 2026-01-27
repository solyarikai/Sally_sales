"""Add integration settings table

Revision ID: 202601231800
Revises: 202601231700
Create Date: 2026-01-23 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202601231800'
down_revision = '202601231700'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integration_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_name', sa.String(100), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('is_connected', sa.Boolean(), default=False),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_name')
    )
    op.create_index(op.f('ix_integration_settings_id'), 'integration_settings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_integration_settings_id'), table_name='integration_settings')
    op.drop_table('integration_settings')
