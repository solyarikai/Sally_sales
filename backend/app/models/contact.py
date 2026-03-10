"""
CRM Contact and Project Models.

Contact: single pool of all contacts from all sources.
Project: top-level organizer — groups contacts, campaigns, pipeline, knowledge base.
ContactActivity: multi-channel interaction timeline.
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

    # DEPRECATED: use campaign_ownership_rules instead.
    campaign_auto_prefixes = Column(JSON, nullable=True)

    # Campaign ownership rules — declarative rules for auto-discovering campaigns.
    # JSON: {"prefixes": ["str"], "contains": ["str"], "smartlead_tags": ["str"]}
    # Evaluation order: tags (most explicit) > longest prefix > contains (loosest).
    campaign_ownership_rules = Column(JSON, nullable=True)

    # GetSales LinkedIn sender filter — list of sender_profile_uuids allowed for this project.
    # When set, LinkedIn replies are only shown if their sender matches this list.
    # Prevents cross-project misrouting when GetSales attributes a reply to wrong automation.
    getsales_senders = Column(JSON, nullable=True)

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

    # Client-facing external status config (per-project status taxonomy)
    external_status_config = Column(JSON, nullable=True)

    # Calendly integration — members with PAT tokens for fetching available time slots
    # JSON: {"members": [{"id": str, "display_name": str, "pat_token": str, "is_default": bool}]}
    calendly_config = Column(JSON, nullable=True)

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

    Key fields:
      status          13-state funnel (lead → qualified)
      last_reply_at   NULL = no reply, set = replied (replaces has_replied bool)
      provenance      JSON — how this contact was gathered (pipeline story)
      platform_state  JSON — per-platform data keyed by name
                      {"smartlead": {"status": "...", "last_synced": "...", "campaigns": [...]},
                       "getsales":  {"status": "...", "last_synced": "..."}}
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identity
    email = Column(String(255), nullable=False, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    company_name = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    job_title = Column(String(500), nullable=True)
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    location = Column(String(500), nullable=True)

    # Classification
    segment = Column(String(255), nullable=True, index=True)
    suitable_for = Column(JSON, nullable=True)  # ["inxy", "tfp"] — cross-project targeting
    geo = Column(String(50), nullable=True, index=True)
    source = Column(String(50), nullable=False, default="manual", index=True)
    source_id = Column(String(255), nullable=True)

    # Funnel
    status = Column(String(50), nullable=False, default="lead", index=True)
    last_reply_at = Column(DateTime, nullable=True)

    # Provenance — NULL for manual/CSV, rich JSON for pipeline contacts
    provenance = Column(JSON, nullable=True)

    # Platform lookup IDs (indexed for webhook matching)
    smartlead_id = Column(String(100), nullable=True, index=True)
    getsales_id = Column(String(100), nullable=True, index=True)

    # Platform state — per-platform consolidated data
    platform_state = Column(JSON, nullable=True)

    # Email verification
    email_verification_result = Column(String(30), nullable=True)

    # Raw debug data (kept until webhook_events table is created)
    smartlead_raw = Column(JSON, nullable=True)
    getsales_raw = Column(JSON, nullable=True)

    # Client-facing sync
    sheet_qualification = Column(String(100), nullable=True)
    sheet_client_comment = Column(String(2000), nullable=True)
    sheet_row = Column(Integer, nullable=True)

    # Project-specific external status (derived from reply category + internal status)
    status_external = Column(String(100), nullable=True)

    # Operator
    notes = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="contacts")
    project = relationship("Project", back_populates="contacts")
    activities = relationship("ContactActivity", back_populates="contact", order_by="desc(ContactActivity.created_at)")

    # ── Helpers ──

    @property
    def has_replied(self) -> bool:
        return self.last_reply_at is not None

    @property
    def needs_followup(self) -> bool:
        if self.last_reply_at is not None:
            return False
        synced = self._get_latest_sync()
        if synced is None:
            return False
        return synced < datetime.utcnow() - timedelta(days=3)

    def _get_latest_sync(self) -> Optional[datetime]:
        """Most recent sync timestamp across all platforms."""
        if not self.platform_state:
            return None
        latest = None
        for p_data in self.platform_state.values():
            if not isinstance(p_data, dict):
                continue
            ts = p_data.get("last_synced")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    if latest is None or dt > latest:
                        latest = dt
                except (ValueError, TypeError):
                    pass
        return latest

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

    def mark_replied(self, channel: str = "email", at: Optional[datetime] = None):
        """Mark contact as replied with the latest timestamp."""
        reply_time = at or datetime.utcnow()
        if self.last_reply_at is None or reply_time > self.last_reply_at:
            self.last_reply_at = reply_time

    def update_platform_status(self, platform: str, status: str):
        """Update platform status + bump sync timestamp."""
        self.set_platform(platform, {"status": status, "last_synced": datetime.utcnow().isoformat()})

    def update_platform_raw(self, platform: str, raw_data):
        """Store raw webhook/API data in platform_state."""
        self.set_platform(platform, {"raw": raw_data})
        if platform == "smartlead":
            self.smartlead_raw = raw_data
        elif platform == "getsales":
            self.getsales_raw = raw_data

    def mark_synced(self, platform: str):
        """Bump the sync timestamp for a platform."""
        self.set_platform(platform, {"last_synced": datetime.utcnow().isoformat()})

    def set_provenance_data(self, data: dict):
        """Set contact provenance."""
        self.provenance = data

    # Indexes
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
        Index('ix_contacts_replied', 'last_reply_at',
              postgresql_where=text("last_reply_at IS NOT NULL")),
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
