"""
CRM Contact and Project Models.

Simple, flat contact management with optional project grouping.
One table for all contacts from all sources, with filters.
Includes activity tracking for multi-channel communication history.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Project(Base, SoftDeleteMixin, TimestampMixin):
    """
    Project - groups contacts for specific outreach campaigns.
    
    Each project can have:
    - Target industries/segments
    - Associated contacts
    - Generated TAM analysis (future: AI SDR)
    - Generated GTM plan (future: AI SDR)
    """
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Target criteria (for AI SDR later)
    target_industries = Column(Text, nullable=True)  # JSON-like string of industries
    target_segments = Column(Text, nullable=True)    # JSON-like string of segments
    
    # Campaign filters — project = saved selection of campaigns
    campaign_filters = Column(JSON, nullable=True)   # List of campaign names: ["Campaign A", "Campaign B"]

    # Auto-reply prompt linked from conversation analysis
    reply_prompt_template_id = Column(Integer, ForeignKey("reply_prompt_templates.id", ondelete="SET NULL"), nullable=True)

    # Auto-enrichment config for pipeline
    # {"auto_extract": true, "auto_apollo": false, "apollo_titles": ["CEO","Founder"], "apollo_max_people": 5, "apollo_max_credits": 50}
    auto_enrich_config = Column(JSON, nullable=True)

    # Telegram notification routing
    telegram_chat_id = Column(String(100), nullable=True)  # Resolved numeric chat ID
    telegram_username = Column(String(100), nullable=True)  # @username (lowercase, no @)

    # Generated content (for AI SDR later)
    tam_analysis = Column(Text, nullable=True)       # Total Addressable Market analysis
    gtm_plan = Column(Text, nullable=True)           # Go-to-market plan
    pitch_templates = Column(Text, nullable=True)    # JSON-like string of templates
    
    # Relationships
    company = relationship("Company", back_populates="projects")
    contacts = relationship("Contact", back_populates="project", cascade="all, delete-orphan")
    

    __table_args__ = (
        Index('ix_projects_company_name', 'company_id', 'name'),
    )


class Contact(Base, SoftDeleteMixin, TimestampMixin):
    """
    Contact - single unified table for all contacts from all sources.
    
    Simple structure:
    - id, email, first_name, last_name
    - company, domain, job_title
    - segment (business segment like "iGaming", "B2B SaaS")
    - project_id (which project this contact belongs to)
    - source (smartlead, apollo, manual, csv)
    - status (lead, contacted, replied, qualified)
    """
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Core contact info
    email = Column(String(255), nullable=False, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Company info
    company_name = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    job_title = Column(String(500), nullable=True)
    
    # Categorization - simple string fields for easy filtering
    segment = Column(String(255), nullable=True, index=True)      # e.g., "iGaming", "B2B SaaS", "FinTech"
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Source tracking
    source = Column(String(50), nullable=False, default="manual", index=True)  # smartlead, apollo, manual, csv
    source_id = Column(String(255), nullable=True)  # Original ID from source system
    
    # Status tracking
    status = Column(String(50), nullable=False, default="lead", index=True)  # lead, contacted, replied, qualified
    
    # Additional info
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    location = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    
    # External system IDs for sync
    smartlead_id = Column(String(100), nullable=True, index=True)
    getsales_id = Column(String(100), nullable=True, index=True)
    
    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    smartlead_status = Column(String(50), nullable=True)  # Status in Smartlead
    getsales_status = Column(String(50), nullable=True)   # Status in GetSales
    
    # Reply tracking
    has_replied = Column(Boolean, default=False, index=True)
    last_reply_at = Column(DateTime, nullable=True)
    reply_channel = Column(String(50), nullable=True)  # email, linkedin
    reply_category = Column(String(50), nullable=True)  # interested, not_interested, meeting_request, etc.
    reply_sentiment = Column(String(20), nullable=True)  # warm, cold, neutral
    funnel_stage = Column(String(50), nullable=True)  # lead, contacted, replied, qualified
    
    # Raw webhook data for debugging
    smartlead_raw = Column(JSON, nullable=True)  # Raw Smartlead webhook payloads
    getsales_raw = Column(JSON, nullable=True)   # Raw GetSales webhook payloads
    
    # Campaign info from source systems
    campaigns = Column(JSON, nullable=True)  # List of {name, id, source, status}
    
    # Relationships
    company = relationship("Company", back_populates="contacts")
    project = relationship("Project", back_populates="contacts")
    activities = relationship("ContactActivity", back_populates="contact", order_by="desc(ContactActivity.created_at)")

    @property
    def needs_followup(self) -> bool:
        """Check if contact needs follow-up (no reply after 3 days)."""
        from datetime import timedelta
        if self.has_replied:
            return False
        if self.last_synced_at is None:
            return False
        return self.last_synced_at < datetime.utcnow() - timedelta(days=3)
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_contacts_company_email', 'company_id', 'email'),
        Index('ix_contacts_company_status', 'company_id', 'status'),
        Index('ix_contacts_company_segment', 'company_id', 'segment'),
        Index('ix_contacts_company_source', 'company_id', 'source'),
        Index('ix_contacts_company_project', 'company_id', 'project_id'),
        Index('ix_contacts_search', 'first_name', 'last_name', 'company_name'),
        Index('ix_contacts_smartlead', 'smartlead_id'),
        Index('ix_contacts_getsales', 'getsales_id'),
        Index('ix_contacts_linkedin', 'linkedin_url'),
    )


class ContactActivity(Base, TimestampMixin):
    """
    ContactActivity - tracks all touches and interactions with a contact.
    
    Activity types:
    - email_sent: Outbound email sent via Smartlead
    - email_opened: Email was opened
    - email_clicked: Link in email was clicked
    - email_replied: Contact replied to email
    - linkedin_sent: LinkedIn message sent via GetSales
    - linkedin_replied: Contact replied on LinkedIn
    - linkedin_connected: LinkedIn connection accepted
    - status_changed: Contact status changed
    - note_added: Manual note added
    """
    __tablename__ = "contact_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Activity info
    activity_type = Column(String(50), nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)  # email, linkedin, manual
    direction = Column(String(20), nullable=True)  # inbound, outbound
    
    # Source tracking
    source = Column(String(50), nullable=False)  # smartlead, getsales, manual
    source_id = Column(String(255), nullable=True)  # Original ID from source system
    
    # Content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    snippet = Column(String(500), nullable=True)  # Short preview
    
    # Extra data
    extra_data = Column(JSON, nullable=True)  # Additional data (campaign_id, sequence_step, etc.)
    
    # Timestamp from source (may differ from created_at)
    activity_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    contact = relationship("Contact", back_populates="activities")
    company = relationship("Company")
    
    __table_args__ = (
        Index('ix_activities_contact_type', 'contact_id', 'activity_type'),
        Index('ix_activities_contact_time', 'contact_id', 'activity_at'),
        Index('ix_activities_company_time', 'company_id', 'activity_at'),
    )
