"""merge all alembic heads

Revision ID: 290672e1906b
Revises: ca40aae5085e
Create Date: 2026-03-16 22:18:21.111853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '290672e1906b'
down_revision: Union[str, None] = 'ca40aae5085e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
