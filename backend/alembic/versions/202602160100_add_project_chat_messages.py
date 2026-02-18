"""add project_chat_messages table

Revision ID: 202602160100
Revises: d8e2f3a4b5c6
Create Date: 2026-02-16 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602160100'
down_revision: Union[str, None] = 'd8e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('client_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_project_chat_messages_project_created', 'project_chat_messages', ['project_id', 'created_at'])
    op.create_index('ix_project_chat_messages_project_client', 'project_chat_messages', ['project_id', 'client_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_project_chat_messages_project_client', table_name='project_chat_messages')
    op.drop_index('ix_project_chat_messages_project_created', table_name='project_chat_messages')
    op.drop_table('project_chat_messages')
