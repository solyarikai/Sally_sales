"""
CRM Contact and Project Models.

Contact: single pool of all contacts from all sources.
Project: top-level organizer — groups contacts, campaigns, pipeline, knowledge base.
ContactActivity: multi-channel interaction timeline.

Architecture evolution (in progress):
  NEW fields: provenance (JSON), platform_state (JSON)
  DEPRECATED fields (kept for backward compat, migrate gradually):
    has_replied, reply_channel, reply_category, reply_sentiment, funnel_stage,
    is_email_verified, email_verified_at, smartlead_status, getsales_status,
    smartlead_raw, getsales_raw, last_synced_at, campaigns, gathering_details
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Boolean, JSON, text
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional
from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Project(Base, SoftDeleteMixin, TimestampMixin):
    """
    Project — the root organizer for all outreach activity.

    Everything hangs off a project: campaigns, contacts, pipeline,
    push rules, knowledge base, operator tasks, sheet sync, notifications.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Target criteria
    target_industries = Column(Text, nullable=True)
    target_segments = Column(Text, nullable=True)

    # DEPRECATED: use project.campaigns relationship instead for querying.
    # Kept for backward compat — services still read this during transition.
    campaign_filters = Column(JSON, nullable=True)

    # Auto-reply prompt linked from conversation analysis
    reply_prompt_template_id = Column(Integer, ForeignKey("reply_prompt_templates.id", ondelete="SET NULL"), nullable=True)

    # Auto-enrichment config for pipeline
    auto_enrich_config = Column(JSON, nullable=True)

    # Telegram notification routing
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_username = Column(String(100), nullable=True)
    telegram_first_name = Column(String(100), nullable=True)

    # Sender identity for AI-drafted replies
    sender_name = Column(String(255), nullable=True)
    sender_position = Column(String(255), nullable=True)
    sender_company = Column(String(255), nullable=True)
    sender_signature = Column(Text, nullable=True)

    # Webhook control
    webhooks_enabled = Column(Boolean, default=True, server_default='true', nullable=False)

    # Google Sheet bidirectional sync config
    sheet_sync_config = Column(JSON, nullable=True)

    # Generated content (for AI SDR)
    tam_analysis = Column(Text, nullable=True)
    gtm_plan = Column(Text, nullable=True)
    pitch_templates = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="projects")
    contacts = relationship("Contact", back_populates="project", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="project", cascade="all, delete-orphan")
    channel_accounts = relationship("ChannelAccount", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_projects_company_name', 'company_id', 'name'),
    )


