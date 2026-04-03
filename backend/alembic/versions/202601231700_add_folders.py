"""add folders

Revision ID: 202601231700
Revises: 202601231600
Create Date: 2026-01-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202601231700'
down_revision: Union[str, None] = '202601231600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create folders table
    op.create_table(
        'folders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_folders_id', 'folders', ['id'])
    
    # Add folder_id to datasets
    op.add_column('datasets', sa.Column('folder_id', sa.Integer(), sa.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('datasets', 'folder_id')
    op.drop_index('ix_folders_id', 'folders')
    op.drop_table('folders')
