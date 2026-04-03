"""Add CRM settings columns to tg_campaigns.

Revision ID: 202604030200
Revises: 202604030100
Create Date: 2026-04-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '202604030200'
down_revision: Union[str, None] = '202604030100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_campaigns', sa.Column('crm_tag_on_reply', JSONB, nullable=False, server_default='[]'))
    op.add_column('tg_campaigns', sa.Column('crm_status_on_reply', sa.String(50), nullable=True))
    op.add_column('tg_campaigns', sa.Column('crm_owner_on_reply', sa.String(100), nullable=True))
    op.add_column('tg_campaigns', sa.Column('crm_auto_create_contact', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('tg_campaigns', 'crm_auto_create_contact')
    op.drop_column('tg_campaigns', 'crm_owner_on_reply')
    op.drop_column('tg_campaigns', 'crm_status_on_reply')
    op.drop_column('tg_campaigns', 'crm_tag_on_reply')
