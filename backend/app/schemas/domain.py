"""
Domain & Search schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============ Enums ============

class DomainStatusEnum(str, Enum):
    active = "active"
    trash = "trash"


class SearchEngineEnum(str, Enum):
    google_serp = "google_serp"
    yandex_api = "yandex_api"


# ============ Domain schemas ============

class DomainCreate(BaseModel):
    domain: str
    status: DomainStatusEnum = DomainStatusEnum.active


class DomainResponse(BaseModel):
    id: int
    domain: str
    status: str
    source: str
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    times_seen: int = 1

    class Config:
        from_attributes = True


class DomainStats(BaseModel):
    total: int = 0
    active: int = 0
    trash: int = 0


class DomainCheckRequest(BaseModel):
    """Check a list of domains against the registry."""
    domains: List[str]


class DomainCheckResult(BaseModel):
    domain: str
    status: str  # "new", "known", "trash"


class DomainCheckResponse(BaseModel):
    results: List[DomainCheckResult]
    summary: Dict[str, int]  # {"new": 5, "known": 10, "trash": 3}


class DomainImportResponse(BaseModel):
    imported: int = 0
    skipped_duplicates: int = 0
    total_in_file: int = 0


# ============ SearchJob schemas ============

class SearchJobCreate(BaseModel):
    search_engine: SearchEngineEnum
    queries: List[str]
    config: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = Field(False, description="Test mode: domains won't be saved to registry")


class SearchJobResponse(BaseModel):
    id: int
    company_id: int
    status: str
    search_engine: str
    queries_total: int = 0
    queries_completed: int = 0
    domains_found: int = 0
    domains_new: int = 0
    domains_trash: int = 0
    domains_duplicate: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    project_id: Optional[int] = None

    class Config:
        from_attributes = True


class SearchQueryResponse(BaseModel):
    id: int
    query_text: str
    status: str
    domains_found: int = 0
    pages_scraped: int = 0

    class Config:
        from_attributes = True


# ============ SearchResult schemas ============

class SearchResultResponse(BaseModel):
    id: int
    search_job_id: int
    project_id: Optional[int] = None
    domain: str
    url: Optional[str] = None
    is_target: bool = False
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    company_info: Optional[Dict[str, Any]] = None
    html_snippet: Optional[str] = None
    scraped_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SpendingInfo(BaseModel):
    queries_count: int = 0
    yandex_cost: float = 0.0
    openai_tokens_used: int = 0
    openai_cost_estimate: float = 0.0
    total_estimate: float = 0.0
