"""Add AI model, knowledge base, working hours to auto-reply config.

Revision ID: 202604040100
Revises: 202604030200
Create Date: 2026-04-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202604040100'
down_revision: Union[str, None] = '202604030200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_auto_reply_configs', sa.Column('model_provider', sa.String(20), nullable=False, server_default='gemini'))
    op.add_column('tg_auto_reply_configs', sa.Column('knowledge_base', sa.Text(), nullable=True))
    op.add_column('tg_auto_reply_configs', sa.Column('working_hours_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tg_auto_reply_configs', sa.Column('working_hours_start', sa.String(5), nullable=False, server_default='09:00'))
    op.add_column('tg_auto_reply_configs', sa.Column('working_hours_end', sa.String(5), nullable=False, server_default='18:00'))
    op.add_column('tg_auto_reply_configs', sa.Column('working_hours_timezone', sa.String(50), nullable=False, server_default='UTC'))


def downgrade() -> None:
    op.drop_column('tg_auto_reply_configs', 'working_hours_timezone')
    op.drop_column('tg_auto_reply_configs', 'working_hours_end')
    op.drop_column('tg_auto_reply_configs', 'working_hours_start')
    op.drop_column('tg_auto_reply_configs', 'working_hours_enabled')
    op.drop_column('tg_auto_reply_configs', 'knowledge_base')
    op.drop_column('tg_auto_reply_configs', 'model_provider')
