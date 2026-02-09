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

    # Debug info
    html_snippet = Column(Text, nullable=True)  # first 2000 chars of scraped HTML

    # Link to discovered company (set when promoted to pipeline)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="SET NULL"), nullable=True)

    scraped_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search_job = relationship("SearchJob", back_populates="results")
    discovered_company = relationship("DiscoveredCompany", foreign_keys=[discovered_company_id])

    __table_args__ = (
        Index("ix_search_results_job_domain", "search_job_id", "domain"),
        Index("ix_search_results_project_target", "project_id", "is_target"),
    )
