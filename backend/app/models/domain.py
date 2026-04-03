"""
Domain Registry Models - Global domain tracking for search dedup and trash filtering.
Domains are GLOBAL (not company-scoped) — any search job populates a shared registry.
SearchJob and SearchQuery are company-scoped.
SearchResult stores per-domain GPT analysis results for a project.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Float, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.db import Base


class DomainStatus(str, enum.Enum):
    ACTIVE = "active"
    TRASH = "trash"


class DomainSource(str, enum.Enum):
    SEARCH_GOOGLE = "search_google"
    SEARCH_YANDEX = "search_yandex"
    SEARCH_APOLLO = "search_apollo"
    SEARCH_CLAY = "search_clay"
    MANUAL = "manual"
    IMPORT = "import"


class SearchJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchEngine(str, enum.Enum):
    GOOGLE_SERP = "google_serp"
    YANDEX_API = "yandex_api"
    APOLLO_ORG = "apollo_org"
    CLAY = "clay"


class SearchQueryStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Domain(Base):
    """
    Global domain registry — shared across all companies.
    Replaces parser/domains/all_domains.csv and trash_domains.csv.
    """
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(DomainStatus), default=DomainStatus.ACTIVE, nullable=False, index=True)
    source = Column(SQLEnum(DomainSource), default=DomainSource.IMPORT, nullable=False)

    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    times_seen = Column(Integer, default=1)

    __table_args__ = (
        Index("ix_domains_status_domain", "status", "domain"),
    )


class SearchJob(Base):
    """
    A search job — company-scoped. Tracks a batch of queries sent to a search engine.
    """
    __tablename__ = "search_jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(SQLEnum(SearchJobStatus), default=SearchJobStatus.PENDING, nullable=False, index=True)
    search_engine = Column(SQLEnum(SearchEngine), nullable=False)

    # Progress counters
    queries_total = Column(Integer, default=0)
    queries_completed = Column(Integer, default=0)
    domains_found = Column(Integer, default=0)
    domains_new = Column(Integer, default=0)
    domains_trash = Column(Integer, default=0)
    domains_duplicate = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Config stored as JSON (max_pages, workers, prompts used, etc.)
    config = Column(JSON, default=dict)

    # Error info
    error_message = Column(Text, nullable=True)

    # Project link (optional — for project-aware search pipeline)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Gathering system link
    gathering_run_id = Column(Integer, ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    company = relationship("Company", back_populates="search_jobs")
    queries = relationship("SearchQuery", back_populates="search_job", cascade="all, delete-orphan")
    results = relationship("SearchResult", back_populates="search_job", cascade="all, delete-orphan")


class SearchQuery(Base):
    """
    Individual query within a SearchJob.
    """
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    search_job_id = Column(Integer, ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    query_text = Column(Text, nullable=False)
    status = Column(SQLEnum(SearchQueryStatus), default=SearchQueryStatus.PENDING, nullable=False)
    domains_found = Column(Integer, default=0)
    pages_scraped = Column(Integer, default=0)

    # Segment/geo tagging for systematic query approach
    segment = Column(String(100), nullable=True, index=True)   # e.g. "real_estate", "investment", "legal"
    geo = Column(String(100), nullable=True, index=True)        # e.g. "dubai", "turkey", "cyprus"
    country = Column(String(100), nullable=True, index=True)    # e.g. "Russia", "UAE", "Turkey"
    language = Column(String(10), nullable=True)                 # "ru" or "en"

    # Query effectiveness tracking (Phase 3)
    targets_found = Column(Integer, default=0)
    effectiveness_score = Column(Float, nullable=True)  # targets_found / max(domains_found, 1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search_job = relationship("SearchJob", back_populates="queries")


class SearchResult(Base):
    """
    Per-domain GPT analysis result within a search job.
    Stores whether a scraped website matches the project's target segments.
    """
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    search_job_id = Column(Integer, ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    domain = Column(String(255), nullable=False, index=True)
    url = Column(Text, nullable=True)

    # GPT analysis results
    is_target = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    company_info = Column(JSON, nullable=True)  # name, description, services etc from GPT
    scores = Column(JSON, nullable=True)  # Multi-criteria scores: {language_match, industry_match, ...}

    # Review status (Phase 2: auto-review + manual review)
    review_status = Column(String(20), nullable=True)  # "confirmed", "rejected", "flagged"
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Query tracking (Phase 3: which query found this domain)
    source_query_id = Column(Integer, ForeignKey("search_queries.id", ondelete="SET NULL"), nullable=True)

    # Segment classification — what segment this company actually belongs to
    matched_segment = Column(String(100), nullable=True, index=True)  # e.g. "real_estate", "investment"

    # Debug info
    html_snippet = Column(Text, nullable=True)  # first 2000 chars of scraped text

    # Link to discovered company (set when promoted to pipeline)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="SET NULL"), nullable=True)

    scraped_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search_job = relationship("SearchJob", back_populates="results")
    discovered_company = relationship("DiscoveredCompany", foreign_keys=[discovered_company_id])
    source_query = relationship("SearchQuery", foreign_keys=[source_query_id])

    __table_args__ = (
        Index("ix_search_results_job_domain", "search_job_id", "domain"),
        Index("ix_search_results_project_target", "project_id", "is_target"),
    )


class ProjectBlacklist(Base):
    """
    Per-project blacklist — domains that should never be re-scraped or re-analyzed.
    Populated automatically from rejected SearchResults and manually.
    """
    __tablename__ = "project_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(255), nullable=False)
    reason = Column(Text, nullable=True)
    source = Column(String(50), default="auto_review")  # auto_review, manual
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_project_blacklist_project_domain", "project_id", "domain", unique=True),
    )


class ProjectSearchKnowledge(Base):
    """
    Accumulated search knowledge for a project — patterns learned from past searches
    and reviews. Fed back into query generation and analysis prompts.
    """
    __tablename__ = "project_search_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Aggregated stats
    total_jobs_run = Column(Integer, default=0)
    total_domains_analyzed = Column(Integer, default=0)
    total_targets_found = Column(Integer, default=0)
    total_false_positives = Column(Integer, default=0)

    # Learned patterns (JSON lists)
    good_query_patterns = Column(JSON, default=list)  # Queries that produced targets
    bad_query_patterns = Column(JSON, default=list)   # Queries that produced only trash
    confirmed_domains = Column(JSON, default=list)     # Domains confirmed as targets
    rejected_domains = Column(JSON, default=list)      # Domains rejected
    industry_keywords = Column(JSON, default=list)     # Keywords from confirmed targets
    anti_keywords = Column(JSON, default=list)         # Keywords from false positives

    # Confidence calibration
    avg_target_confidence = Column(Float, nullable=True)
    avg_false_positive_confidence = Column(Float, nullable=True)
    recommended_threshold = Column(Float, default=0.5)

    # Custom rules (JSON list of rule dicts)
    custom_exclusion_rules = Column(JSON, default=list)

    # Per-project search config: segments, geos, templates, doc_keywords
    # Replaces hardcoded SEGMENTS/DOC_KEYWORDS from query_templates.py
    search_config = Column(JSON, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
