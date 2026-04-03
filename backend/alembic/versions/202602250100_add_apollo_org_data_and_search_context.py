"""add apollo_org_data to discovered_companies and apollo_search_context to extracted_contacts

Revision ID: 202602250100
Revises: 202602200400
Create Date: 2026-02-25 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602250100'
down_revision: Union[str, None] = '202602251400'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'discovered_companies',
        sa.Column('apollo_org_data', postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        'extracted_contacts',
        sa.Column('apollo_search_context', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('extracted_contacts', 'apollo_search_context')
    op.drop_column('discovered_companies', 'apollo_org_data')
