"""add_campaigns_to_contacts

Revision ID: a6b9d701ba6d
Revises: 2fb87aa98654
Create Date: 2026-02-03 01:22:08.457726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a6b9d701ba6d'
down_revision: Union[str, None] = '2fb87aa98654'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add campaigns JSON column to contacts
    op.add_column('contacts', sa.Column('campaigns', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'campaigns')
