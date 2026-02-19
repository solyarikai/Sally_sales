"""Add query dashboard performance indexes

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
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_sq_job_status_segment_geo "
        "ON search_queries (search_job_id, status, segment, geo)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_sq_effectiveness "
        "ON search_queries (search_job_id, effectiveness_score)"
    ))


def downgrade() -> None:
    op.drop_index("ix_sq_effectiveness", table_name="search_queries")
    op.drop_index("ix_sq_job_status_segment_geo", table_name="search_queries")
