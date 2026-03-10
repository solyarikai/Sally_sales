"""merge_heads

Revision ID: e49f81b62f90
Revises: a1b2c3d4e5f7, 202603100200
Create Date: 2026-03-10 18:08:57.727792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e49f81b62f90'
down_revision: Union[str, None] = ('a1b2c3d4e5f7', '202603100200')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
