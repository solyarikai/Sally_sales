"""
Gathering schemas — request/response models for the TAM gathering pipeline.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Request Models ============

class StartGatheringRequest(BaseModel):
    """Start a new gathering run."""
    project_id: int
    source_type: str = Field(..., description="e.g. apollo.companies.api, clay.companies.emulator")
    filters: Dict[str, Any] = Field(..., description="Source-specific filters (opaque JSONB)")
    segment_id: Optional[int] = None
    triggered_by: str = "operator"
    input_mode: str = "structured"
    input_text: Optional[str] = None
    notes: Optional[str] = None


class EstimateRequest(BaseModel):
    """Estimate cost/results without executing."""
    source_type: str
    filters: Dict[str, Any]


class ContinuePipelineRequest(BaseModel):
    """Continue pipeline to next phase."""
    next_phase: str = Field(..., description="Phase to continue to: dedup, blacklist, scrape, analyze, approve, enrich, verify, push")
    config: Optional[Dict[str, Any]] = None


class StartAnalysisRequest(BaseModel):
    """Start an AI analysis run."""
    project_id: int
    model: str = "gemini-2.5-pro"
    prompt_text: str
    scope_filter: Dict[str, Any] = Field(default_factory=dict, description="e.g. {gathering_run_id: 5} or {status: 'new'}")
    triggered_by: str = "operator"


class ApproveGateRequest(BaseModel):
    decided_by: str = "operator"
    decision_note: Optional[str] = None


class ScrapeRefreshRequest(BaseModel):
    """Trigger re-scrape for specific companies or expired content."""
    discovered_company_ids: Optional[List[int]] = None
    expired_only: bool = True
    pages: List[str] = Field(default=["/"], description="Page paths to scrape")
    method: str = "httpx"


class BlacklistCheckRequest(BaseModel):
    """Dry-run blacklist check against domains."""
    domains: List[str]
    project_id: Optional[int] = None


# ============ Response Models ============

class GatheringRunResponse(BaseModel):
    id: int
    project_id: int
    company_id: int
    source_type: str
    source_label: Optional[str] = None
    source_subtype: Optional[str] = None
    filters: Dict[str, Any]
    filter_hash: str
    status: str
    current_phase: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    raw_results_count: int = 0
    new_companies_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    error_count: int = 0
    credits_used: int = 0
    total_cost_usd: float = 0.0
    target_rate: Optional[float] = None
    avg_analysis_confidence: Optional[float] = None
    cost_per_target_usd: Optional[float] = None
    segment_id: Optional[int] = None
    pipeline_run_id: Optional[int] = None
    parent_run_id: Optional[int] = None
    triggered_by: Optional[str] = None
    input_mode: Optional[str] = None
    input_text: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GatheringRunDetail(GatheringRunResponse):
    """Extended detail with companies and source links."""
    raw_output_sample: Optional[List[Dict[str, Any]]] = None
    companies_count: int = 0


class CompanySourceLinkResponse(BaseModel):
    id: int
    discovered_company_id: int
    gathering_run_id: int
    source_rank: Optional[int] = None
    source_data: Optional[Dict[str, Any]] = None
    source_confidence: Optional[float] = None
    found_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyScrapeResponse(BaseModel):
    id: int
    discovered_company_id: int
    url: str
    page_path: str = "/"
    clean_text: Optional[str] = None
    page_metadata: Optional[Dict[str, Any]] = None
    scraped_at: Optional[datetime] = None
    ttl_days: int = 180
    expires_at: Optional[datetime] = None
    is_current: bool = True
    version: int = 1
    scrape_method: str = "httpx"
    scrape_status: str = "success"
    error_message: Optional[str] = None
    http_status_code: Optional[int] = None
    html_size_bytes: Optional[int] = None
    text_size_bytes: Optional[int] = None

    class Config:
        from_attributes = True


class AnalysisRunResponse(BaseModel):
    id: int
    project_id: int
    model: str
    scope_type: str = "batch"
    scope_filter: Optional[Dict[str, Any]] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_analyzed: int = 0
    targets_found: int = 0
    rejected_count: int = 0
    avg_confidence: Optional[float] = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    triggered_by: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisResultResponse(BaseModel):
    id: int
    analysis_run_id: int
    discovered_company_id: int
    is_target: bool = False
    confidence: Optional[float] = None
    segment: Optional[str] = None
    reasoning: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    override_verdict: Optional[bool] = None
    override_reason: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalysisComparisonResponse(BaseModel):
    """Compare two analysis runs — agreements, disagreements, confidence deltas."""
    run_a_id: int
    run_b_id: int
    total_compared: int = 0
    agreements: int = 0
    disagreements: int = 0
    only_in_a: int = 0
    only_in_b: int = 0
    disagreement_details: List[Dict[str, Any]] = []


class ApprovalGateResponse(BaseModel):
    id: int
    project_id: int
    pipeline_run_id: Optional[int] = None
    gathering_run_id: Optional[int] = None
    gate_type: str
    gate_label: str
    scope: Dict[str, Any]
    status: str
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EstimateResponse(BaseModel):
    source_type: str
    estimated_companies: int = 0
    estimated_credits: int = 0
    estimated_cost_usd: float = 0.0
    notes: Optional[str] = None


class DedupeResult(BaseModel):
    total_input: int = 0
    new_companies: int = 0
    duplicates: int = 0
    source_links_created: int = 0


class BlacklistRejectedDomain(BaseModel):
    domain: str
    company_name: Optional[str] = None
    reason: str  # project_blacklist | same_project_campaign | enterprise_blacklist
    detail: str
    campaigns: Optional[List[str]] = None
    contact_count: Optional[int] = None


class BlacklistWarningDomain(BaseModel):
    domain: str
    company_name: Optional[str] = None
    other_project_name: str
    other_project_id: int
    other_contact_count: int = 0
    other_campaigns: List[str] = []


class BlacklistResult(BaseModel):
    """Detailed, project-scoped blacklist check result.

    Key design: only THIS project's campaigns trigger auto-rejection.
    Other projects' campaigns appear as warnings (never auto-reject).
    """
    project_id: int
    project_name: str
    total_checked: int = 0
    passed: int = 0
    rejected_total: int = 0
    in_project_blacklist: int = 0
    in_same_project_campaigns: int = 0
    in_enterprise_blacklist: int = 0
    cross_project_warnings: int = 0
    rejected_domains: List[BlacklistRejectedDomain] = []
    warning_domains: List[BlacklistWarningDomain] = []


class GatheringPromptResponse(BaseModel):
    id: int
    company_id: int
    project_id: Optional[int] = None
    name: str
    prompt_text: str
    prompt_hash: str
    category: str = "icp_analysis"
    model_default: str = "gpt-4o-mini"
    version: int = 1
    usage_count: int = 0
    avg_target_rate: Optional[float] = None
    avg_confidence: Optional[float] = None
    total_companies_analyzed: int = 0
    is_active: bool = True
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreatePromptRequest(BaseModel):
    project_id: Optional[int] = None
    name: str
    prompt_text: str
    category: str = "icp_analysis"
    model_default: str = "gpt-4o-mini"
    created_by: Optional[str] = None


class SourceCapability(BaseModel):
    source_type: str
    source_label: Optional[str] = None
    has_estimate: bool = True
    has_filter_schema: bool = True
    cost_model: str = "free"
    requires_auth: bool = False
    filter_schema: Optional[Dict[str, Any]] = None
