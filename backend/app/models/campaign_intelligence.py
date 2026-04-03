"""
Campaign Intelligence — GOD_SEQUENCE system.

Learns from top-performing campaigns, extracts reusable patterns,
and generates optimized sequences for new campaigns.

Tables:
- CampaignSnapshot: point-in-time performance + sequence freeze
- CampaignPattern: extracted reusable learnings
- CampaignIntelligenceRun: audit trail for extraction cycles
- GeneratedSequence: AI-generated sequences awaiting review
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, Boolean,
    ForeignKey, Index, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db import Base


class CampaignSnapshot(Base):
    """
    Point-in-time performance snapshot of a campaign, including frozen sequences.

    Created daily by the intelligence scheduler. Freezes campaign metrics
    so AI analysis operates on stable, reproducible data.
    """
    __tablename__ = "campaign_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Frozen metrics
    leads_count = Column(Integer, nullable=False, server_default="0")
    total_replies = Column(Integer, nullable=False, server_default="0")
    warm_replies = Column(Integer, nullable=False, server_default="0")
    meetings_count = Column(Integer, nullable=False, server_default="0")
    questions_count = Column(Integer, nullable=False, server_default="0")
    not_interested_count = Column(Integer, nullable=False, server_default="0")
    ooo_count = Column(Integer, nullable=False, server_default="0")
    wrong_person_count = Column(Integer, nullable=False, server_default="0")

    # Calculated scores
    warm_reply_rate = Column(Float, nullable=True)
    meeting_rate = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)

    # Campaign metadata (frozen)
    campaign_name = Column(String(500), nullable=False)
    platform = Column(String(50), nullable=True)
    channel = Column(String(50), nullable=True)
    market = Column(String(50), nullable=True)  # en/ru/ar

    # Sequence content (frozen from SmartLead API)
    sequence_steps = Column(JSONB, nullable=True)
    sequence_step_count = Column(Integer, nullable=True)
    sequence_total_days = Column(Integer, nullable=True)

    # Operator correction stats
    approve_rate = Column(Float, nullable=True)
    edit_rate = Column(Float, nullable=True)

    # Versioning
    snapshot_version = Column(Integer, nullable=False, server_default="1")
    is_latest = Column(Boolean, nullable=False, server_default="true")
    min_sample_size_met = Column(Boolean, nullable=False, server_default="false")

    snapshotted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_cs_campaign_latest", "campaign_id", "is_latest"),
        Index("ix_cs_project_score", "project_id", "quality_score"),
        Index("ix_cs_market_score", "market", "quality_score"),
        Index("ix_cs_company", "company_id"),
    )


class CampaignPattern(Base):
    """
    Extracted reusable pattern from top-performing campaigns.

    3-level knowledge hierarchy:
    - scope_level='universal': Applies to ALL projects (cold email mechanics)
    - scope_level='business':  Applies to all projects with same sender_company
                               (product knowledge, competitors, objections)
    - scope_level='project':   Applies to one project only (market, ICP, language)

    When generating a sequence, all 3 levels are assembled:
    Universal patterns + Business knowledge + Project specifics → Gemini → sequence
    """
    __tablename__ = "campaign_patterns"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Knowledge hierarchy
    scope_level = Column(String(20), nullable=False, server_default="universal")
    # 'universal' = all projects, 'business' = same sender_company, 'project' = one project
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    # NULL for universal. For business-level, points to the "source" project.
    # Business grouping uses Project.sender_company — all projects with same
    # sender_company share business-level patterns.
    business_key = Column(String(255), nullable=True)
    # Denormalized from Project.sender_company for fast filtering.
    # e.g. "easystaff.io" groups project 9 (global) + project 40 (ru)

    # Pattern identity
    pattern_type = Column(String(50), nullable=False)
    # subject_line / body_structure / timing / personalization / cta / tone /
    # sequence_flow / opener / proof_point / objection_preempt
    pattern_key = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Scope
    market = Column(String(50), nullable=True)   # null=universal
    channel = Column(String(50), nullable=True)   # null=universal
    segment = Column(String(100), nullable=True)  # null=universal

    # Evidence
    confidence = Column(Float, nullable=True)
    evidence_campaign_ids = Column(JSONB, nullable=True)  # snapshot IDs
    evidence_summary = Column(Text, nullable=True)
    sample_size = Column(Integer, nullable=True)

    # Versioning
    version = Column(Integer, nullable=False, server_default="1")
    supersedes_id = Column(Integer, ForeignKey("campaign_patterns.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    # Source
    extraction_run_id = Column(Integer, ForeignKey("campaign_intelligence_runs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_cp_type_market", "pattern_type", "market", "is_active"),
        Index("ix_cp_company", "company_id", "is_active"),
    )


class CampaignIntelligenceRun(Base):
    """
    Tracks each pattern extraction cycle — audit trail + incremental processing.
    """
    __tablename__ = "campaign_intelligence_runs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Run scope
    trigger = Column(String(50), nullable=False)  # scheduled / manual
    market_filter = Column(String(50), nullable=True)
    min_sample_size = Column(Integer, nullable=True)

    # Input
    campaigns_analyzed = Column(Integer, nullable=True)
    top_campaigns_count = Column(Integer, nullable=True)
    snapshots_used = Column(JSONB, nullable=True)

    # Output
    patterns_created = Column(Integer, nullable=True, server_default="0")
    patterns_updated = Column(Integer, nullable=True, server_default="0")
    patterns_total = Column(Integer, nullable=True, server_default="0")

    # AI metadata
    model_used = Column(String(100), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)

    # Status
    status = Column(String(30), nullable=False, server_default="processing")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_cir_company_status", "company_id", "status"),
    )


class GeneratedSequence(Base):
    """
    AI-generated campaign sequence awaiting operator review.

    Flow: draft → approved → pushed (to SmartLead) OR draft → rejected
    """
    __tablename__ = "generated_sequences"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Generation context
    generation_prompt = Column(Text, nullable=True)
    patterns_used = Column(JSONB, nullable=True)
    project_knowledge_snapshot = Column(JSONB, nullable=True)

    # Output
    campaign_name = Column(String(500), nullable=True)
    sequence_steps = Column(JSONB, nullable=False)
    sequence_step_count = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=True)

    # Review
    status = Column(String(30), nullable=False, server_default="draft")
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    operator_notes = Column(Text, nullable=True)

    # Push tracking
    pushed_campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    pushed_at = Column(DateTime(timezone=True), nullable=True)

    # AI metadata
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_gs_project_status", "project_id", "status"),
        Index("ix_gs_company", "company_id"),
    )
