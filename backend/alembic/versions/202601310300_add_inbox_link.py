"""Add inbox_link field to processed_replies for Smartlead direct access

Revision ID: 202601310300
Revises: 202601310200
Create Date: 2026-01-31 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202601310300'
down_revision: Union[str, None] = '202601310200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add inbox_link field to store Smartlead ui_master_inbox_link
    op.add_column('processed_replies', sa.Column('inbox_link', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('processed_replies', 'inbox_link')
