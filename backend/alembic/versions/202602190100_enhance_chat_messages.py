"""enhance chat messages with action metadata

Revision ID: 202602190100
Revises: 202602180300
Create Date: 2026-02-19 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602190100'
down_revision: Union[str, None] = '202602180300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project_chat_messages', sa.Column('action_type', sa.String(50), nullable=True))
    op.add_column('project_chat_messages', sa.Column('action_data', postgresql.JSONB(), nullable=True))
    op.add_column('project_chat_messages', sa.Column('suggestions', postgresql.JSONB(), nullable=True))
    op.add_column('project_chat_messages', sa.Column('feedback', sa.String(10), nullable=True))
    op.add_column('project_chat_messages', sa.Column('tokens_used', sa.Integer(), nullable=True))
    op.add_column('project_chat_messages', sa.Column('duration_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('project_chat_messages', 'duration_ms')
    op.drop_column('project_chat_messages', 'tokens_used')
    op.drop_column('project_chat_messages', 'feedback')
    op.drop_column('project_chat_messages', 'suggestions')
    op.drop_column('project_chat_messages', 'action_data')
    op.drop_column('project_chat_messages', 'action_type')
