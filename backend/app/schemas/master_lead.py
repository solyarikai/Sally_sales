from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Source tracking
class LeadSource(BaseModel):
    dataset_id: int
    dataset_name: str
    row_id: int
    added_at: datetime


# Field mapping
class FieldMapping(BaseModel):
    source_column: str
    target_field: str  # core field name or "custom"
    custom_field_name: Optional[str] = None  # if target_field == "custom"
    confidence: float = 1.0  # AI confidence score


class FieldMappingSuggestion(BaseModel):
    mappings: List[FieldMapping]
    unmapped_columns: List[str]


# Master Lead schemas
class MasterLeadBase(BaseModel):
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


class MasterLeadCreate(MasterLeadBase):
    sources: List[LeadSource] = Field(default_factory=list)


class MasterLeadResponse(MasterLeadBase):
    id: int
    sources: List[Dict[str, Any]] = []
    enrichment_history: List[Dict[str, Any]] = []
    is_verified: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MasterLeadListResponse(BaseModel):
    leads: List[MasterLeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Add from dataset request
class AddToMasterRequest(BaseModel):
    dataset_id: int
    row_ids: Optional[List[int]] = None  # None = all rows
    field_mappings: List[FieldMapping]


class AddToMasterResponse(BaseModel):
    success: bool
    total_processed: int
    new_leads: int
    updated_leads: int  # duplicates that were merged
    errors: List[str] = []


# Suggest mapping request
class SuggestMappingRequest(BaseModel):
    dataset_id: int
    columns: List[str]
    sample_data: Optional[List[Dict[str, Any]]] = None  # First 5 rows for AI


# Stats
class MasterLeadsStats(BaseModel):
    total_leads: int
    leads_with_email: int
    leads_with_linkedin: int
    sources_count: Dict[str, int]  # dataset_name -> count
    recent_additions: int  # last 7 days


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
