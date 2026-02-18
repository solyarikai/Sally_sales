"""Merge branches + add last_touched_at (stub for existing DB state)

Revision ID: 202602160050
Revises: 202602130200, c7d1e2f3a4b5
Create Date: 2026-02-16 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602160050'
down_revision: Union[str, Sequence[str], None] = ('202602130200', 'c7d1e2f3a4b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: column already exists in production DB
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'processed_replies' AND column_name = 'last_touched_at'"
    ))
    if result.fetchone() is None:
        op.add_column('processed_replies', sa.Column('last_touched_at', sa.DateTime(), nullable=True))
        op.create_index('ix_processed_replies_last_touched_at', 'processed_replies', ['last_touched_at'])


def downgrade() -> None:
    op.drop_index('ix_processed_replies_last_touched_at', table_name='processed_replies')
    op.drop_column('processed_replies', 'last_touched_at')
