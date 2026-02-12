"""Add Apollo org and Clay as domain sources and search engines.

- DomainSource: add 'search_apollo', 'search_clay'
- SearchEngine: add 'apollo_org', 'clay'

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy sends uppercase enum names; PostgreSQL needs both cases
    op.execute("ALTER TYPE domainsource ADD VALUE IF NOT EXISTS 'SEARCH_APOLLO'")
    op.execute("ALTER TYPE domainsource ADD VALUE IF NOT EXISTS 'SEARCH_CLAY'")
    op.execute("ALTER TYPE searchengine ADD VALUE IF NOT EXISTS 'APOLLO_ORG'")
    op.execute("ALTER TYPE searchengine ADD VALUE IF NOT EXISTS 'CLAY'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; manual cleanup needed
    pass
