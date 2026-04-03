"""Create Campaign Intelligence (GOD_SEQUENCE) tables.

New tables: campaign_snapshots, campaign_patterns,
campaign_intelligence_runs, generated_sequences.

Revision ID: i1_campaign_intelligence
Revises: h1_gathering_system
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "i1_campaign_intelligence"
down_revision = "h1_gathering_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # campaign_intelligence_runs — must be created first (referenced by campaign_patterns)
    op.create_table(
        "campaign_intelligence_runs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("market_filter", sa.String(50), nullable=True),
        sa.Column("min_sample_size", sa.Integer, nullable=True),
        sa.Column("campaigns_analyzed", sa.Integer, nullable=True),
        sa.Column("top_campaigns_count", sa.Integer, nullable=True),
        sa.Column("snapshots_used", JSONB, nullable=True),
        sa.Column("patterns_created", sa.Integer, server_default="0"),
        sa.Column("patterns_updated", sa.Integer, server_default="0"),
        sa.Column("patterns_total", sa.Integer, server_default="0"),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cir_company_status", "campaign_intelligence_runs", ["company_id", "status"])

    # campaign_snapshots
    op.create_table(
        "campaign_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leads_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_replies", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warm_replies", sa.Integer, nullable=False, server_default="0"),
        sa.Column("meetings_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("questions_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_interested_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ooo_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wrong_person_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warm_reply_rate", sa.Float, nullable=True),
        sa.Column("meeting_rate", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("campaign_name", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("market", sa.String(50), nullable=True),
        sa.Column("sequence_steps", JSONB, nullable=True),
        sa.Column("sequence_step_count", sa.Integer, nullable=True),
        sa.Column("sequence_total_days", sa.Integer, nullable=True),
        sa.Column("approve_rate", sa.Float, nullable=True),
        sa.Column("edit_rate", sa.Float, nullable=True),
        sa.Column("snapshot_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_latest", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("min_sample_size_met", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("snapshotted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cs_campaign_latest", "campaign_snapshots", ["campaign_id", "is_latest"])
    op.create_index("ix_cs_project_score", "campaign_snapshots", ["project_id", "quality_score"])
    op.create_index("ix_cs_market_score", "campaign_snapshots", ["market", "quality_score"])
    op.create_index("ix_cs_company", "campaign_snapshots", ["company_id"])

    # campaign_patterns
    op.create_table(
        "campaign_patterns",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_level", sa.String(20), nullable=False, server_default="universal"),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("business_key", sa.String(255), nullable=True),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("pattern_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("market", sa.String(50), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("segment", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("evidence_campaign_ids", JSONB, nullable=True),
        sa.Column("evidence_summary", sa.Text, nullable=True),
        sa.Column("sample_size", sa.Integer, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.Integer, sa.ForeignKey("campaign_patterns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("extraction_run_id", sa.Integer, sa.ForeignKey("campaign_intelligence_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cp_type_market", "campaign_patterns", ["pattern_type", "market", "is_active"])
    op.create_index("ix_cp_company", "campaign_patterns", ["company_id", "is_active"])

    # generated_sequences
    op.create_table(
        "generated_sequences",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_prompt", sa.Text, nullable=True),
        sa.Column("patterns_used", JSONB, nullable=True),
        sa.Column("project_knowledge_snapshot", JSONB, nullable=True),
        sa.Column("campaign_name", sa.String(500), nullable=True),
        sa.Column("sequence_steps", JSONB, nullable=False),
        sa.Column("sequence_step_count", sa.Integer, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_notes", sa.Text, nullable=True),
        sa.Column("pushed_campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gs_project_status", "generated_sequences", ["project_id", "status"])
    op.create_index("ix_gs_company", "generated_sequences", ["company_id"])


def downgrade() -> None:
    op.drop_table("generated_sequences")
    op.drop_table("campaign_patterns")
    op.drop_table("campaign_snapshots")
    op.drop_table("campaign_intelligence_runs")
