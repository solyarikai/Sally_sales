"""add automation monitoring columns

Revision ID: 202602010200
Revises: 202602010100
Create Date: 2026-02-01 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202602010200'
down_revision = '202602010100'
branch_labels = None
depends_on = None


def upgrade():
    # Add monitoring columns to reply_automations
    op.add_column('reply_automations', sa.Column('last_run_at', sa.DateTime(), nullable=True))
    op.add_column('reply_automations', sa.Column('total_processed', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('reply_automations', sa.Column('total_errors', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('reply_automations', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('reply_automations', sa.Column('last_error_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('reply_automations', 'last_error_at')
    op.drop_column('reply_automations', 'last_error')
    op.drop_column('reply_automations', 'total_errors')
    op.drop_column('reply_automations', 'total_processed')
    op.drop_column('reply_automations', 'last_run_at')
