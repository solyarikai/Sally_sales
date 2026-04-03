"""Pydantic schemas for iGaming module."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ── Contact schemas ────────────────────────────────────────────────────

class IGamingContactBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    job_title: Optional[str] = None
    bio: Optional[str] = None
    other_contact: Optional[str] = None
    organization_name: Optional[str] = None
    website_url: Optional[str] = None
    business_type_raw: Optional[str] = None
    business_type: Optional[str] = None
    source_conference: Optional[str] = None
    sector: Optional[str] = None
    regions: Optional[list] = None
    new_regions_targeting: Optional[list] = None
    channel: Optional[str] = None
    products_services: Optional[str] = None
    tags: Optional[list] = None
    notes: Optional[str] = None


class IGamingContactCreate(IGamingContactBase):
    pass


class IGamingContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    job_title: Optional[str] = None
    bio: Optional[str] = None
    other_contact: Optional[str] = None
    organization_name: Optional[str] = None
    website_url: Optional[str] = None
    business_type_raw: Optional[str] = None
    business_type: Optional[str] = None
    source_conference: Optional[str] = None
    sector: Optional[str] = None
    regions: Optional[list] = None
    channel: Optional[str] = None
    products_services: Optional[str] = None
    tags: Optional[list] = None
    notes: Optional[str] = None
    company_id: Optional[int] = None
    custom_fields: Optional[dict] = None


class IGamingContactResponse(IGamingContactBase):
    id: int
    company_id: Optional[int] = None
    source_id: Optional[str] = None
    source_file: Optional[str] = None
    import_id: Optional[int] = None
    custom_fields: dict = {}
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("company_name", "company_website", mode="before")
    @classmethod
    def extract_company_field(cls, v):
        return v


class IGamingContactListResponse(BaseModel):
    contacts: list[IGamingContactResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Company schemas ────────────────────────────────────────────────────

class IGamingCompanyResponse(BaseModel):
    id: int
    name: str
    name_aliases: list = []
    website: Optional[str] = None
    business_type: Optional[str] = None
    business_type_raw: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[str] = None
    regions: Optional[list] = None
    headquarters: Optional[str] = None
    contacts_count: int = 0
    employees_count: int = 0
    enrichment_data: Optional[dict] = None
    custom_fields: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IGamingCompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    business_type: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[str] = None
    regions: Optional[list] = None
    headquarters: Optional[str] = None
    custom_fields: Optional[dict] = None


class IGamingCompanyListResponse(BaseModel):
    companies: list[IGamingCompanyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Employee schemas ───────────────────────────────────────────────────

class IGamingEmployeeResponse(BaseModel):
    id: int
    company_id: int
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    search_query: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IGamingEmployeeListResponse(BaseModel):
    employees: list[IGamingEmployeeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Import schemas ─────────────────────────────────────────────────────

class IGamingImportUploadResponse(BaseModel):
    file_id: str
    filename: str
    rows_preview: int
    columns: list[str]
    preview: list[dict]


class IGamingImportStartRequest(BaseModel):
    file_id: str
    column_mapping: dict[str, str]
    source_conference: Optional[str] = None
    update_existing: bool = False


class IGamingImportResponse(BaseModel):
    id: int
    filename: str
    source_conference: Optional[str] = None
    status: str
    rows_total: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_updated: int = 0
    companies_created: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── AI Column schemas ─────────────────────────────────────────────────

class IGamingAIColumnCreate(BaseModel):
    name: str
    target: str = "contact"  # "contact" or "company"
    prompt_template: str
    model: str = "gemini-2.5-flash"


class IGamingAIColumnResponse(BaseModel):
    id: int
    name: str
    target: str
    prompt_template: str
    model: str
    is_active: bool
    rows_processed: int
    rows_total: int
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Stats ──────────────────────────────────────────────────────────────

class IGamingStatsResponse(BaseModel):
    total_contacts: int
    total_companies: int
    total_employees: int
    contacts_with_email: int
    contacts_with_linkedin: int
    companies_with_website: int
    top_conferences: list[dict]
    top_business_types: list[dict]
    recent_imports: list[IGamingImportResponse]
