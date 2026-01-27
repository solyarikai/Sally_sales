from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Source tracking
class ProspectSource(BaseModel):
    dataset_id: int
    dataset_name: str
    row_id: int
    added_at: datetime


# Field mapping (reused from master_lead)
class FieldMapping(BaseModel):
    source_column: str
    target_field: str  # core field name or "custom"
    custom_field_name: Optional[str] = None
    confidence: float = 1.0


class FieldMappingSuggestion(BaseModel):
    mappings: List[FieldMapping]
    unmapped_columns: List[str]


# Activity
class ProspectActivityResponse(BaseModel):
    id: int
    prospect_id: int
    activity_type: str
    description: Optional[str]
    activity_data: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


# Prospect schemas
class ProspectBase(BaseModel):
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_linkedin: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ProspectCreate(ProspectBase):
    sources: List[ProspectSource] = Field(default_factory=list)


class ProspectUpdate(BaseModel):
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_linkedin: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class ProspectResponse(ProspectBase):
    id: int
    sources: List[Dict[str, Any]] = []
    enrichment_history: List[Dict[str, Any]] = []
    is_verified: int = 0
    
    # Outreach status - Email
    sent_to_email: bool = False
    sent_to_email_at: Optional[datetime] = None
    email_campaign_id: Optional[str] = None
    email_campaign_name: Optional[str] = None
    email_tool: Optional[str] = None
    
    # Outreach status - LinkedIn
    sent_to_linkedin: bool = False
    sent_to_linkedin_at: Optional[datetime] = None
    linkedin_campaign_id: Optional[str] = None
    linkedin_campaign_name: Optional[str] = None
    linkedin_tool: Optional[str] = None
    
    # Status
    status: str = 'new'
    status_updated_at: Optional[datetime] = None
    
    # Segment
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Lead status options
LEAD_STATUSES = [
    {"value": "new", "label": "New", "color": "gray"},
    {"value": "contacted", "label": "Contacted", "color": "blue"},
    {"value": "interested", "label": "Interested", "color": "green"},
    {"value": "not_interested", "label": "Not Interested", "color": "orange"},
    {"value": "qualified", "label": "Qualified", "color": "emerald"},
    {"value": "unqualified", "label": "Unqualified", "color": "red"},
    {"value": "converted", "label": "Converted", "color": "violet"},
    {"value": "blocklist", "label": "Blocklist", "color": "black"},
]


class ProspectListResponse(BaseModel):
    prospects: List[ProspectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Server-side filtering/sorting request
class ProspectFilterRequest(BaseModel):
    page: int = 1
    page_size: int = 100
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"  # asc or desc
    search: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None  # {field: {operator: value}}


# Add from dataset request
class AddToProspectsRequest(BaseModel):
    dataset_id: int
    row_ids: Optional[List[int]] = None
    field_mappings: List[FieldMapping]


class AddToProspectsResponse(BaseModel):
    success: bool
    total_processed: int
    new_prospects: int
    updated_prospects: int
    errors: List[str] = []


# Suggest mapping request
class SuggestMappingRequest(BaseModel):
    dataset_id: int
    columns: List[str]
    sample_data: Optional[List[Dict[str, Any]]] = None


# Stats
class ProspectStats(BaseModel):
    total_prospects: int
    prospects_with_email: int
    prospects_with_linkedin: int
    sent_to_email: int
    sent_to_linkedin: int
    recent_additions: int  # last 7 days
    call_done: int = 0  # prospects with completed calls
    # Status breakdown
    status_new: int = 0
    status_contacted: int = 0
    status_interested: int = 0
    status_not_interested: int = 0


# Status update request
class StatusUpdateRequest(BaseModel):
    status: str


# Tags
class TagsUpdateRequest(BaseModel):
    tags: List[str]


# Notes
class NotesUpdateRequest(BaseModel):
    notes: str


# Column info for dynamic columns
class ColumnInfo(BaseModel):
    field: str
    header: str
    type: str  # text, email, url, date, boolean, number
    filterable: bool = True
    sortable: bool = True


# Core fields definition for frontend
CORE_FIELDS = [
    {"name": "email", "label": "Email", "type": "email"},
    {"name": "linkedin_url", "label": "LinkedIn URL", "type": "url"},
    {"name": "first_name", "label": "First Name", "type": "text"},
    {"name": "last_name", "label": "Last Name", "type": "text"},
    {"name": "full_name", "label": "Full Name", "type": "text"},
    {"name": "company_name", "label": "Company Name", "type": "text"},
    {"name": "company_domain", "label": "Company Domain", "type": "text"},
    {"name": "company_linkedin", "label": "Company LinkedIn", "type": "url"},
    {"name": "job_title", "label": "Job Title", "type": "text"},
    {"name": "phone", "label": "Phone", "type": "phone"},
    {"name": "location", "label": "Location", "type": "text"},
    {"name": "country", "label": "Country", "type": "text"},
    {"name": "city", "label": "City", "type": "text"},
    {"name": "industry", "label": "Industry", "type": "text"},
    {"name": "company_size", "label": "Company Size", "type": "text"},
    {"name": "website", "label": "Website", "type": "url"},
]

CORE_FIELD_NAMES = [f["name"] for f in CORE_FIELDS]


# Google Sheets export
class GoogleSheetsExportRequest(BaseModel):
    prospect_ids: Optional[List[int]] = None
    columns: Optional[List[str]] = None
    include_custom_fields: bool = True
