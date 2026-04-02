"""Pydantic schemas for Telegram Outreach module."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Proxy Group ────────────────────────────────────────────────────────

class TgProxyGroupBase(BaseModel):
    name: str
    country: Optional[str] = None
    description: Optional[str] = None


class TgProxyGroupCreate(TgProxyGroupBase):
    pass


class TgProxyGroupUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None


class TgProxyGroupResponse(TgProxyGroupBase):
    id: int
    proxies_count: int = 0
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Proxy ──────────────────────────────────────────────────────────────

class TgProxyBase(BaseModel):
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"


class TgProxyCreate(TgProxyBase):
    pass


class TgProxyBulkCreate(BaseModel):
    """Parse proxies from raw text (one per line, ip:port:user:pass or user:pass@ip:port)."""
    raw_text: str
    protocol: str = "http"


class TgProxyResponse(TgProxyBase):
    id: int
    proxy_group_id: int
    is_active: bool = True
    last_checked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Account Tag ────────────────────────────────────────────────────────

class TgAccountTagBase(BaseModel):
    name: str
    color: str = "#6366f1"


class TgAccountTagCreate(TgAccountTagBase):
    pass


class TgAccountTagResponse(TgAccountTagBase):
    id: int
    model_config = {"from_attributes": True}


# ── Account ────────────────────────────────────────────────────────────

class TgAccountBase(BaseModel):
    phone: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    device_model: Optional[str] = "Samsung SM-G998B"
    system_version: Optional[str] = "SDK 33"
    app_version: Optional[str] = "10.6.2"
    lang_code: Optional[str] = "en"
    system_lang_code: Optional[str] = "en-US"
    two_fa_password: Optional[str] = None


class TgAccountCreate(TgAccountBase):
    session_file_name: Optional[str] = None


class TgAccountUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    device_model: Optional[str] = None
    system_version: Optional[str] = None
    app_version: Optional[str] = None
    lang_code: Optional[str] = None
    system_lang_code: Optional[str] = None
    two_fa_password: Optional[str] = None
    daily_message_limit: Optional[int] = None
    status: Optional[str] = None
    proxy_group_id: Optional[int] = None
    assigned_proxy_id: Optional[int] = None
    skip_warmup: Optional[bool] = None


class TgAccountResponse(BaseModel):
    id: int
    phone: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    device_model: Optional[str] = None
    system_version: Optional[str] = None
    app_version: Optional[str] = None
    lang_code: Optional[str] = None
    system_lang_code: Optional[str] = None
    status: str = "active"
    spamblock_type: str = "none"
    spamblock_end: Optional[datetime] = None
    daily_message_limit: int = 10
    effective_daily_limit: Optional[int] = None
    warmup_day: Optional[int] = None
    is_young_session: bool = False
    skip_warmup: bool = False
    warmup_active: bool = False
    warmup_started_at: Optional[datetime] = None
    warmup_actions_done: int = 0
    warmup_progress: Optional[dict] = None  # {day, total_days, actions_today}
    messages_sent_today: int = 0
    total_messages_sent: int = 0
    proxy_group_id: Optional[int] = None
    proxy_group_name: Optional[str] = None
    assigned_proxy_id: Optional[int] = None
    assigned_proxy_host: Optional[str] = None
    tags: list[TgAccountTagResponse] = []
    campaigns_count: int = 0
    country_code: Optional[str] = None
    telegram_created_at: Optional[datetime] = None
    session_created_at: Optional[datetime] = None
    last_connected_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgAccountListResponse(BaseModel):
    items: list[TgAccountResponse]
    total: int
    page: int
    page_size: int


# ── Campaign ───────────────────────────────────────────────────────────

class TgCampaignBase(BaseModel):
    name: str
    daily_message_limit: Optional[int] = None
    timezone: str = "Europe/Moscow"
    send_from_hour: int = 9
    send_to_hour: int = 18
    delay_between_sends_min: int = 11
    delay_between_sends_max: int = 25
    delay_randomness_percent: int = 20
    spamblock_errors_to_skip: int = 5
    followup_priority: int = 100
    link_preview: bool = False
    silent: bool = False
    delete_dialog_after: bool = False


class TgCampaignCreate(TgCampaignBase):
    tags: Optional[list[str]] = None


class TgCampaignUpdate(BaseModel):
    name: Optional[str] = None
    daily_message_limit: Optional[int] = None
    timezone: Optional[str] = None
    send_from_hour: Optional[int] = None
    send_to_hour: Optional[int] = None
    delay_between_sends_min: Optional[int] = None
    delay_between_sends_max: Optional[int] = None
    delay_randomness_percent: Optional[int] = None
    spamblock_errors_to_skip: Optional[int] = None
    followup_priority: Optional[int] = None
    link_preview: Optional[bool] = None
    silent: Optional[bool] = None
    delete_dialog_after: Optional[bool] = None
    tags: Optional[list[str]] = None


class TgCampaignResponse(TgCampaignBase):
    id: int
    status: str = "draft"
    tags: list[str] = []
    messages_sent_today: int = 0
    total_messages_sent: int = 0
    total_recipients: int = 0
    accounts_count: int = 0
    replies_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgCampaignListResponse(BaseModel):
    items: list[TgCampaignResponse]
    total: int


# ── Recipient ──────────────────────────────────────────────────────────

class TgRecipientBase(BaseModel):
    username: str
    first_name: Optional[str] = None
    company_name: Optional[str] = None
    custom_variables: dict = {}


class TgRecipientCreate(TgRecipientBase):
    pass


class TgRecipientResponse(TgRecipientBase):
    id: int
    campaign_id: int
    status: str = "pending"
    current_step: int = 0
    assigned_account_id: Optional[int] = None
    next_message_at: Optional[datetime] = None
    last_message_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgRecipientListResponse(BaseModel):
    items: list[TgRecipientResponse]
    total: int
    page: int
    page_size: int


class TgRecipientUploadText(BaseModel):
    """Upload recipients as raw text (one @username per line)."""
    raw_text: str


class TgRecipientUploadCSVMapping(BaseModel):
    """Map CSV columns to recipient fields."""
    username_column: str
    first_name_column: Optional[str] = None
    company_name_column: Optional[str] = None
    custom_columns: dict[str, str] = {}  # csv_column -> variable_name


# ── Sequence ───────────────────────────────────────────────────────────

class TgStepVariantSchema(BaseModel):
    id: Optional[int] = None
    variant_label: str = "A"
    message_text: str = ""
    weight_percent: int = 100


class TgSequenceStepSchema(BaseModel):
    id: Optional[int] = None
    step_order: int = 1
    delay_days: int = 0
    variants: list[TgStepVariantSchema] = []


class TgSequenceSchema(BaseModel):
    """Full sequence with all steps and variants — used for both read and write."""
    id: Optional[int] = None
    name: Optional[str] = None
    steps: list[TgSequenceStepSchema] = []


class TgSequencePreviewRequest(BaseModel):
    """Preview: render spintax + variables for a sample recipient."""
    recipient_index: int = 0


class TgSequencePreviewResponse(BaseModel):
    steps: list[dict]  # [{step_order, delay_days, rendered_variants: [{label, text}]}]


# ── Outreach Message ──────────────────────────────────────────────────

class TgOutreachMessageResponse(BaseModel):
    id: int
    campaign_id: int
    recipient_id: int
    recipient_username: Optional[str] = None
    account_id: Optional[int] = None
    account_phone: Optional[str] = None
    step_order: Optional[int] = None
    variant_label: Optional[str] = None
    rendered_text: str
    status: str
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgOutreachMessageListResponse(BaseModel):
    items: list[TgOutreachMessageResponse]
    total: int
    page: int
    page_size: int


# ── Campaign Stats ─────────────────────────────────────────────────────

class TgCampaignStatsResponse(BaseModel):
    total_recipients: int = 0
    pending: int = 0
    in_sequence: int = 0
    completed: int = 0
    replied: int = 0
    failed: int = 0
    bounced: int = 0
    total_messages_sent: int = 0
    messages_sent_today: int = 0


# ── Bulk actions ───────────────────────────────────────────────────────

class TgBulkAssignProxy(BaseModel):
    account_ids: list[int]
    proxy_group_id: int


class TgBulkTag(BaseModel):
    account_ids: list[int]
    tag_id: int


class TgBulkAccountIds(BaseModel):
    account_ids: list[int]


# ── TeleRaptor Import ─────────────────────────────────────────────────

class TgTeleRaptorAccount(BaseModel):
    """Single account in TeleRaptor JSON format."""
    app_id: Optional[int] = None
    app_hash: Optional[str] = None
    sdk: Optional[str] = None          # maps to device_model
    device: Optional[str] = None       # maps to system_version
    app_version: Optional[str] = None
    lang_pack: Optional[str] = None    # maps to lang_code
    system_lang_pack: Optional[str] = None  # maps to system_lang_code
    twoFA: Optional[str] = None        # maps to two_fa_password
    phone: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    spamblock: Optional[str] = None    # "no", "some", "permanent"
    session_file: Optional[str] = None
    stats_spam_count: Optional[int] = 0
    last_connect_date: Optional[str] = None
    tgid: Optional[int] = None
    register_time: Optional[str] = None  # ISO date if available from export
    reg_date: Optional[float] = None  # Unix timestamp from TeleRaptor JSON

    model_config = {"extra": "ignore"}


class TgTeleRaptorImportRequest(BaseModel):
    accounts: list[TgTeleRaptorAccount]


class TgTeleRaptorImportResponse(BaseModel):
    added: int
    skipped: int
    errors: list[str]


# ── Incoming Replies ──────────────────────────────────────────────────

class TgIncomingReplyResponse(BaseModel):
    id: int
    campaign_id: int
    recipient_id: int
    recipient_username: Optional[str] = None
    account_id: Optional[int] = None
    account_phone: Optional[str] = None
    tg_message_id: Optional[int] = None
    message_text: str
    received_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgIncomingReplyListResponse(BaseModel):
    items: list[TgIncomingReplyResponse]
    total: int
    page: int
    page_size: int


# ── Blacklist ─────────────────────────────────────────────────────────

class TgBlacklistUploadText(BaseModel):
    """Upload blacklisted usernames as raw text (one per line, supports @user, t.me/user, etc.)."""
    raw_text: str
    reason: Optional[str] = None


class TgBlacklistResponse(BaseModel):
    id: int
    username: str
    reason: Optional[str] = None
    added_by: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgBlacklistListResponse(BaseModel):
    items: list[TgBlacklistResponse]
    total: int
    page: int
    page_size: int


# ── Warm-up ──────────────────────────────────────────────────────────

class TgWarmupStatusResponse(BaseModel):
    account_id: int
    warmup_active: bool
    warmup_day: Optional[int] = None
    total_days: int = 14
    warmup_started_at: Optional[datetime] = None
    actions_done: int = 0
    actions_today: int = 0
    recent_actions: list[dict] = []  # [{action_type, detail, success, performed_at}]


class TgWarmupLogResponse(BaseModel):
    id: int
    account_id: int
    action_type: str
    detail: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    performed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
