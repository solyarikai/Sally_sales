"""merge alembic heads

Revision ID: 4dcaf98f10ef
Revises: 202603162000
Create Date: 2026-03-16 22:14:09.383186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dcaf98f10ef'
down_revision: Union[str, None] = '202603162000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
