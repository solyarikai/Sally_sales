"""
Telegram Outreach models.

Tables for managing Telegram accounts, proxy groups, outreach campaigns,
message sequences (follow-up chains), recipients, and sent message logs.
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Text, Boolean, Float,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base
from app.models.mixins import TimestampMixin


# ── Enums ──────────────────────────────────────────────────────────────

class TgAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    SPAMBLOCKED = "spamblocked"
    BANNED = "banned"
    DEAD = "dead"
    FROZEN = "frozen"


class TgSpamblockType(str, enum.Enum):
    NONE = "none"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"


class TgProxyProtocol(str, enum.Enum):
    HTTP = "http"
    SOCKS5 = "socks5"
    MTPROTO = "mtproto"


class TgCampaignType(str, enum.Enum):
    ONE_TIME = "one_time"
    DYNAMIC = "dynamic"


class TgCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class TgRecipientStatus(str, enum.Enum):
    PENDING = "pending"
    IN_SEQUENCE = "in_sequence"
    REPLIED = "replied"
    COMPLETED = "completed"
    FAILED = "failed"
    BOUNCED = "bounced"


class TgMessageStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    SPAMBLOCKED = "spamblocked"


# ── Models ─────────────────────────────────────────────────────────────

class TgProxyGroup(Base, TimestampMixin):
    """Group of proxies, typically by country or purpose."""
    __tablename__ = "tg_proxy_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    country = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    proxies = relationship("TgProxy", back_populates="group", cascade="all, delete-orphan")
    accounts = relationship("TgAccount", back_populates="proxy_group")


class TgProxy(Base, TimestampMixin):
    """Individual proxy entry."""
    __tablename__ = "tg_proxies"

    id = Column(Integer, primary_key=True, index=True)
    proxy_group_id = Column(Integer, ForeignKey("tg_proxy_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    protocol = Column(SQLEnum(TgProxyProtocol, values_callable=lambda e: [x.value for x in e]), nullable=False, default=TgProxyProtocol.HTTP)
    is_active = Column(Boolean, nullable=False, default=True)
    last_checked_at = Column(DateTime, nullable=True)

    # Relationships
    group = relationship("TgProxyGroup", back_populates="proxies")


class TgAccountTag(Base, TimestampMixin):
    """Tag for categorizing Telegram accounts."""
    __tablename__ = "tg_account_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(20), nullable=False, default="#6366f1")

    # Relationships
    accounts = relationship("TgAccount", secondary="tg_account_tag_links", back_populates="tags")


class TgAccountTagLink(Base):
    """Many-to-many link between accounts and tags."""
    __tablename__ = "tg_account_tag_links"

    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tg_account_tags.id", ondelete="CASCADE"), primary_key=True)


class TgAccount(Base, TimestampMixin):
    """Telegram user account for outreach."""
    __tablename__ = "tg_accounts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    profile_photo_path = Column(String(500), nullable=True)

    # Telegram client params
    api_id = Column(Integer, nullable=True)
    api_hash = Column(String(100), nullable=True)
    device_model = Column(String(100), nullable=True, default="PC 64bit")
    system_version = Column(String(50), nullable=True, default="Windows 10")
    app_version = Column(String(50), nullable=True, default="6.7.1 x64")
    lang_code = Column(String(10), nullable=True, default="en")
    system_lang_code = Column(String(10), nullable=True, default="en-US")

    # Auth
    two_fa_password = Column(String(255), nullable=True)
    session_file = Column(String(500), nullable=True)
    string_session = Column(Text, nullable=True)  # Telethon StringSession for inbox

    # Proxy
    proxy_group_id = Column(Integer, ForeignKey("tg_proxy_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_proxy_id = Column(Integer, ForeignKey("tg_proxies.id", ondelete="SET NULL"), nullable=True)

    # Status
    status = Column(
        SQLEnum(TgAccountStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgAccountStatus.ACTIVE, index=True,
    )
    spamblock_type = Column(
        SQLEnum(TgSpamblockType, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgSpamblockType.NONE,
    )

    # Limits & counters
    is_premium = Column(Boolean, nullable=False, default=False, server_default="false")
    daily_message_limit = Column(Integer, nullable=False, default=5)
    messages_sent_today = Column(Integer, nullable=False, default=0)
    total_messages_sent = Column(Integer, nullable=False, default=0)

    # Geo + Session age
    country_code = Column(String(5), nullable=True)
    session_created_at = Column(DateTime, nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    skip_warmup = Column(Boolean, nullable=False, default=False, server_default="false")

    # Active warm-up (channel joins, reactions, conversations)
    warmup_active = Column(Boolean, nullable=False, default=False, server_default="false")
    warmup_started_at = Column(DateTime, nullable=True)
    warmup_actions_done = Column(Integer, nullable=False, default=0, server_default="0")

    # Timestamps
    last_connected_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    telegram_created_at = Column(DateTime, nullable=True)
    spamblocked_at = Column(DateTime, nullable=True)
    spamblock_end = Column(DateTime, nullable=True)
    ban_reason = Column(String(255), nullable=True)  # e.g. "abuse_notifications", "send_failed"
    banned_at = Column(DateTime, nullable=True)
    freeze_since = Column(DateTime, nullable=True)
    freeze_until = Column(DateTime, nullable=True)
    freeze_appeal_url = Column(String(500), nullable=True)
    last_spambot_check_at = Column(DateTime, nullable=True)

    # Relationships
    proxy_group = relationship("TgProxyGroup", back_populates="accounts")
    assigned_proxy = relationship("TgProxy", foreign_keys=[assigned_proxy_id])
    tags = relationship("TgAccountTag", secondary="tg_account_tag_links", back_populates="accounts")
    campaign_links = relationship("TgCampaignAccount", back_populates="account", cascade="all, delete-orphan")
    sent_messages = relationship("TgOutreachMessage", back_populates="account")

    __table_args__ = (
        Index("ix_tg_accounts_status", "status"),
        Index("ix_tg_accounts_phone", "phone", unique=True),
    )


class TgCampaign(Base, TimestampMixin):
    """Outreach campaign with sequence, recipients, and sending settings."""
    __tablename__ = "tg_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(
        SQLEnum(TgCampaignStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgCampaignStatus.DRAFT, index=True,
    )

    # Campaign type: one_time (fixed CSV list) or dynamic (CRM segment-based)
    campaign_type = Column(String(20), nullable=False, default="one_time")
    # Filter criteria for dynamic campaigns (JSON: {logic, filters[]})
    segment_filters = Column(JSONB, nullable=True, default=None)
    segment_last_synced_at = Column(DateTime, nullable=True)

    # Sending settings
    daily_message_limit = Column(Integer, nullable=True)
    timezone = Column(String(50), nullable=False, default="Europe/Moscow")
    send_from_hour = Column(Integer, nullable=False, default=9)
    send_to_hour = Column(Integer, nullable=False, default=18)
    send_days = Column(JSONB, nullable=False, default=[0, 1, 2, 3, 4, 5, 6])  # 0=Mon..6=Sun

    # Delays
    delay_between_sends_min = Column(Integer, nullable=False, default=11)
    delay_between_sends_max = Column(Integer, nullable=False, default=25)
    delay_randomness_percent = Column(Integer, nullable=False, default=20)

    # Error tolerance
    spamblock_errors_to_skip = Column(Integer, nullable=False, default=5)

    # Follow-up priority (0=all new leads, 100=all follow-ups)
    followup_priority = Column(Integer, nullable=False, default=100)

    # Send options
    link_preview = Column(Boolean, nullable=False, default=False)
    silent = Column(Boolean, nullable=False, default=False)
    delete_dialog_after = Column(Boolean, nullable=False, default=False)

    # Tags for organization (project names, etc.)
    tags = Column(JSONB, nullable=False, default=list)

    # CRM settings — auto-apply on reply
    crm_tag_on_reply = Column(JSONB, nullable=False, default=list)        # list[str] tags to add to CRM contact on reply
    crm_status_on_reply = Column(String(50), nullable=True, default=None) # TgContactStatus value to set (e.g. "interested")
    crm_owner_on_reply = Column(String(100), nullable=True, default=None) # owner name to assign
    crm_auto_create_contact = Column(Boolean, nullable=False, default=True)  # auto-create CRM contact on reply if missing

    # Counters
    messages_sent_today = Column(Integer, nullable=False, default=0)
    total_messages_sent = Column(Integer, nullable=False, default=0)
    total_recipients = Column(Integer, nullable=False, default=0)

    # Relationships
    account_links = relationship("TgCampaignAccount", back_populates="campaign", cascade="all, delete-orphan")
    recipients = relationship("TgRecipient", back_populates="campaign", cascade="all, delete-orphan")
    sequence = relationship("TgSequence", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    messages = relationship("TgOutreachMessage", back_populates="campaign")


class TgCampaignAccount(Base):
    """Many-to-many link between campaigns and accounts."""
    __tablename__ = "tg_campaign_accounts"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Track per-account spamblock errors within this campaign
    consecutive_spamblock_errors = Column(Integer, nullable=False, default=0)

    # Relationships
    campaign = relationship("TgCampaign", back_populates="account_links")
    account = relationship("TgAccount", back_populates="campaign_links")

    __table_args__ = (
        UniqueConstraint("campaign_id", "account_id", name="uq_tg_campaign_account"),
    )


class TgRecipient(Base, TimestampMixin):
    """Recipient in a campaign."""
    __tablename__ = "tg_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=True)
    company_name = Column(String(255), nullable=True)
    custom_variables = Column(JSONB, nullable=False, default=dict)

    status = Column(
        SQLEnum(TgRecipientStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgRecipientStatus.PENDING, index=True,
    )
    current_step = Column(Integer, nullable=False, default=0)
    assigned_account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="SET NULL"), nullable=True)
    next_message_at = Column(DateTime, nullable=True, index=True)
    last_message_sent_at = Column(DateTime, nullable=True)

    # Inbox tag for reply classification
    inbox_tag = Column(String(50), nullable=True)  # interested, info_requested, not_interested

    # Relationships
    campaign = relationship("TgCampaign", back_populates="recipients")
    assigned_account = relationship("TgAccount", foreign_keys=[assigned_account_id])
    messages = relationship("TgOutreachMessage", back_populates="recipient")

    __table_args__ = (
        Index("ix_tg_recipients_campaign_status", "campaign_id", "status"),
        Index("ix_tg_recipients_next_msg", "next_message_at",
              postgresql_where="next_message_at IS NOT NULL"),
    )


class TgSequence(Base, TimestampMixin):
    """Message sequence (chain of follow-ups) for a campaign."""
    __tablename__ = "tg_sequences"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(255), nullable=True)

    # Relationships
    campaign = relationship("TgCampaign", back_populates="sequence")
    steps = relationship("TgSequenceStep", back_populates="sequence", cascade="all, delete-orphan",
                         order_by="TgSequenceStep.step_order")


class TgSequenceStep(Base, TimestampMixin):
    """Single step in a sequence (e.g., initial message, follow-up 1, etc.)."""
    __tablename__ = "tg_sequence_steps"

    id = Column(Integer, primary_key=True, index=True)
    sequence_id = Column(Integer, ForeignKey("tg_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False, default=1)
    delay_days = Column(Integer, nullable=False, default=0)
    message_type = Column(String(20), nullable=False, default="text", server_default="text")  # text, image, video, document, voice

    # Relationships
    sequence = relationship("TgSequence", back_populates="steps")
    variants = relationship("TgStepVariant", back_populates="step", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("sequence_id", "step_order", name="uq_tg_sequence_step_order"),
    )


class TgStepVariant(Base, TimestampMixin):
    """A/B test variant for a sequence step."""
    __tablename__ = "tg_step_variants"

    id = Column(Integer, primary_key=True, index=True)
    step_id = Column(Integer, ForeignKey("tg_sequence_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_label = Column(String(5), nullable=False, default="A")
    message_text = Column(Text, nullable=False, default="")
    weight_percent = Column(Integer, nullable=False, default=100)
    media_file_path = Column(String(500), nullable=True)  # path to uploaded media file

    # Relationships
    step = relationship("TgSequenceStep", back_populates="variants")


class TgOutreachMessage(Base):
    """Log of every message sent through outreach campaigns."""
    __tablename__ = "tg_outreach_messages"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("tg_recipients.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    step_id = Column(Integer, ForeignKey("tg_sequence_steps.id", ondelete="SET NULL"), nullable=True)
    variant_id = Column(Integer, ForeignKey("tg_step_variants.id", ondelete="SET NULL"), nullable=True)

    rendered_text = Column(Text, nullable=False)
    status = Column(
        SQLEnum(TgMessageStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgMessageStatus.SENT,
    )
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    tg_message_id = Column(Integer, nullable=True)  # Telegram msg ID for read tracking
    read_at = Column(DateTime, nullable=True)  # When recipient read this message

    # Relationships
    campaign = relationship("TgCampaign", back_populates="messages")
    recipient = relationship("TgRecipient", back_populates="messages")
    account = relationship("TgAccount", back_populates="sent_messages")
    step = relationship("TgSequenceStep", foreign_keys=[step_id])
    variant = relationship("TgStepVariant", foreign_keys=[variant_id])

    __table_args__ = (
        Index("ix_tg_outreach_messages_campaign", "campaign_id"),
        Index("ix_tg_outreach_messages_sent", "sent_at"),
    )


class TgIncomingReply(Base):
    """Incoming reply from a recipient to one of our outreach accounts."""
    __tablename__ = "tg_incoming_replies"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("tg_recipients.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    tg_message_id = Column(Integer, nullable=True)
    message_text = Column(Text, nullable=False, default="")
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    campaign = relationship("TgCampaign")
    recipient = relationship("TgRecipient")
    account = relationship("TgAccount")


class TgAutoReplyConfig(Base):
    """Auto-reply configuration per campaign."""
    __tablename__ = "tg_auto_reply_configs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)
    system_prompt = Column(Text, nullable=False, default="You are a helpful business development manager. Reply concisely and professionally. Keep responses short (1-3 sentences).")
    stop_phrases = Column(JSONB, nullable=False, default=list)
    max_replies_per_conversation = Column(Integer, nullable=False, default=5)
    dialog_timeout_hours = Column(Integer, nullable=False, default=24)
    simulate_human = Column(Boolean, nullable=False, default=True)
    model_provider = Column(String(20), nullable=False, default="gemini")  # gemini, openai, anthropic
    knowledge_base = Column(Text, nullable=True)  # plain text KB for AI context
    working_hours_enabled = Column(Boolean, nullable=False, default=False)
    working_hours_start = Column(String(5), nullable=False, default="09:00")  # HH:MM
    working_hours_end = Column(String(5), nullable=False, default="18:00")
    working_hours_timezone = Column(String(50), nullable=False, default="UTC")

    campaign = relationship("TgCampaign")


class TgConversation(Base):
    """Tracks an auto-reply conversation with a recipient."""
    __tablename__ = "tg_conversations"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("tg_recipients.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    messages = Column(JSONB, nullable=False, default=list)
    replies_sent = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    campaign = relationship("TgCampaign")
    recipient = relationship("TgRecipient")
    account = relationship("TgAccount")


class TgInboxDialog(Base):
    """Cached Telegram dialog for unified inbox."""
    __tablename__ = "tg_inbox_dialogs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    peer_id = Column(BigInteger, nullable=False)  # Telegram user ID
    peer_name = Column(String(200), nullable=True)  # first_name + last_name
    peer_username = Column(String(100), nullable=True)
    peer_photo_small = Column(String(500), nullable=True)  # cached photo URL/path
    last_message_text = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    last_message_outbound = Column(Boolean, nullable=True)  # True if last msg is ours
    unread_count = Column(Integer, nullable=False, default=0)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="SET NULL"), nullable=True)
    inbox_tag = Column(String(50), nullable=True)  # interested/info_requested/not_interested
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tg_inbox_dialogs_account_peer", "account_id", "peer_id", unique=True),
    )

    account = relationship("TgAccount")
    campaign = relationship("TgCampaign")


class TgContactStatus(str, enum.Enum):
    COLD = "cold"
    CONTACTED = "contacted"
    REPLIED = "replied"
    INTERESTED = "interested"
    QUALIFIED = "qualified"
    MEETING_SET = "meeting_set"
    CONVERTED = "converted"
    NOT_INTERESTED = "not_interested"


class TgContact(Base, TimestampMixin):
    """Unified CRM contact — aggregated from all campaigns."""
    __tablename__ = "tg_contacts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)

    status = Column(
        SQLEnum(TgContactStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TgContactStatus.COLD, index=True,
    )

    tags = Column(JSONB, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    custom_data = Column(JSONB, nullable=False, default=dict)

    campaigns = Column(JSONB, nullable=False, default=list)
    total_messages_sent = Column(Integer, nullable=False, default=0)
    total_replies_received = Column(Integer, nullable=False, default=0)
    first_contacted_at = Column(DateTime, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)
    last_reply_at = Column(DateTime, nullable=True)
    source_campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="SET NULL"), nullable=True)


class TgCrmCustomFieldType(str, enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    DATE = "date"
    URL = "url"


class TgCrmCustomField(Base, TimestampMixin):
    """Custom property definition for CRM contacts."""
    __tablename__ = "tg_crm_custom_fields"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    field_type = Column(
        SQLEnum(TgCrmCustomFieldType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    options_json = Column(JSONB, nullable=False, default=list)  # for select/multi_select
    sort_order = Column(Integer, nullable=False, default=0)

    values = relationship("TgCrmLeadFieldValue", back_populates="field", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_crm_custom_field_project_name"),
    )


class TgCrmLeadFieldValue(Base, TimestampMixin):
    """Value of a custom field for a specific CRM contact."""
    __tablename__ = "tg_crm_lead_field_values"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("tg_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = Column(Integer, ForeignKey("tg_crm_custom_fields.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(Text, nullable=True)

    field = relationship("TgCrmCustomField", back_populates="values")

    __table_args__ = (
        UniqueConstraint("lead_id", "field_id", name="uq_crm_lead_field_value"),
    )


class TgBlacklist(Base, TimestampMixin):
    """Blacklisted Telegram usernames — recipients matching these are filtered out on upload."""
    __tablename__ = "tg_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=True)
    added_by = Column(String(100), nullable=True)


class TgWarmupChannel(Base):
    """Curated channels for warm-up subscription."""
    __tablename__ = "tg_warmup_channels"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


class TgWarmupActionType(str, enum.Enum):
    CHANNEL_JOIN = "channel_join"
    REACTION = "reaction"
    CONVERSATION = "conversation"
    CHANNEL_VIEW = "channel_view"


class TgWarmupLog(Base):
    """Log of warm-up actions performed by accounts."""
    __tablename__ = "tg_warmup_log"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(
        SQLEnum(TgWarmupActionType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    detail = Column(Text, nullable=True)  # channel URL, reaction emoji, conversation partner
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    performed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    account = relationship("TgAccount")

    __table_args__ = (
        Index("ix_tg_warmup_log_account_at", "account_id", "performed_at"),
    )


# ── Notification Bot ──────────────────────────────────────────────────

class TgNotifyMode(str, enum.Enum):
    ALL = "all"               # every reply
    INTERESTED = "interested"  # only inbox_tag=interested
    NEW_ONLY = "new_only"     # only first reply from a recipient


class TgOutreachNotifSub(Base):
    """Manager subscription for TG outreach reply notifications via Telegram bot."""
    __tablename__ = "tg_outreach_notif_subs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String(100), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(200), nullable=True)
    notify_mode = Column(String(20), nullable=False, default=TgNotifyMode.ALL.value)
    daily_digest = Column(Boolean, nullable=False, default=False)
    digest_hour = Column(Integer, nullable=False, default=9)  # UTC hour
    campaign_ids = Column(JSONB, nullable=True)  # null = all campaigns
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


class TgOutreachNotifLog(Base):
    """Tracks sent notification messages for quick-reply routing."""
    __tablename__ = "tg_outreach_notif_log"

    id = Column(Integer, primary_key=True, index=True)
    bot_message_id = Column(BigInteger, nullable=False, index=True)
    chat_id = Column(String(100), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("tg_recipients.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("tg_accounts.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("tg_campaigns.id", ondelete="CASCADE"), nullable=False)
    recipient_username = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_notif_log_chat_msg", "chat_id", "bot_message_id"),
    )