class Contact(Base, SoftDeleteMixin, TimestampMixin):
    """
    Contact — single pool of all contacts from all sources.

    CANONICAL fields (use these in new code):
      - status: 13-status funnel machine (single source of truth)
      - last_reply_at: also serves as has_replied (IS NOT NULL)
      - provenance: JSON — how this contact was gathered (pipeline story)
      - platform_state: JSON — each platform's own data, keyed by platform name

    DEPRECATED fields (still work, migrate away gradually):
      - has_replied → use last_reply_at IS NOT NULL
      - reply_category → use ProcessedReply.category
      - reply_sentiment → use status_machine.is_warm()
      - reply_channel → use latest ContactActivity.channel
      - funnel_stage → use status (duplicate)
      - is_email_verified → use email_verification_result = 'valid'
      - email_verified_at → use email_verifications table
      - smartlead_status → use platform_state["smartlead"]["status"]
      - getsales_status → use platform_state["getsales"]["status"]
      - smartlead_raw → use webhook_events table
      - getsales_raw → use webhook_events table
      - last_synced_at → use platform_state[platform]["last_synced"]
      - campaigns (JSON) → use campaigns table + platform_state
      - gathering_details → use provenance (same data, renamed)
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # ── Identity ──
    email = Column(String(255), nullable=False, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    company_name = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    job_title = Column(String(500), nullable=True)
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    location = Column(String(500), nullable=True)

    # ── Classification ──
    segment = Column(String(255), nullable=True, index=True)
    geo = Column(String(50), nullable=True, index=True)
    source = Column(String(50), nullable=False, default="manual", index=True)
    source_id = Column(String(255), nullable=True)

    # ── Funnel (single source of truth) ──
    status = Column(String(50), nullable=False, default="lead", index=True)
    last_reply_at = Column(DateTime, nullable=True)

    # ── NEW: Provenance (how this contact was gathered) ──
    # NULL for manual/CSV/SmartLead-synced. Rich JSON for pipeline contacts:
    # {gathered_at, source, extracted_contact_id, discovered_company_id,
    #  domain, company_name, confidence, search_job_id, query, search_engine,
    #  segment, geo, description}
    provenance = Column(JSON, nullable=True)

    # ── Platform lookup IDs (indexed for webhook matching) ──
    smartlead_id = Column(String(100), nullable=True, index=True)
    getsales_id = Column(String(100), nullable=True, index=True)

    # ── NEW: Platform state (each platform's own data model) ──
    # {"smartlead": {"status": "...", "category": 1, "last_synced": "...", "campaigns": [...]},
    #  "getsales": {"status": "...", "flow_name": "...", "last_synced": "..."}}
    platform_state = Column(JSON, nullable=True)

    # ── Email verification ──
    email_verification_result = Column(String(30), nullable=True)

    # ── Client-facing sync ──
    sheet_qualification = Column(String(100), nullable=True)
    sheet_client_comment = Column(String(2000), nullable=True)
    sheet_row = Column(Integer, nullable=True)

    # ── Operator ──
    notes = Column(Text, nullable=True)

    # ══════════════════════════════════════════════════════════════
    # DEPRECATED columns — kept for backward compat, migrate away.
    # New code should NOT use these. Use the canonical fields above.
    # ══════════════════════════════════════════════════════════════
    has_replied = Column(Boolean, default=False, index=True)               # → last_reply_at IS NOT NULL
    reply_channel = Column(String(50), nullable=True)                      # → ContactActivity.channel
    reply_category = Column(String(50), nullable=True)                     # → ProcessedReply.category
    reply_sentiment = Column(String(20), nullable=True)                    # → status_machine.is_warm()
    funnel_stage = Column(String(50), nullable=True)                       # → status (duplicate)
    is_email_verified = Column(Boolean, default=False, index=True)         # → email_verification_result='valid'
    email_verified_at = Column(DateTime(timezone=True), nullable=True)     # → email_verifications table
    smartlead_status = Column(String(50), nullable=True)                   # → platform_state["smartlead"]["status"]
    getsales_status = Column(String(50), nullable=True)                    # → platform_state["getsales"]["status"]
    smartlead_raw = Column(JSON, nullable=True)                            # → webhook_events table
    getsales_raw = Column(JSON, nullable=True)                             # → webhook_events table
    last_synced_at = Column(DateTime, nullable=True)                       # → platform_state[p]["last_synced"]
    campaigns = Column(JSON, nullable=True)                                # → campaigns table + platform_state
    gathering_details = Column(JSON, nullable=True)                        # → provenance (renamed)

    # ── Relationships ──
    company = relationship("Company", back_populates="contacts")
    project = relationship("Project", back_populates="contacts")
    activities = relationship("ContactActivity", back_populates="contact", order_by="desc(ContactActivity.created_at)")

    # ── Helper methods for new fields ──

    @property
    def needs_followup(self) -> bool:
        if self.has_replied:
            return False
        if self.last_synced_at is None:
            return False
        return self.last_synced_at < datetime.utcnow() - timedelta(days=3)

    def get_platform(self, platform: str) -> dict:
        """Get state for a specific platform, or empty dict."""
        if not self.platform_state:
            return {}
        return self.platform_state.get(platform, {})

    def set_platform(self, platform: str, data: dict):
        """Update state for a specific platform (merge, don't overwrite)."""
        if not self.platform_state:
            self.platform_state = {}
        existing = self.platform_state.get(platform, {})
        existing.update(data)
        self.platform_state = {**self.platform_state, platform: existing}

    # ── Indexes ──
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
    ContactActivity — tracks all touches and interactions with a contact.

    Activity types:
    - email_sent, email_opened, email_clicked, email_replied
    - linkedin_sent, linkedin_replied, linkedin_connected
    - status_changed, note_added
    """
    __tablename__ = "contact_activities"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)

    activity_type = Column(String(50), nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)
    direction = Column(String(20), nullable=True)

    source = Column(String(50), nullable=False)
    source_id = Column(String(255), nullable=True)

    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    snippet = Column(String(500), nullable=True)

    extra_data = Column(JSON, nullable=True)

    activity_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    contact = relationship("Contact", back_populates="activities")
    company = relationship("Company")

    __table_args__ = (
        Index('ix_activities_contact_type', 'contact_id', 'activity_type'),
        Index('ix_activities_contact_time', 'contact_id', 'activity_at'),
        Index('ix_activities_company_time', 'company_id', 'activity_at'),
    )
