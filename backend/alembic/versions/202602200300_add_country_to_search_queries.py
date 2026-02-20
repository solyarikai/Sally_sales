"""add country column to search_queries with geo backfill

Revision ID: 202602200300
Revises: 202602200200
Create Date: 2026-02-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602200300'
down_revision: Union[str, None] = '202602200200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Geo key → country mapping (derived from query_templates.py SEGMENTS)
GEO_TO_COUNTRY = {
    "dubai": "UAE",
    "dubai_difc": "UAE",
    "abu_dhabi": "UAE",
    "turkey": "Turkey",
    "istanbul": "Turkey",
    "antalya": "Turkey",
    "cyprus": "Cyprus",
    "limassol": "Cyprus",
    "thailand": "Thailand",
    "phuket": "Thailand",
    "bangkok": "Thailand",
    "montenegro": "Montenegro",
    "spain": "Spain",
    "marbella": "Spain",
    "barcelona": "Spain",
    "madrid": "Spain",
    "greece": "Greece",
    "athens": "Greece",
    "crete": "Greece",
    "abroad": "abroad",
    "uk": "UK",
    "london": "UK",
    "israel": "Israel",
    "tel_aviv": "Israel",
    "italy": "Italy",
    "milan": "Italy",
    "rome": "Italy",
    "russia": "Russia",
    "moscow": "Russia",
    "moscow_fo": "Russia",
    "spb": "Russia",
    "sochi": "Russia",
    "switzerland": "Switzerland",
    "zurich": "Switzerland",
    "singapore": "Singapore",
    "estonia": "Estonia",
    "tallinn": "Estonia",
    "georgia": "Georgia",
    "tbilisi": "Georgia",
    "serbia": "Serbia",
    "belgrade": "Serbia",
    "offshore": "offshore",
    "malta": "Malta",
    "portugal": "Portugal",
    "lisbon": "Portugal",
    "caribbean": "Caribbean",
    "bali": "Indonesia",
    "indonesia": "Indonesia",
}


def upgrade() -> None:
    # Add country column
    op.add_column('search_queries', sa.Column('country', sa.String(100), nullable=True))
    op.create_index('ix_search_queries_country', 'search_queries', ['country'])

    # Backfill country from geo mapping
    conn = op.get_bind()
    for geo_key, country in GEO_TO_COUNTRY.items():
        conn.execute(
            sa.text(
                "UPDATE search_queries SET country = :country WHERE geo = :geo AND country IS NULL"
            ),
            {"country": country, "geo": geo_key},
        )


def downgrade() -> None:
    op.drop_index('ix_search_queries_country', table_name='search_queries')
    op.drop_column('search_queries', 'country')
