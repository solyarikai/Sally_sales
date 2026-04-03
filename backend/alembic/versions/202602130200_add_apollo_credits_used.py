"""add apollo_credits_used to discovered_companies

Revision ID: 202602130200
Revises: b53e23b41ac4
Create Date: 2026-02-13 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602130200'
down_revision: Union[str, None] = 'b53e23b41ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: check if column exists before adding
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'discovered_companies' AND column_name = 'apollo_credits_used'"
    ))
    if result.fetchone() is None:
        op.add_column('discovered_companies', sa.Column('apollo_credits_used', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    op.drop_column('discovered_companies', 'apollo_credits_used')
