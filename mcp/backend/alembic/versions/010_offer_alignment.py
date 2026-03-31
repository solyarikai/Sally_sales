"""Add offer_summary and offer_approved to projects.

Revision ID: 010_offer_alignment
Revises: 009_kpi_progress
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "010_offer_alignment"
down_revision = "009_pipeline_kpi_progress"


def upgrade():
    op.add_column("projects", sa.Column("offer_summary", JSONB, nullable=True))
    op.add_column("projects", sa.Column("offer_approved", sa.Boolean(), server_default="false"))


def downgrade():
    op.drop_column("projects", "offer_approved")
    op.drop_column("projects", "offer_summary")
