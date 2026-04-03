"""Pydantic schemas for Telegram Outreach module."""
from datetime import datetime
from typing import Any, Optional
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
    device_model: Optional[str] = "PC 64bit"
    system_version: Optional[str] = "Windows 10"
    app_version: Optional[str] = "6.5.1 x64"
    lang_code: Optional[str] = "en"
    system_lang_code: Optional[str] = "en-US"
    two_fa_password: Optional[str] = None
    is_premium: bool = False


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
    is_premium: Optional[bool] = None
    status: Optional[str] = None
    proxy_group_id: Optional[int] = None
    assigned_proxy_id: Optional[int] = None
    skip_warmup: Optional[bool] = None


class TgAccountResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
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
    daily_message_limit: int = 5
    is_premium: bool = False
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

class SegmentFilter(BaseModel):
    field: str  # "status", "tags", "owner", "custom:<field_id>"
    operator: str  # "in", "not_in", "contains_any", "contains_all", "eq", "neq"
    value: Any  # list[str] for in/contains, str for eq/neq


class SegmentFilters(BaseModel):
    logic: str = "AND"  # "AND" or "OR"
    filters: list[SegmentFilter] = []


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
    project_id: Optional[int] = None
    campaign_type: str = "one_time"  # "one_time" or "dynamic"
    segment_filters: Optional[SegmentFilters] = None
    tags: Optional[list[str]] = None
    crm_tag_on_reply: Optional[list[str]] = None
    crm_status_on_reply: Optional[str] = None
    crm_owner_on_reply: Optional[str] = None
    crm_auto_create_contact: bool = True


class TgCampaignUpdate(BaseModel):
    project_id: Optional[int] = None
    name: Optional[str] = None
    campaign_type: Optional[str] = None
    segment_filters: Optional[dict] = None
    daily_message_limit: Optional[int] = None
    timezone: Optional[str] = None
    send_from_hour: Optional[int] = None
    send_to_hour: Optional[int] = None
    link_preview: Optional[bool] = None
    silent: Optional[bool] = None
    delete_dialog_after: Optional[bool] = None
    tags: Optional[list[str]] = None
    crm_tag_on_reply: Optional[list[str]] = None
    crm_status_on_reply: Optional[str] = None
    crm_owner_on_reply: Optional[str] = None
    crm_auto_create_contact: Optional[bool] = None


class TgCampaignResponse(TgCampaignBase):
    id: int
    project_id: Optional[int] = None
    status: str = "draft"
    campaign_type: str = "one_time"
    segment_filters: Optional[dict] = None
    segment_last_synced_at: Optional[datetime] = None
    tags: list[str] = []
    crm_tag_on_reply: list[str] = []
    crm_status_on_reply: Optional[str] = None
    crm_owner_on_reply: Optional[str] = None
    crm_auto_create_contact: bool = True
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
    phone_column: Optional[str] = None
    first_name_column: Optional[str] = None
    company_name_column: Optional[str] = None
    custom_columns: dict[str, str] = {}  # csv_column -> variable_name


class TgCheckDuplicatesRequest(BaseModel):
    """Check usernames for cross-campaign duplicates."""
    usernames: list[str]


class TgDuplicateDetail(BaseModel):
    username: str
    campaign_id: int
    campaign_name: str
    campaign_status: str
    current_step: int
    total_steps: int
    step_label: str
    recipient_status: str
    campaign_completion_pct: int
    assigned_account: Optional[str] = None


class TgCheckDuplicatesResponse(BaseModel):
    total_checked: int
    duplicates_count: int
    duplicates: list[TgDuplicateDetail]


class TgBulkRemoveRecipients(BaseModel):
    """Remove recipients by username from a campaign."""
    usernames: list[str]


# ── Sequence ───────────────────────────────────────────────────────────

class TgStepVariantSchema(BaseModel):
    id: Optional[int] = None
    variant_label: str = "A"
    message_text: str = ""
    weight_percent: int = 100
    media_file_path: Optional[str] = None
    model_config = {"from_attributes": True}


class TgSequenceStepSchema(BaseModel):
    id: Optional[int] = None
    step_order: int = 1
    delay_days: int = 0
    message_type: str = "text"  # text, image, video, document, voice
    variants: list[TgStepVariantSchema] = []
    model_config = {"from_attributes": True}


class TgSequenceSchema(BaseModel):
    """Full sequence with all steps and variants — used for both read and write."""
    id: Optional[int] = None
    name: Optional[str] = None
    steps: list[TgSequenceStepSchema] = []
    model_config = {"from_attributes": True}


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


class TgWarmupChannelCreate(BaseModel):
    url: str
    title: Optional[str] = None


class TgWarmupChannelResponse(BaseModel):
    id: int
    url: str
    title: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Campaign Timeline ────────────────────────────────────────────────

class TgTimelineStepStatus(BaseModel):
    """Status of a single message step for a recipient in the timeline."""
    status: str  # scheduled, sent, read, replied, failed, spamblocked, pending
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TgTimelineRecipient(BaseModel):
    """One row in the campaign timeline grid."""
    id: int
    username: str
    first_name: Optional[str] = None
    status: str
    assigned_account_id: Optional[int] = None
    assigned_account_phone: Optional[str] = None
    next_message_at: Optional[datetime] = None
    steps: dict[str, TgTimelineStepStatus] = {}  # key = step_order as string


class TgTimelineStep(BaseModel):
    """Column header info for the timeline."""
    step_order: int
    step_id: int
    delay_days: int


class TgCampaignTimelineResponse(BaseModel):
    steps: list[TgTimelineStep] = []
    recipients: list[TgTimelineRecipient] = []
    total: int = 0
    page: int = 1
    page_size: int = 50


# ── CRM Custom Fields ────────────────────────────────────────────────

class TgCrmCustomFieldCreate(BaseModel):
    name: str
    field_type: str  # text, number, select, multi_select, date, url
    options_json: list = []
    project_id: Optional[int] = None
    sort_order: int = 0


class TgCrmCustomFieldUpdate(BaseModel):
    name: Optional[str] = None
    field_type: Optional[str] = None
    options_json: Optional[list] = None
    sort_order: Optional[int] = None


class TgCrmCustomFieldResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    name: str
    field_type: str
    options_json: list = []
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TgCrmLeadFieldValueUpdate(BaseModel):
    field_id: int
    value: Optional[str] = None


class TgCrmLeadFieldValueResponse(BaseModel):
    id: int
    lead_id: int
    field_id: int
    value: Optional[str] = None
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    options_json: list = []
    model_config = {"from_attributes": True}
