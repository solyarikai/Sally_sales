"""
Pipeline Models — Persistent company records, extracted contacts, and audit trail.

DiscoveredCompany: persists across search jobs, tracks companies through the outreach pipeline.
ExtractedContact: contacts found from website scraping or Apollo enrichment.
PipelineEvent: audit trail for all pipeline actions.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Float, Numeric, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db import Base


class DiscoveredCompanyStatus(str, enum.Enum):
    NEW = "new"
    SCRAPED = "scraped"
    ANALYZED = "analyzed"
    CONTACTS_EXTRACTED = "contacts_extracted"
    ENRICHED = "enriched"
    EXPORTED = "exported"
    REJECTED = "rejected"


class ContactSource(str, enum.Enum):
    WEBSITE_SCRAPE = "website_scrape"
    SUBPAGE_SCRAPE = "subpage_scrape"
    APOLLO = "apollo"
    APOLLO_ORG = "apollo_org"
    LINKEDIN = "linkedin"
    CLAY = "clay"
    MANUAL = "manual"


class PipelineEventType(str, enum.Enum):
    SEARCH_COMPLETED = "search_completed"
    SCRAPE_COMPLETED = "scrape_completed"
    ANALYSIS_COMPLETED = "analysis_completed"
    CONTACT_EXTRACTED = "contact_extracted"
    APOLLO_ENRICHED = "apollo_enriched"
    EXPORTED_SHEET = "exported_sheet"
    EXPORTED_CSV = "exported_csv"
    STATUS_CHANGED = "status_changed"
    PROMOTED_TO_CRM = "promoted_to_crm"
    SMARTLEAD_CAMPAIGN_CREATED = "smartlead_campaign_created"
    SMARTLEAD_LEADS_PUSHED = "smartlead_leads_pushed"
    ERROR = "error"


class DiscoveredCompany(Base):
    """
    Persistent company record — survives across search jobs.
    Tracks a company through the full outreach pipeline.
    """
    __tablename__ = "discovered_companies"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Domain and identity
    domain = Column(String(255), nullable=False, index=True)
    name = Column(String(500), nullable=True)
    url = Column(Text, nullable=True)

    # Origin tracking
    search_result_id = Column(Integer, ForeignKey("search_results.id", ondelete="SET NULL"), nullable=True)
    search_job_id = Column(Integer, ForeignKey("search_jobs.id", ondelete="SET NULL"), nullable=True)

    # GPT analysis results (copied from SearchResult for independence)
    is_target = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    company_info = Column(JSON, nullable=True)

    # Segment classification (copied from SearchResult.matched_segment)
    matched_segment = Column(String(100), nullable=True, index=True)

    # Pipeline status
    status = Column(SQLEnum(DiscoveredCompanyStatus), default=DiscoveredCompanyStatus.NEW, nullable=False, index=True)

    # Cached scrape data (for re-processing without re-scraping)
    scraped_html = Column(Text, nullable=True)
    scraped_text = Column(Text, nullable=True)
    scraped_at = Column(DateTime(timezone=True), nullable=True)

    # Contact extraction results
    contacts_count = Column(Integer, default=0)
    emails_found = Column(JSON, nullable=True)
    phones_found = Column(JSON, nullable=True)

    # Apollo enrichment
    apollo_people_count = Column(Integer, default=0)
    apollo_enriched_at = Column(DateTime(timezone=True), nullable=True)
    apollo_credits_used = Column(Integer, default=0)  # Actual credits spent on this domain

    # Apollo organization enrichment (FREE call — /organizations/enrich)
    # Stores: industry, keywords, country, city, estimated_num_employees,
    # annual_revenue, founded_year, linkedin_url, languages, technologies, etc.
    apollo_org_data = Column(JSONB, nullable=True)

    # Multi-source tracking (gathering system)
    source_count = Column(Integer, server_default="1")
    first_found_by = Column(Integer, ForeignKey("gathering_runs.id", ondelete="SET NULL"), nullable=True)

    # CRM blacklist cache
    blacklist_checked_at = Column(DateTime(timezone=True), nullable=True)
    in_active_campaign = Column(Boolean, server_default="false")
    campaign_ids_active = Column(JSONB, nullable=True)
    crm_contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)

    # Latest analysis reference
    latest_analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True)
    latest_analysis_verdict = Column(Boolean, nullable=True)
    latest_analysis_segment = Column(String(100), nullable=True)

    # LinkedIn identity (secondary dedup)
    linkedin_company_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    project = relationship("Project")
    search_result = relationship("SearchResult", foreign_keys=[search_result_id])
    search_job = relationship("SearchJob")
    extracted_contacts = relationship("ExtractedContact", back_populates="discovered_company", cascade="all, delete-orphan")
    events = relationship("PipelineEvent", back_populates="discovered_company", cascade="all, delete-orphan", order_by="desc(PipelineEvent.created_at)")

    __table_args__ = (
        Index("ix_discovered_company_project_domain", "company_id", "project_id", "domain", unique=True),
        Index("ix_discovered_company_status", "company_id", "status"),
        Index("ix_discovered_company_target", "company_id", "project_id", "is_target"),
    )


class ExtractedContact(Base):
    """
    Contact found from website scraping or Apollo enrichment.
    Can be promoted to CRM Contact record.
    """
    __tablename__ = "extracted_contacts"

    id = Column(Integer, primary_key=True, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Contact info
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(100), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    job_title = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)

    # Source tracking
    source = Column(SQLEnum(ContactSource), nullable=False, default=ContactSource.WEBSITE_SCRAPE)
    raw_data = Column(JSON, nullable=True)

    # Apollo search context — which filters/titles were used to find this contact
    # Stores: {titles: [...], max_people: N, domain: "...", ...}
    apollo_search_context = Column(JSONB, nullable=True)

    # Verification
    is_verified = Column(Boolean, default=False)
    verification_method = Column(String(100), nullable=True)

    # CRM promotion
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    discovered_company = relationship("DiscoveredCompany", back_populates="extracted_contacts")
    contact = relationship("Contact")

    __table_args__ = (
        Index("ix_extracted_contact_email", "discovered_company_id", "email"),
    )


class PipelineEvent(Base):
    """
    Audit trail — tracks every action in the pipeline.
    """
    __tablename__ = "pipeline_events"

    id = Column(Integer, primary_key=True, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(SQLEnum(PipelineEventType), nullable=False, index=True)
    detail = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    discovered_company = relationship("DiscoveredCompany", back_populates="events")
    company = relationship("Company")

    __table_args__ = (
        Index("ix_pipeline_event_company_type", "company_id", "event_type"),
    )


class EnrichmentAttempt(Base):
    """
    Log of every enrichment attempt per company — scrape, Apollo call, subpage, etc.
    Tracks success/failure, cost, and contacts found.
    """
    __tablename__ = "enrichment_attempts"

    id = Column(Integer, primary_key=True, index=True)
    discovered_company_id = Column(Integer, ForeignKey("discovered_companies.id", ondelete="CASCADE"), nullable=False)

    source_type = Column(String(50), nullable=False)  # WEBSITE_SCRAPE, SUBPAGE_SCRAPE, APOLLO_PEOPLE, APOLLO_ORG, etc.
    method = Column(String(100), nullable=True)  # "homepage_gpt", "subpage_/contacts", "apollo_titles_CEO"
    attempted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    credits_used = Column(Integer, server_default="0")
    cost_usd = Column(Numeric(10, 4), server_default="0")
    contacts_found = Column(Integer, server_default="0")
    emails_found = Column(Integer, server_default="0")
    status = Column(String(20), nullable=False, server_default="SUCCESS")  # SUCCESS, ZERO_RESULTS, ERROR, SKIPPED
    error_message = Column(Text, nullable=True)
    config = Column(JSONB, nullable=True)  # {titles, max_people, subpage_path, ...}
    result_summary = Column(JSONB, nullable=True)  # {contact_ids, emails, source_url}

    # Relationships
    discovered_company = relationship("DiscoveredCompany", backref="enrichment_attempts")

    __table_args__ = (
        Index("ix_enrichment_attempts_dc_id", "discovered_company_id"),
        Index("ix_enrichment_attempts_source", "source_type", "status"),
        Index("ix_enrichment_attempts_attempted_at", "attempted_at"),
    )


class EnrichmentEffectiveness(Base):
    """
    Aggregated stats per (project, segment, source_type) — the self-evolving brain.
    Recomputed periodically from enrichment_attempts.
    """
    __tablename__ = "enrichment_effectiveness"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    segment = Column(String(255), nullable=True)
    source_type = Column(String(50), nullable=False)

    total_attempts = Column(Integer, server_default="0")
    successful_attempts = Column(Integer, server_default="0")
    total_contacts_found = Column(Integer, server_default="0")
    total_credits_used = Column(Integer, server_default="0")
    success_rate = Column(Numeric(5, 4), server_default="0")
    cost_per_contact = Column(Numeric(10, 4), server_default="0")
    priority_rank = Column(Integer, server_default="99")  # auto-computed, lower = better ROI

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project")

    __table_args__ = (
        Index("uq_enrichment_effectiveness_project_seg_source", "project_id", "segment", "source_type", unique=True),
    )


class EmailVerification(Base):
    """
    Email verification history + 90-day cache.
    Before calling Findymail API, check if a recent valid result exists.
    """
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    service = Column(String(50), nullable=False)  # 'findymail', 'millionverifier'
    result = Column(String(30), nullable=True)  # 'valid', 'invalid', 'catch_all', 'unknown', 'error'
    is_valid = Column(Boolean, nullable=True)
    provider = Column(String(100), nullable=True)  # email provider from API
    raw_response = Column(JSONB, nullable=True)
    cost_usd = Column(Numeric(10, 4), nullable=True)
    credits_used = Column(Integer, server_default="1")
    verified_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # verified_at + 90 days

    # Links
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    extracted_contact_id = Column(Integer, ForeignKey("extracted_contacts.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_email_verifications_email_verified", "email", "verified_at"),
        Index("ix_email_verifications_company_project", "company_id", "project_id"),
    )


class CampaignPushRule(Base):
    """
    Rules for automatically pushing contacts to SmartLead campaigns.
    Each rule defines classification criteria and campaign configuration.
    """
    __tablename__ = "campaign_push_rules"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Classification criteria
    language = Column(String(10), nullable=False, default="any")  # "ru", "en", "any"
    has_first_name = Column(Boolean, nullable=True)  # True=requires name, False=generic emails, None=any
    name_pattern = Column(String(500), nullable=True)  # Optional regex

    # SmartLead campaign config
    campaign_name_template = Column(String(500), nullable=False)  # e.g. "Deliryo {date} Из РФ"
    sequence_language = Column(String(10), nullable=False, default="ru")  # "ru" or "en"
    sequence_template = Column(JSON, nullable=True)  # SmartLead sequences array
    use_first_name_var = Column(Boolean, default=True)  # Whether to use {{first_name}}

    # Campaign settings
    email_account_ids = Column(JSON, nullable=True)  # SmartLead email account IDs
    schedule_config = Column(JSON, nullable=True)  # timezone, days, hours, limits
    campaign_settings = Column(JSON, nullable=True)  # tracking, plain text, follow-up %

    # Limits
    max_leads_per_campaign = Column(Integer, default=500)
    priority = Column(Integer, default=0)  # Higher = checked first
    is_active = Column(Boolean, default=True, nullable=False)

    # Track which SmartLead campaign is currently being filled
    current_campaign_id = Column(String(50), nullable=True)
    current_campaign_lead_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    project = relationship("Project")

    __table_args__ = (
        Index("ix_push_rule_project", "company_id", "project_id", "is_active"),
    )
