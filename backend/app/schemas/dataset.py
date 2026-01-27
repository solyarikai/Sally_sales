from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EnrichmentStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Folder schemas
class FolderBase(BaseModel):
    name: str


class FolderCreate(FolderBase):
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


class FolderResponse(FolderBase):
    id: int
    parent_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Dataset schemas
class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None


class DatasetCreate(DatasetBase):
    pass


class GoogleSheetsImport(BaseModel):
    url: str
    name: Optional[str] = None
    sheet_name: Optional[str] = None  # Specific sheet to import


class DatasetResponse(DatasetBase):
    id: int
    source_type: str
    source_url: Optional[str]
    original_filename: Optional[str]
    columns: List[str]
    row_count: int
    folder_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None


class DatasetListResponse(BaseModel):
    datasets: List[DatasetResponse]
    total: int


# DataRow schemas
class DataRowBase(BaseModel):
    data: Dict[str, Any]
    enriched_data: Dict[str, Any] = Field(default_factory=dict)


class DataRowResponse(DataRowBase):
    id: int
    dataset_id: int
    row_index: int
    enrichment_status: EnrichmentStatusEnum
    last_enriched_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class DataRowsPageResponse(BaseModel):
    rows: List[DataRowResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Prompt Template schemas
class PromptTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None  # Deprecated, use tags instead
    tags: Optional[List[str]] = None  # New: list of tags for filtering
    prompt_template: str
    output_column: str
    system_prompt: Optional[str] = None


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    prompt_template: Optional[str] = None
    output_column: Optional[str] = None
    system_prompt: Optional[str] = None


class PromptTemplateResponse(PromptTemplateBase):
    id: int
    is_system: bool
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('tags', mode='before')
    @classmethod
    def ensure_tags_list(cls, v):
        """Convert None to empty list to prevent validation errors"""
        return v if v is not None else []


# Enrichment Job schemas
class EnrichmentJobCreate(BaseModel):
    dataset_id: int
    prompt_template_id: Optional[int] = None
    custom_prompt: Optional[str] = None
    output_column: str
    model: str = "gpt-4o-mini"
    selected_row_ids: Optional[List[int]] = None  # None = process all rows


class EnrichmentJobResponse(BaseModel):
    id: int
    dataset_id: int
    prompt_template_id: Optional[int]
    custom_prompt: Optional[str]
    output_column: str
    model: str
    selected_row_ids: Optional[List[int]]
    status: EnrichmentStatusEnum
    total_rows: int
    processed_rows: int
    failed_rows: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EnrichmentPreviewRequest(BaseModel):
    dataset_id: int
    prompt_template_id: Optional[int] = None
    custom_prompt: Optional[str] = None
    output_column: str
    model: str = "gpt-4o-mini"
    row_ids: List[int]  # Specific rows to preview


class EnrichmentPreviewResponse(BaseModel):
    results: List[Dict[str, Any]]  # row_id -> enriched value
    model_used: str
    tokens_used: int


# Settings
class OpenAISettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    default_model: Optional[str] = None


class OpenAISettingsResponse(BaseModel):
    has_api_key: bool
    default_model: str
    available_models: List[str]


# Integrations
class IntegrationSettingsUpdate(BaseModel):
    instantly_api_key: Optional[str] = None


class IntegrationSettingsResponse(BaseModel):
    instantly_connected: bool
    instantly_campaigns: List[Dict[str, Any]] = []


class InstantlySendLeadsRequest(BaseModel):
    campaign_id: str
    dataset_id: int
    row_ids: Optional[List[int]] = None  # If None, send all rows
    email_column: str  # Column containing email addresses
    first_name_column: Optional[str] = None
    last_name_column: Optional[str] = None
    company_column: Optional[str] = None
    custom_variables: Optional[Dict[str, str]] = None  # Maps variable name to column name


class InstantlySendLeadsResponse(BaseModel):
    success: bool
    leads_sent: int
    errors: List[str] = []


# Findymail Enrichment
class FindymailEnrichmentRequest(BaseModel):
    dataset_id: int
    row_ids: Optional[List[int]] = None  # If None, process all rows
    enrichment_type: str  # 'find_email' or 'verify_email'
    output_column: str
    # For find_email
    name_column: Optional[str] = None  # Column with person's name
    domain_column: Optional[str] = None  # Column with company domain
    # For verify_email
    email_column: Optional[str] = None  # Column with email to verify


class FindymailEnrichmentResponse(BaseModel):
    success: bool
    processed: int
    found: int
    errors: List[str] = []
    total_cost: float = 0.0


# Website Scraper Enrichment
class WebsiteScraperRequest(BaseModel):
    dataset_id: int
    row_ids: Optional[List[int]] = None  # If None, process all rows
    url_column: str  # Column containing website URLs
    output_column: str  # Column to store scraped text
    timeout: int = 10  # Request timeout in seconds


class WebsiteScraperResponse(BaseModel):
    success: bool
    processed: int
    succeeded: int
    failed: int
    errors: List[str] = []
