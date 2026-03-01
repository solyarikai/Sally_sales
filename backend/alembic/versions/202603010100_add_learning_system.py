"""Add learning system — learning_logs, operator_corrections tables + template tracking columns.

Revision ID: 202603010100
Revises: 202602250100
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202603010100"
down_revision = "202602250100"
branch_labels = None
depends_on = None


def upgrade():
    # --- learning_logs ---
    op.create_table(
        "learning_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("conversations_analyzed", sa.Integer(), nullable=True),
        sa.Column("conversations_email", sa.Integer(), nullable=True),
        sa.Column("conversations_linkedin", sa.Integer(), nullable=True),
        sa.Column("qualified_count", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(50), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("reply_prompt_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_logs_project_trigger", "learning_logs", ["project_id", "trigger"])
    op.create_index("ix_learning_logs_project_created", "learning_logs", ["project_id", "created_at"])

    # --- operator_corrections ---
    op.create_table(
        "operator_corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("processed_reply_id", sa.Integer(), sa.ForeignKey("processed_replies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_draft_reply", sa.Text(), nullable=True),
        sa.Column("ai_draft_subject", sa.String(500), nullable=True),
        sa.Column("sent_reply", sa.Text(), nullable=True),
        sa.Column("sent_subject", sa.String(500), nullable=True),
        sa.Column("was_edited", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reply_category", sa.String(50), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("lead_company", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_operator_corrections_project_created", "operator_corrections", ["project_id", "created_at"])

    # --- reply_prompt_templates: add tracking columns ---
    op.add_column("reply_prompt_templates", sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("reply_prompt_templates", sa.Column("last_used_at", sa.DateTime(), nullable=True))
    op.add_column("reply_prompt_templates", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("reply_prompt_templates", "version")
    op.drop_column("reply_prompt_templates", "last_used_at")
    op.drop_column("reply_prompt_templates", "usage_count")
    op.drop_index("ix_operator_corrections_project_created", "operator_corrections")
    op.drop_table("operator_corrections")
    op.drop_index("ix_learning_logs_project_created", "learning_logs")
    op.drop_index("ix_learning_logs_project_trigger", "learning_logs")
    op.drop_table("learning_logs")
