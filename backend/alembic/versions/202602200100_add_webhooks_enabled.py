"""add webhooks_enabled to projects

Revision ID: 202602200100
Revises: 202602190200
Create Date: 2026-02-20 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602200100'
down_revision: Union[str, None] = '202602190200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('webhooks_enabled', sa.Boolean(), nullable=False, server_default='true'))
    # Disable webhooks for Rizzult (project_id=22)
    op.execute("UPDATE projects SET webhooks_enabled = false WHERE id = 22")


def downgrade() -> None:
    op.drop_column('projects', 'webhooks_enabled')
