"""
Pipeline Models — Persistent company records, extracted contacts, and audit trail.

DiscoveredCompany: persists across search jobs, tracks companies through the outreach pipeline.
ExtractedContact: contacts found from website scraping or Apollo enrichment.
PipelineEvent: audit trail for all pipeline actions.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Float, Enum as SQLEnum, Index
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
    APOLLO = "apollo"
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
