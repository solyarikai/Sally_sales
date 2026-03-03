"""Add reference_examples table with pgvector + corrections_snapshot column on learning_logs.

Revision ID: 202603040100
Revises: 202603030300
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

revision = "202603040100"
down_revision = "202603030300"
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create reference_examples table
    op.create_table(
        "reference_examples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_message", sa.Text(), nullable=False),
        sa.Column("operator_reply", sa.Text(), nullable=False),
        sa.Column("lead_context", JSONB(), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("quality_score", sa.Integer(), server_default="3"),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("thread_message_id", sa.Integer(), nullable=True),
        sa.Column("processed_reply_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index("ix_ref_examples_project", "reference_examples", ["project_id"])

    # IVFFlat index for fast vector cosine search
    # Note: IVFFlat requires data to build — if table is empty, index is suboptimal
    # but it self-optimizes as data is inserted. For <1M rows this is fine.
    op.execute(
        "CREATE INDEX ix_ref_examples_embedding ON reference_examples "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # Add corrections_snapshot to learning_logs
    op.add_column("learning_logs", sa.Column("corrections_snapshot", JSONB(), nullable=True))


def downgrade():
    op.drop_column("learning_logs", "corrections_snapshot")
    op.drop_index("ix_ref_examples_embedding", table_name="reference_examples")
    op.drop_index("ix_ref_examples_project", table_name="reference_examples")
    op.drop_table("reference_examples")
    op.execute("DROP EXTENSION IF EXISTS vector")
