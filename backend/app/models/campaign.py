"""
Campaign and ChannelAccount models.

Campaign: first-class registry of outreach campaigns across all platforms.
ChannelAccount: sender identities (email accounts, LinkedIn profiles) per platform.

These replace the JSON-blob approach (Project.campaign_filters, Contact.campaigns)
with proper FK relationships that can be indexed and queried.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Index, text
from sqlalchemy.orm import relationship
from app.db import Base
from app.models.mixins import TimestampMixin


class Campaign(Base, TimestampMixin):
    """
    Campaign — registered outreach campaign from any platform.

    Each project has many campaigns (SmartLead email campaigns, GetSales LinkedIn flows, etc.).
    Campaigns are auto-registered from webhooks/sync or created by CampaignPushRule.

    Replaces:
      - Project.campaign_filters JSON (deprecated, kept for backward compat)
      - Contact.campaigns JSON (campaign info now lives here)
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    platform = Column(String(50), nullable=False)       # smartlead, getsales, instantly
    channel = Column(String(50), nullable=False)         # email, linkedin
    external_id = Column(String(255), nullable=True)     # SmartLead campaign_id, GetSales flow UUID
    name = Column(String(500), nullable=False)
    status = Column(String(50), default="active")        # active, paused, completed, archived

    # Link to the push rule that created this campaign (if auto-created)
    push_rule_id = Column(Integer, ForeignKey("campaign_push_rules.id", ondelete="SET NULL"), nullable=True)

    # Cached stats (refreshed by scheduler)
    leads_count = Column(Integer, default=0)
    replied_count = Column(Integer, default=0)

    # Contact sync tracking
    synced_leads_count = Column(Integer, default=0, nullable=False, server_default="0")
    last_contact_sync_at = Column(DateTime, nullable=True)

    # SmartLead analytics reply_count — shared between webhook & polling paths.
    # Polling reads /analytics, compares with this value; webhook increments it.
    # Prevents redundant pagination when webhook already caught the reply.
    sl_reply_count = Column(Integer, default=0, nullable=False, server_default="0")

    # God Panel — campaign intelligence tracking
    resolution_method = Column(String(50), nullable=True)   # exact_match, prefix_match, sender_match, db_fallback, manual, unresolved
    resolution_detail = Column(Text, nullable=True)          # Human-readable: "Matched prefix 'squarefi - es' → project 47"
    first_seen_at = Column(DateTime, nullable=True, default=datetime.utcnow)  # When campaign was first discovered
    acknowledged = Column(Boolean, nullable=False, default=False, server_default="false")  # Operator reviewed in God Panel

    # Platform-specific config (sequence, schedule, tracking settings)
    config = Column(JSON, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="campaigns")
    company = relationship("Company")

    __table_args__ = (
        Index("uq_campaign_platform_ext", "platform", "external_id", unique=True,
              postgresql_where=text("external_id IS NOT NULL")),
        Index("ix_campaigns_project", "project_id"),
        Index("ix_campaigns_company", "company_id"),
        Index("ix_campaigns_name", "name"),
    )


class ChannelAccount(Base, TimestampMixin):
    """
    ChannelAccount — sender identity on an outreach platform.

    Examples:
      - SmartLead email account (email_account_id → external_id)
      - GetSales LinkedIn profile (senderProfileId → external_id, display_name = "Алекс")
    """
    __tablename__ = "channel_accounts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    platform = Column(String(50), nullable=False)         # smartlead, getsales
    channel = Column(String(50), nullable=False)           # email, linkedin
    external_id = Column(String(255), nullable=False)      # platform-specific account/profile ID
    display_name = Column(String(255), nullable=False)     # "Алекс", "Катя", "Элеонора"
    email = Column(String(255), nullable=True)             # for email accounts
    profile_url = Column(String(500), nullable=True)       # for LinkedIn profiles
    is_active = Column(Boolean, default=True, nullable=False)

    metadata_ = Column("metadata", JSON, nullable=True)    # platform-specific extras

    # Relationships
    project = relationship("Project", back_populates="channel_accounts")
    company = relationship("Company")

    __table_args__ = (
        Index("uq_channel_account", "platform", "external_id", unique=True),
        Index("ix_ca_project", "project_id"),
    )
