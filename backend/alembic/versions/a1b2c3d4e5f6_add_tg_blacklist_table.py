"""Add tg_blacklist table

Revision ID: a1b2c3d4e5f6
Revises: f8a3b2c1d4e5
Create Date: 2026-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a3b2c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tg_blacklist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('added_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_blacklist_id', 'tg_blacklist', ['id'])
    op.create_index('ix_tg_blacklist_username', 'tg_blacklist', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_tg_blacklist_username', table_name='tg_blacklist')
    op.drop_index('ix_tg_blacklist_id', table_name='tg_blacklist')
    op.drop_table('tg_blacklist')
