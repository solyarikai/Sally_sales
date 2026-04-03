"""Add AI-extracted interests, tags, and geo_tags columns to reply_analysis.

Revision ID: 202603180100
Revises: 202603162200, 202603171000
Create Date: 2026-03-18 01:00:00

Columns added:
- reply_analysis.interests: Free-text AI summary of lead's needs
- reply_analysis.tags: ARRAY of searchable tags with GIN index
- reply_analysis.geo_tags: ARRAY of geography tags with GIN index
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


revision = "202603180100"
down_revision = "c2d87b5f252e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reply_analysis", sa.Column("interests", sa.Text(), nullable=True))
    op.add_column("reply_analysis", sa.Column("tags", ARRAY(sa.String()), nullable=True))
    op.add_column("reply_analysis", sa.Column("geo_tags", ARRAY(sa.String()), nullable=True))
    op.create_index("ix_reply_analysis_tags", "reply_analysis", ["tags"], postgresql_using="gin")
    op.create_index("ix_reply_analysis_geo_tags", "reply_analysis", ["geo_tags"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_reply_analysis_geo_tags", table_name="reply_analysis")
    op.drop_index("ix_reply_analysis_tags", table_name="reply_analysis")
    op.drop_column("reply_analysis", "geo_tags")
    op.drop_column("reply_analysis", "tags")
    op.drop_column("reply_analysis", "interests")
