"""Add approval workflow fields to processed_replies

Revision ID: 202601310200
Revises: 202601310100
Create Date: 2026-01-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202601310200'
down_revision: Union[str, None] = '202601310100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add approval workflow fields to processed_replies
    op.add_column('processed_replies', sa.Column('approval_status', sa.String(50), nullable=True))
    op.add_column('processed_replies', sa.Column('approved_by', sa.String(100), nullable=True))
    op.add_column('processed_replies', sa.Column('approved_at', sa.DateTime(), nullable=True))
    
    # Create index for approval_status
    op.create_index('ix_processed_replies_approval_status', 'processed_replies', ['approval_status'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_processed_replies_approval_status', table_name='processed_replies')
    
    # Drop columns
    op.drop_column('processed_replies', 'approved_at')
    op.drop_column('processed_replies', 'approved_by')
    op.drop_column('processed_replies', 'approval_status')
