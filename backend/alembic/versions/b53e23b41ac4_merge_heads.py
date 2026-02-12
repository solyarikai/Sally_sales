"""merge heads

Revision ID: b53e23b41ac4
Revises: 202602111000, 202602121600
Create Date: 2026-02-13 00:33:22.956088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b53e23b41ac4'
down_revision: Union[str, None] = ('202602111000', '202602121600')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
