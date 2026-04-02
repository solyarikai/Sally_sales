"""Add tg_warmup_channels table for curated warm-up channel list.

Revision ID: 202604020200
Revises: 202604020100
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "202604020200"
down_revision = "202604020100"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tg_warmup_channels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(255), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tg_warmup_channels_id", "tg_warmup_channels", ["id"])


def downgrade():
    op.drop_index("ix_tg_warmup_channels_id", table_name="tg_warmup_channels")
    op.drop_table("tg_warmup_channels")
