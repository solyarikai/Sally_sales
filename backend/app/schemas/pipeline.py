"""
Pipeline schemas — request/response models for the outreach pipeline.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============ Enums ============

class DiscoveredCompanyStatusEnum(str, Enum):
    new = "new"
    scraped = "scraped"
    analyzed = "analyzed"
    contacts_extracted = "contacts_extracted"
    enriched = "enriched"
    exported = "exported"
    rejected = "rejected"


class ContactSourceEnum(str, Enum):
    website_scrape = "website_scrape"
    apollo = "apollo"
    manual = "manual"


class PipelineEventTypeEnum(str, Enum):
    search_completed = "search_completed"
    scrape_completed = "scrape_completed"
    analysis_completed = "analysis_completed"
    contact_extracted = "contact_extracted"
    apollo_enriched = "apollo_enriched"
    exported_sheet = "exported_sheet"
    exported_csv = "exported_csv"
    status_changed = "status_changed"
    promoted_to_crm = "promoted_to_crm"
    error = "error"


# ============ Extracted Contact ============

class ExtractedContactResponse(BaseModel):
    id: int
    discovered_company_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: str
    is_verified: bool = False
    verification_method: Optional[str] = None
    contact_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Pipeline Event ============

class PipelineEventResponse(BaseModel):
    id: int
    discovered_company_id: Optional[int] = None
    company_id: int
    event_type: str
    detail: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Discovered Company ============

class DiscoveredCompanyResponse(BaseModel):
    id: int
    company_id: int
    project_id: Optional[int] = None
    domain: str
    name: Optional[str] = None
    url: Optional[str] = None
    is_target: bool = False
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    company_info: Optional[Dict[str, Any]] = None
    status: str
    contacts_count: int = 0
    emails_found: Optional[List[str]] = None
    phones_found: Optional[List[str]] = None
    apollo_people_count: int = 0
    apollo_enriched_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    search_job_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DiscoveredCompanyDetail(DiscoveredCompanyResponse):
    """Extended detail with nested contacts and events."""
    extracted_contacts: List[ExtractedContactResponse] = []
    events: List[PipelineEventResponse] = []


# ============ Search Job Extended ============

class SearchJobFullDetail(BaseModel):
    """Extended job detail with config, results summary, spending."""
    id: int
    company_id: int
    status: str
    search_engine: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None

    # Progress
    queries_total: int = 0
    queries_completed: int = 0
    domains_found: int = 0
    domains_new: int = 0
    domains_trash: int = 0
    domains_duplicate: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Config
    config: Optional[Dict[str, Any]] = None

    # Results summary
    results_total: int = 0
    targets_found: int = 0
    avg_confidence: Optional[float] = None

    # Spending
    yandex_cost: float = 0.0
    openai_tokens_used: int = 0
    openai_cost_estimate: float = 0.0
    crona_credits_used: int = 0
    crona_cost: float = 0.0
    total_cost_estimate: float = 0.0

    class Config:
        from_attributes = True


# ============ Pipeline Stats ============

class SpendingDetail(BaseModel):
    yandex_cost: float = 0.0
    openai_cost_estimate: float = 0.0
    gemini_cost_estimate: float = 0.0
    ai_cost_estimate: float = 0.0
    crona_cost: float = 0.0
    apollo_credits_used: int = 0
    apollo_cost_estimate: float = 0.0
    total_estimate: float = 0.0


class PipelineStats(BaseModel):
    total_discovered: int = 0
    targets: int = 0
    contacts_extracted: int = 0
    enriched: int = 0
    exported: int = 0
    rejected: int = 0
    total_contacts: int = 0
    total_apollo_people: int = 0
    spending: Optional[SpendingDetail] = None


# ============ Export Models ============

class PipelineExportSheetRequest(BaseModel):
    project_id: Optional[int] = None
    is_target: Optional[bool] = None

class PipelineExportSheetResponse(BaseModel):
    sheet_url: str


# ============ Request Models ============

class ExtractContactsRequest(BaseModel):
    discovered_company_ids: List[int] = Field(..., min_length=1)


class ApolloEnrichRequest(BaseModel):
    discovered_company_ids: List[int] = Field(..., min_length=1)
    max_people: int = Field(5, ge=1, le=25)
    titles: Optional[List[str]] = Field(None, description="Filter by job titles, e.g. ['CEO', 'CTO', 'Founder']")
    max_credits: Optional[int] = Field(None, ge=1, description="Max Apollo credits to use")


class PromoteToContactsRequest(BaseModel):
    extracted_contact_ids: List[int] = Field(..., min_length=1)
    project_id: Optional[int] = None
    segment: Optional[str] = None


class BulkStatusUpdateRequest(BaseModel):
    discovered_company_ids: List[int] = Field(..., min_length=1)
    status: DiscoveredCompanyStatusEnum
