"""
Gathering API — strict linear pipeline with 3 mandatory checkpoints.

All endpoints enforce phase order. Out-of-order calls are rejected with clear error messages.
Prefix: /api/pipeline/gathering/
"""
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.db import get_session
from app.api.companies import get_required_company
from app.models.user import Company
from app.schemas.gathering import (
    StartGatheringRequest, EstimateRequest, StartAnalysisRequest,
    ApproveGateRequest, CreatePromptRequest,
    GatheringRunResponse, GatheringRunDetail,
    CompanyScrapeResponse, AnalysisRunResponse, AnalysisComparisonResponse,
    ApprovalGateResponse, EstimateResponse, SourceCapability,
    GatheringPromptResponse,
)
from app.schemas.pipeline import DiscoveredCompanyResponse
from app.services.gathering_service import gathering_service, PHASE_ORDER
from app.services.gathering_adapters import get_adapter, list_adapters

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline/gathering", tags=["gathering"])


# ══════════════════════════════════════════════════════════════
# PIPELINE PHASES (strict order)
# ══════════════════════════════════════════════════════════════

@router.post("/start", response_model=GatheringRunResponse)
async def start_gathering(
    body: StartGatheringRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Phase 1: GATHER + DEDUP. Creates a new gathering run."""
    try:
        return await gathering_service.start_gathering(
            session=db, project_id=body.project_id, company_id=company.id,
            source_type=body.source_type, filters=body.filters,
            segment_id=body.segment_id, triggered_by=body.triggered_by,
            input_mode=body.input_mode, input_text=body.input_text, notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/blacklist-check")
async def run_blacklist_check(
    run_id: int,
    cross_project: bool = False,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Phase 2: BLACKLIST → creates CHECKPOINT 1 (scope verification).

    Returns detailed per-campaign rejection breakdown. Operator MUST approve
    the checkpoint gate before the pipeline can continue.

    Set cross_project=true to also see warnings about domains in other projects.
    """
    try:
        return await gathering_service.run_blacklist_check(db, run_id, cross_project=cross_project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/pre-filter")
async def run_pre_filter(
    run_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Phase 3: PRE-FILTER (deterministic, free). Requires checkpoint 1 approved."""
    try:
        return await gathering_service.run_pre_filter(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/scrape")
async def scrape_run_companies(
    run_id: int,
    pages: str = "/",
    method: str = "httpx",
    force: bool = False,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Phase 4: SCRAPE (free, httpx). Requires pre-filter complete."""
    try:
        page_list = [p.strip() for p in pages.split(",")]
        return await gathering_service.scrape_companies(db, run_id, pages=page_list, method=method, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/analyze")
async def run_analysis(
    run_id: int,
    prompt_text: str = "",
    model: str = "gpt-4o-mini",
    prompt_name: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Phase 5: ANALYZE (cheap AI) → creates CHECKPOINT 2 (target review).

    Returns target list with confidence scores. Operator MUST approve
    the checkpoint gate before FindyMail can run.
    """
    if not prompt_text:
        raise HTTPException(status_code=400, detail="prompt_text is required for analysis")
    try:
        return await gathering_service.run_analysis(db, run_id, model=model, prompt_text=prompt_text, prompt_name=prompt_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/prepare-verification")
async def prepare_verification(
    run_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """After checkpoint 2 approved: calculate FindyMail cost → creates CHECKPOINT 3.

    Operator MUST approve the cost before FindyMail runs.
    """
    try:
        return await gathering_service.prepare_verification(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# CHECKPOINT APPROVALS
# ══════════════════════════════════════════════════════════════

@router.post("/approval-gates/{gate_id}/approve")
async def approve_checkpoint(
    gate_id: int,
    body: ApproveGateRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Approve a checkpoint gate. Advances the gathering run to the next phase."""
    try:
        return await gathering_service.approve_checkpoint(db, gate_id, body.decided_by, body.decision_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approval-gates/{gate_id}/reject")
async def reject_checkpoint(
    gate_id: int,
    body: ApproveGateRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Reject a checkpoint gate. Run stays at current phase for investigation."""
    try:
        return await gathering_service.reject_checkpoint(db, gate_id, body.decided_by, body.decision_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/approval-gates", response_model=List[ApprovalGateResponse])
async def list_pending_gates(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List pending approval gates for a project."""
    return await gathering_service.get_pending_gates(db, project_id)


# ══════════════════════════════════════════════════════════════
# CANCEL + RE-ANALYZE
# ══════════════════════════════════════════════════════════════

@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: int,
    reason: str = "",
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Cancel a gathering run at any phase. Rejects all pending gates."""
    try:
        run = await gathering_service.cancel_run(db, run_id, reason)
        return {"run_id": run.id, "status": "cancelled", "phase": run.current_phase}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/re-analyze")
async def re_analyze(
    run_id: int,
    prompt_text: str = "",
    model: str = "gpt-4o-mini",
    prompt_name: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Re-run analysis with a different prompt. Only works at checkpoint 2.
    Rejects the current target review gate, resets to scraped, runs new analysis.
    """
    if not prompt_text:
        raise HTTPException(status_code=400, detail="prompt_text is required")
    try:
        return await gathering_service.re_analyze(db, run_id, model=model, prompt_text=prompt_text, prompt_name=prompt_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# RUNS & COMPANIES
# ══════════════════════════════════════════════════════════════

@router.get("/runs", response_model=List[GatheringRunResponse])
async def list_runs(
    project_id: int,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = QueryParam(default=1, ge=1),
    page_size: int = QueryParam(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.get_runs(db, project_id, source_type=source_type, status=status, page=page, page_size=page_size)


@router.get("/runs/{run_id}", response_model=GatheringRunDetail)
async def get_run_detail(
    run_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    run = await gathering_service.get_run_detail(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/companies", response_model=List[DiscoveredCompanyResponse])
async def get_run_companies(
    run_id: int,
    page: int = QueryParam(default=1, ge=1),
    page_size: int = QueryParam(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.get_run_companies(db, run_id, page, page_size)


# ══════════════════════════════════════════════════════════════
# SOURCES
# ══════════════════════════════════════════════════════════════

@router.get("/sources", response_model=List[SourceCapability])
async def list_sources():
    return list_adapters()


@router.get("/sources/{source_type}/schema")
async def get_source_schema(source_type: str):
    try:
        adapter = get_adapter(source_type)
        schema = adapter.get_filter_schema()
        return schema or {"message": f"{source_type} has dynamic filters"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/estimate", response_model=EstimateResponse)
async def estimate_gathering(body: EstimateRequest):
    try:
        adapter = get_adapter(body.source_type)
        validated = await adapter.validate(body.filters)
        result = await adapter.estimate(validated)
        return EstimateResponse(
            source_type=body.source_type, estimated_companies=result.estimated_companies,
            estimated_credits=result.estimated_credits, estimated_cost_usd=result.estimated_cost_usd,
            notes=result.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# SCRAPES & ANALYSIS
# ══════════════════════════════════════════════════════════════

@router.get("/scrapes/{company_id}", response_model=List[CompanyScrapeResponse])
async def get_company_scrapes(
    company_id: int, current_only: bool = True,
    db: AsyncSession = Depends(get_session),
    _company: Company = Depends(get_required_company),
):
    return await gathering_service.get_company_scrapes(db, company_id, current_only)


@router.get("/analysis-runs", response_model=List[AnalysisRunResponse])
async def list_analysis_runs(
    project_id: int,
    page: int = QueryParam(default=1, ge=1),
    page_size: int = QueryParam(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.get_analysis_runs(db, project_id, page, page_size)


@router.get("/analysis-runs/{run_a}/compare/{run_b}", response_model=AnalysisComparisonResponse)
async def compare_analysis_runs(
    run_a: int, run_b: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.compare_analysis_runs(db, run_a, run_b)


# ══════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════

@router.get("/prompts", response_model=List[GatheringPromptResponse])
async def list_prompts(
    project_id: Optional[int] = None, category: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.list_prompts(db, company.id, project_id, category)


@router.post("/prompts", response_model=GatheringPromptResponse)
async def create_prompt(
    body: CreatePromptRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    return await gathering_service.get_or_create_prompt(
        db, company.id, name=body.name, prompt_text=body.prompt_text,
        project_id=body.project_id, category=body.category,
        model_default=body.model_default, created_by=body.created_by,
    )


# ══════════════════════════════════════════════════════════════
# MCP
# ══════════════════════════════════════════════════════════════

@router.get("/mcp/tools")
async def get_mcp_tools():
    from app.services.gathering_mcp import get_mcp_tool_definitions
    return get_mcp_tool_definitions()
