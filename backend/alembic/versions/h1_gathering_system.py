"""Create TAM gathering system tables and extend existing models.

New tables: gathering_runs, company_source_links, company_scrapes,
analysis_runs, analysis_results, approval_gates.

New columns on discovered_companies: source_count, first_found_by,
blacklist cache, latest analysis reference, linkedin_company_url.

New column on search_jobs: gathering_run_id.

Materialized view: active_campaign_domains for instant CRM blacklist lookup.

Revision ID: h1_gathering_system
Revises: g1_channel_agnostic
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "h1_gathering_system"
down_revision = "g1_channel_agnostic"
branch_labels = None
depends_on = None


def upgrade():
    # ── gathering_runs ──
    op.create_table(
        "gathering_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("source_label", sa.String(255), nullable=True),
        sa.Column("source_subtype", sa.String(100), nullable=True),
        sa.Column("filters", JSONB, nullable=False),
        sa.Column("filter_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("current_phase", sa.String(30), nullable=False, server_default="gather"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("raw_results_count", sa.Integer(), server_default="0"),
        sa.Column("new_companies_count", sa.Integer(), server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), server_default="0"),
        sa.Column("rejected_count", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("credits_used", sa.Integer(), server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(10, 4), server_default="0"),
        sa.Column("target_rate", sa.Float(), nullable=True),
        sa.Column("avg_analysis_confidence", sa.Float(), nullable=True),
        sa.Column("cost_per_target_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("enrichment_hit_rate", sa.Float(), nullable=True),
        sa.Column("segment_id", sa.Integer(), sa.ForeignKey("kb_segments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_run_id", sa.Integer(), sa.ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=True),
        sa.Column("input_mode", sa.String(30), server_default="structured"),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_output_ref", sa.Text(), nullable=True),
        sa.Column("raw_output_sample", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_gr_project_source", "gathering_runs", ["project_id", "source_type", "status"])
    op.create_index("ix_gr_filter_hash", "gathering_runs", ["project_id", "filter_hash"])
    op.create_index("ix_gr_pipeline", "gathering_runs", ["pipeline_run_id"])
    op.create_index("ix_gr_created", "gathering_runs", ["project_id", "created_at"])

    # ── company_source_links ──
    op.create_table(
        "company_source_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("discovered_company_id", sa.Integer(), sa.ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gathering_run_id", sa.Integer(), sa.ForeignKey("gathering_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_rank", sa.Integer(), nullable=True),
        sa.Column("source_data", JSONB, nullable=True),
        sa.Column("source_confidence", sa.Float(), nullable=True),
        sa.Column("found_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_csl_discovered_company", "company_source_links", ["discovered_company_id"])
    op.create_index("ix_csl_gathering_run", "company_source_links", ["gathering_run_id"])
    op.create_index("uq_csl_company_run", "company_source_links", ["discovered_company_id", "gathering_run_id"], unique=True)

    # ── company_scrapes ──
    op.create_table(
        "company_scrapes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("discovered_company_id", sa.Integer(), sa.ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("page_path", sa.String(255), server_default="/"),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("page_metadata", JSONB, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ttl_days", sa.Integer(), server_default="180"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("scrape_method", sa.String(50), server_default="httpx"),
        sa.Column("scrape_status", sa.String(30), server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("html_size_bytes", sa.Integer(), nullable=True),
        sa.Column("text_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cs_company_path_current", "company_scrapes", ["discovered_company_id", "page_path", "is_current"])
    op.create_index("ix_cs_status", "company_scrapes", ["scrape_status"])
    op.execute("CREATE INDEX ix_cs_current ON company_scrapes(discovered_company_id) WHERE is_current = true")
    op.execute("CREATE INDEX ix_cs_expires ON company_scrapes(expires_at) WHERE is_current = true")

    # ── gathering_prompts (before analysis_runs — FK target) ──
    op.create_table(
        "gathering_prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("category", sa.String(50), server_default="icp_analysis"),
        sa.Column("model_default", sa.String(100), server_default="gpt-4o-mini"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("parent_prompt_id", sa.Integer(), sa.ForeignKey("gathering_prompts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0"),
        sa.Column("avg_target_rate", sa.Float(), nullable=True),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("total_companies_analyzed", sa.Integer(), server_default="0"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_gp_company_project", "gathering_prompts", ["company_id", "project_id"])
    op.create_index("ix_gp_category", "gathering_prompts", ["company_id", "category"])

    # ── analysis_runs ──
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("gathering_prompts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("scope_type", sa.String(50), server_default="batch"),
        sa.Column("scope_filter", JSONB, nullable=True),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_analyzed", sa.Integer(), server_default="0"),
        sa.Column("targets_found", sa.Integer(), server_default="0"),
        sa.Column("rejected_count", sa.Integer(), server_default="0"),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 4), server_default="0"),
        sa.Column("total_tokens", sa.Integer(), server_default="0"),
        sa.Column("triggered_by", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ar_project_status", "analysis_runs", ["project_id", "status"])
    op.create_index("ix_ar_project_model", "analysis_runs", ["project_id", "model"])
    op.create_index("ix_ar_project_prompt", "analysis_runs", ["project_id", "prompt_hash"])

    # ── analysis_results ──
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discovered_company_id", sa.Integer(), sa.ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_target", sa.Boolean(), server_default="false"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("segment", sa.String(100), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("scores", JSONB, nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("override_verdict", sa.Boolean(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("uq_ar_run_company", "analysis_results", ["analysis_run_id", "discovered_company_id"], unique=True)
    op.create_index("ix_ar_company", "analysis_results", ["discovered_company_id"])
    op.create_index("ix_ar_run_target", "analysis_results", ["analysis_run_id", "is_target"])

    # ── approval_gates ──
    op.create_table(
        "approval_gates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gathering_run_id", sa.Integer(), sa.ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gate_type", sa.String(50), nullable=False),
        sa.Column("gate_label", sa.String(255), nullable=False),
        sa.Column("scope", JSONB, nullable=False),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("decided_by", sa.String(100), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ag_project_status", "approval_gates", ["project_id", "status"])
    op.execute("CREATE INDEX ix_ag_pending ON approval_gates(status) WHERE status = 'pending'")

    # ── Extend discovered_companies ──
    op.add_column("discovered_companies", sa.Column("source_count", sa.Integer(), server_default="1"))
    op.add_column("discovered_companies", sa.Column("first_found_by", sa.Integer(), nullable=True))
    op.add_column("discovered_companies", sa.Column("blacklist_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("discovered_companies", sa.Column("in_active_campaign", sa.Boolean(), server_default="false"))
    op.add_column("discovered_companies", sa.Column("campaign_ids_active", JSONB, nullable=True))
    op.add_column("discovered_companies", sa.Column("crm_contact_id", sa.Integer(), nullable=True))
    op.add_column("discovered_companies", sa.Column("latest_analysis_run_id", sa.Integer(), nullable=True))
    op.add_column("discovered_companies", sa.Column("latest_analysis_verdict", sa.Boolean(), nullable=True))
    op.add_column("discovered_companies", sa.Column("latest_analysis_segment", sa.String(100), nullable=True))
    op.add_column("discovered_companies", sa.Column("linkedin_company_url", sa.String(500), nullable=True))

    # FKs for new discovered_companies columns
    op.create_foreign_key(
        "fk_dc_first_found_by", "discovered_companies", "gathering_runs",
        ["first_found_by"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_dc_crm_contact", "discovered_companies", "contacts",
        ["crm_contact_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_dc_latest_analysis", "discovered_companies", "analysis_runs",
        ["latest_analysis_run_id"], ["id"], ondelete="SET NULL",
    )

    # ── Extend search_jobs ──
    op.add_column("search_jobs", sa.Column("gathering_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_sj_gathering_run", "search_jobs", "gathering_runs",
        ["gathering_run_id"], ["id"], ondelete="SET NULL",
    )

    # ── Materialized view: active_campaign_domains (PROJECT-SCOPED) ──
    # Includes project_id so blacklist checks can filter by project.
    # Query with: WHERE domain = ANY(:domains) AND project_id = :pid
    # for same-project checks, or without project_id for cross-project.
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS active_campaign_domains AS
        SELECT DISTINCT
            lower(c.domain) AS domain,
            c.project_id,
            p.name AS project_name,
            array_agg(DISTINCT camp.id) AS campaign_ids,
            array_agg(DISTINCT camp.name) AS campaign_names,
            count(DISTINCT c.id) AS contact_count
        FROM contacts c
        JOIN projects p ON p.id = c.project_id
        JOIN campaigns camp ON camp.project_id = c.project_id AND camp.status = 'active'
        WHERE c.domain IS NOT NULL AND c.domain != ''
        GROUP BY lower(c.domain), c.project_id, p.name
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_acd_domain_project ON active_campaign_domains(domain, project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_acd_project ON active_campaign_domains(project_id)")


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS active_campaign_domains")

    op.drop_constraint("fk_sj_gathering_run", "search_jobs", type_="foreignkey")
    op.drop_column("search_jobs", "gathering_run_id")

    op.drop_constraint("fk_dc_latest_analysis", "discovered_companies", type_="foreignkey")
    op.drop_constraint("fk_dc_crm_contact", "discovered_companies", type_="foreignkey")
    op.drop_constraint("fk_dc_first_found_by", "discovered_companies", type_="foreignkey")
    op.drop_column("discovered_companies", "linkedin_company_url")
    op.drop_column("discovered_companies", "latest_analysis_segment")
    op.drop_column("discovered_companies", "latest_analysis_verdict")
    op.drop_column("discovered_companies", "latest_analysis_run_id")
    op.drop_column("discovered_companies", "crm_contact_id")
    op.drop_column("discovered_companies", "campaign_ids_active")
    op.drop_column("discovered_companies", "in_active_campaign")
    op.drop_column("discovered_companies", "blacklist_checked_at")
    op.drop_column("discovered_companies", "first_found_by")
    op.drop_column("discovered_companies", "source_count")

    op.drop_table("approval_gates")
    op.drop_table("analysis_results")
    op.drop_table("analysis_runs")
    op.drop_table("gathering_prompts")
    op.drop_table("company_scrapes")
    op.drop_table("company_source_links")
    op.drop_table("gathering_runs")
