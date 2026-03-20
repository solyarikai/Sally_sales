"""
Gathering Models — TAM gathering pipeline with filter memory, multi-source dedup,
versioned scraping, AI analysis versioning, and approval gates.

GatheringRun: every search execution with exact filters remembered.
CompanySourceLink: multi-source dedup bridge (company found by N sources).
CompanyScrape: versioned website content with TTL-based re-scraping.
AnalysisRun + AnalysisResult: AI analysis with multiple models/prompts, stored per-company.
ApprovalGate: operator checkpoints before credit-spending steps.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float, Numeric, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base


class GatheringRun(Base):
    """
    Every search execution = one record. Remembers EXACTLY which filters were applied.
    Source-agnostic: the DB stores opaque JSONB filters. Adding a new source = new adapter, zero DB changes.
    """
    __tablename__ = "gathering_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source identification — free string, convention: {platform}.{target}.{method}
    source_type = Column(String(100), nullable=False)
    source_label = Column(String(255), nullable=True)
    source_subtype = Column(String(100), nullable=True)

    # Filter memory — source-specific schema stored as opaque JSONB
    filters = Column(JSONB, nullable=False)
    filter_hash = Column(String(64), nullable=False)

    # Execution state — linear pipeline, no skipping
    status = Column(String(30), nullable=False, server_default="pending")
    current_phase = Column(String(30), nullable=False, server_default="gather")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Results summary
    raw_results_count = Column(Integer, server_default="0")
    new_companies_count = Column(Integer, server_default="0")
    duplicate_count = Column(Integer, server_default="0")
    rejected_count = Column(Integer, server_default="0")
    error_count = Column(Integer, server_default="0")

    # Cost
    credits_used = Column(Integer, server_default="0")
    total_cost_usd = Column(Numeric(10, 4), server_default="0")

    # Effectiveness (populated after ANALYZE phase)
    target_rate = Column(Float, nullable=True)
    avg_analysis_confidence = Column(Float, nullable=True)
    cost_per_target_usd = Column(Numeric(10, 4), nullable=True)
    enrichment_hit_rate = Column(Float, nullable=True)

    # Context links
    segment_id = Column(Integer, ForeignKey("kb_segments.id", ondelete="SET NULL"), nullable=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    parent_run_id = Column(Integer, ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True)

    # Operator context
    triggered_by = Column(String(100), nullable=True)
    input_mode = Column(String(30), server_default="structured")
    input_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Raw output (debug/reprocess)
    raw_output_ref = Column(Text, nullable=True)
    raw_output_sample = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project")
    company = relationship("Company")
    parent_run = relationship("GatheringRun", remote_side="GatheringRun.id")
    source_links = relationship("CompanySourceLink", back_populates="gathering_run", cascade="all, delete-orphan")
    approval_gates = relationship("ApprovalGate", back_populates="gathering_run")

    __table_args__ = (
        Index("ix_gr_project_source", "project_id", "source_type", "status"),
        Index("ix_gr_filter_hash", "project_id", "filter_hash"),
        Index("ix_gr_pipeline", "pipeline_run_id"),
        Index("ix_gr_created", "project_id", "created_at"),
    )


class CompanySourceLink(Base):
    """
    Multi-source dedup bridge. Each link = "this company was found by this gathering run."
    One DiscoveredCompany can have many source links (found by Apollo, Clay, CSV, etc.)
    """
    __tablename__ = "company_source_links"

    id = Column(Integer, primary_key=True, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    gathering_run_id = Column(Integer, ForeignKey("gathering_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    source_rank = Column(Integer, nullable=True)
    source_data = Column(JSONB, nullable=True)
    source_confidence = Column(Float, nullable=True)
    found_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    discovered_company = relationship("DiscoveredCompany", backref="source_links")
    gathering_run = relationship("GatheringRun", back_populates="source_links")

    __table_args__ = (
        Index("uq_csl_company_run", "discovered_company_id", "gathering_run_id", unique=True),
    )


class CompanyScrape(Base):
    """
    Versioned website content with TTL-based re-scraping.
    Multiple pages per company (/about, /contact, /team). All versions preserved.
    """
    __tablename__ = "company_scrapes"

    id = Column(Integer, primary_key=True, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    url = Column(Text, nullable=False)
    page_path = Column(String(255), server_default="/")
    raw_html = Column(Text, nullable=True)
    clean_text = Column(Text, nullable=True)
    page_metadata = Column(JSONB, nullable=True)

    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    ttl_days = Column(Integer, server_default="180")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, server_default="true")
    version = Column(Integer, server_default="1")

    scrape_method = Column(String(50), server_default="httpx")
    scrape_status = Column(String(30), server_default="success")
    error_message = Column(Text, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    html_size_bytes = Column(Integer, nullable=True)
    text_size_bytes = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    discovered_company = relationship("DiscoveredCompany", backref="scrapes")

    __table_args__ = (
        Index("ix_cs_company_path_current", "discovered_company_id", "page_path", "is_current"),
        Index("ix_cs_current", "discovered_company_id", postgresql_where="is_current = true"),
        Index("ix_cs_expires", "expires_at", postgresql_where="is_current = true"),
        Index("ix_cs_status", "scrape_status"),
    )


class GatheringPrompt(Base):
    """
    Reusable prompt template for AI analysis. Same prompt can be used across many runs.
    Tracks version history and per-prompt effectiveness.
    """
    __tablename__ = "gathering_prompts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String(255), nullable=False)
    prompt_text = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False, unique=True)

    category = Column(String(50), server_default="icp_analysis")
    model_default = Column(String(100), server_default="gpt-4o-mini")
    version = Column(Integer, server_default="1")
    parent_prompt_id = Column(Integer, ForeignKey("gathering_prompts.id", ondelete="SET NULL"), nullable=True)

    # Effectiveness tracking (updated after analysis runs complete)
    usage_count = Column(Integer, server_default="0")
    avg_target_rate = Column(Float, nullable=True)
    avg_confidence = Column(Float, nullable=True)
    total_companies_analyzed = Column(Integer, server_default="0")

    created_by = Column(String(100), nullable=True)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    project = relationship("Project")
    analysis_runs = relationship("AnalysisRun", back_populates="prompt", foreign_keys="AnalysisRun.prompt_id")

    __table_args__ = (
        Index("ix_gp_company_project", "company_id", "project_id"),
        Index("ix_gp_category", "company_id", "category"),
    )


class AnalysisRun(Base):
    """
    An AI analysis pass over a batch of companies with a specific model + prompt.
    Multiple runs allowed — compare results across models/prompts.
    """
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Prompt reference — prefer FK to gathering_prompts, fallback to inline text
    prompt_id = Column(Integer, ForeignKey("gathering_prompts.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(String(100), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    prompt_text = Column(Text, nullable=True)  # Inline fallback if no prompt_id

    scope_type = Column(String(50), server_default="batch")
    scope_filter = Column(JSONB, nullable=True)

    status = Column(String(30), server_default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    total_analyzed = Column(Integer, server_default="0")
    targets_found = Column(Integer, server_default="0")
    rejected_count = Column(Integer, server_default="0")
    avg_confidence = Column(Float, nullable=True)

    total_cost_usd = Column(Numeric(10, 4), server_default="0")
    total_tokens = Column(Integer, server_default="0")

    triggered_by = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project")
    company = relationship("Company")
    prompt = relationship("GatheringPrompt", back_populates="analysis_runs", foreign_keys=[prompt_id])
    results = relationship("AnalysisResult", back_populates="analysis_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ar_project_status", "project_id", "status"),
        Index("ix_ar_project_model", "project_id", "model"),
        Index("ix_ar_project_prompt", "project_id", "prompt_hash"),
    )


class AnalysisResult(Base):
    """
    Per-company result from an analysis run.
    Stores verdict, confidence, scores, and optional operator override.
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    is_target = Column(Boolean, server_default="false")
    confidence = Column(Float, nullable=True)
    segment = Column(String(100), nullable=True)
    reasoning = Column(Text, nullable=True)
    scores = Column(JSONB, nullable=True)
    raw_output = Column(Text, nullable=True)

    # Operator override
    override_verdict = Column(Boolean, nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_at = Column(DateTime(timezone=True), nullable=True)

    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun", back_populates="results")
    discovered_company = relationship("DiscoveredCompany", backref="analysis_results")

    __table_args__ = (
        Index("uq_ar_run_company", "analysis_run_id", "discovered_company_id", unique=True),
        Index("ix_ar_company", "discovered_company_id"),
        Index("ix_ar_run_target", "analysis_run_id", "is_target"),
    )


class ApprovalGate(Base):
    """
    Pipeline pause before credit-spending steps.
    Operator reviews scope + estimated cost, then approves/rejects.
    """
    __tablename__ = "approval_gates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    gathering_run_id = Column(Integer, ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True)

    gate_type = Column(String(50), nullable=False)
    gate_label = Column(String(255), nullable=False)
    scope = Column(JSONB, nullable=False)

    status = Column(String(30), server_default="pending")
    decided_by = Column(String(100), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project")
    gathering_run = relationship("GatheringRun", back_populates="approval_gates")

    __table_args__ = (
        Index("ix_ag_project_status", "project_id", "status"),
        Index("ix_ag_pending", "status", postgresql_where="status = 'pending'"),
    )
