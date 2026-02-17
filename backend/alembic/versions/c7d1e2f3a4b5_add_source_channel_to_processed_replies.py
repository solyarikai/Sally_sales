"""Add source and channel columns to processed_replies

Revision ID: c7d1e2f3a4b5
Revises: f8a3b2c1d4e5
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d1e2f3a4b5'
down_revision: Union[str, None] = 'f8a3b2c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('processed_replies', sa.Column('source', sa.String(50), nullable=True))
    op.add_column('processed_replies', sa.Column('channel', sa.String(50), nullable=True))
    op.create_index('ix_processed_replies_source', 'processed_replies', ['source'])
    op.create_index('ix_processed_replies_channel', 'processed_replies', ['channel'])

    # Backfill existing rows as SmartLead email replies
    op.execute("UPDATE processed_replies SET source = 'smartlead', channel = 'email' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_index('ix_processed_replies_channel', table_name='processed_replies')
    op.drop_index('ix_processed_replies_source', table_name='processed_replies')
    op.drop_column('processed_replies', 'channel')
    op.drop_column('processed_replies', 'source')
