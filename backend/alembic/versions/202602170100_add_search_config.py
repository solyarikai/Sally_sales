"""add search_config to project_search_knowledge

Revision ID: 202602170100
Revises: 202602160100
Create Date: 2026-02-17 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602170100'
down_revision: Union[str, None] = '202602160100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'project_search_knowledge',
        sa.Column('search_config', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('project_search_knowledge', 'search_config')
