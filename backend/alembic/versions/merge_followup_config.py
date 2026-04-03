"""merge follow_up_config with existing heads

Revision ID: merge_followup_config
Revises: e49f81b62f90, 202603100300
Create Date: 2026-03-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'merge_followup_config'
down_revision: Union[str, None] = ('e49f81b62f90', '202603100300')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
