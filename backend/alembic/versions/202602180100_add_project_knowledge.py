"""add project_knowledge table

Revision ID: 202602180100
Revises: 202602170100
Create Date: 2026-02-18 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602180100'
down_revision: Union[str, None] = '202602170100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_knowledge',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('value', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('source', sa.String(50), server_default='manual'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_project_knowledge_project_cat',
        'project_knowledge',
        ['project_id', 'category'],
        unique=False,
    )
    op.create_index(
        'uq_project_knowledge_project_cat_key',
        'project_knowledge',
        ['project_id', 'category', 'key'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_project_knowledge_project_cat_key', table_name='project_knowledge')
    op.drop_index('ix_project_knowledge_project_cat', table_name='project_knowledge')
    op.drop_table('project_knowledge')
