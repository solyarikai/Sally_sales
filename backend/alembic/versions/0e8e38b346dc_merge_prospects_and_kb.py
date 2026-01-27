"""merge_prospects_and_kb

Revision ID: 0e8e38b346dc
Revises: 202601232100, 202601240600
Create Date: 2026-01-24 09:57:15.790674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e8e38b346dc'
down_revision: Union[str, None] = ('202601232100', '202601240600')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
