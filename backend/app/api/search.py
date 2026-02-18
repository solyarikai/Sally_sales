"""
Search API — Query generation, search jobs, project search pipeline, SSE, export.

Endpoints:
- POST /search/generate-queries — Generate queries via GPT-4o-mini
- POST /search/jobs — Create and start a search job
- GET  /search/jobs — List search jobs
- GET  /search/jobs/{job_id} — Get job details with queries
- POST /search/jobs/{job_id}/cancel — Cancel running job
- GET  /search/jobs/{job_id}/stream — SSE real-time progress
- POST /search/projects/{project_id}/run — Run full pipeline for project
- GET  /search/projects/{project_id}/results — Get analyzed results
- GET  /search/projects/{project_id}/spending — Cost tracking
- POST /search/projects/{project_id}/export-sheet — Export to Google Sheet
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func as sqlfunc
from typing import Optional, List
from datetime import datetime
import asyncio
import json
import logging

from app.db import get_session, async_session_maker
from app.api.companies import get_required_company
from app.models.user import Company
from app.models.contact import Project, Contact
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchQueryStatus, SearchResult,
)
from app.schemas.domain import (
    SearchJobCreate, SearchJobResponse, SearchQueryResponse,
    SearchResultResponse, SpendingInfo,
)
from app.services.search_service import search_service
from app.services.company_search_service import company_search_service
from app.services.crm_sync_service import parse_campaigns
from app.core.config import settings
from pydantic import BaseModel, Field

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


# ============ Request/Response schemas ============

class GenerateQueriesRequest(BaseModel):
    count: int = Field(50, ge=1, le=1000, description="Number of queries to generate")
    model: Optional[str] = Field("gpt-4o-mini", description="OpenAI model")
    existing_queries: List[str] = Field(default_factory=list, description="Queries to avoid duplicating")
    target_segments: Optional[str] = Field(None, description="Target segments text (or provide project_id)")
    project_id: Optional[int] = Field(None, description="Load target_segments from project")


class GenerateQueriesResponse(BaseModel):
    queries: List[str]
    count: int


class SearchJobDetailResponse(SearchJobResponse):
    queries: List[SearchQueryResponse] = []


class ProjectRunRequest(BaseModel):
    max_queries: int = Field(500, ge=1, le=5000, description="Max queries budget (default 500)")
    target_goal: Optional[int] = Field(None, ge=1, le=10000, description="Stop when this many targets found (default from settings)")


class ProjectRunResponse(BaseModel):
    job_id: int
    status: str = "running"


class ExportSheetResponse(BaseModel):
    sheet_url: str


class ReviewRequest(BaseModel):
    verdict: str = Field(..., description="confirmed, rejected, or flagged")
    note: Optional[str] = Field(None, description="Optional review note")


class BatchSegmentSearchRequest(BaseModel):
    segments: Optional[List[str]] = Field(None, description="Segment keys to search (default: all)")
    geos: Optional[List[str]] = Field(None, description="Geo keys to search (default: all)")
    search_engine: str = Field("google_serp", description="google_serp or yandex_api")
    ai_expand_rounds: int = Field(0, ge=0, le=5, description="AI expansion rounds per combo (0=templates only)")
    max_concurrent: int = Field(2, ge=1, le=5, description="Max concurrent segment searches")


class BatchSegmentSearchResponse(BaseModel):
    status: str = "running"
    total_combos: int
    message: str


class AnalyzeDomainsRequest(BaseModel):
    """Re-analyze unprocessed domains from an existing search job."""
    job_id: int = Field(..., description="SearchJob ID to resume analysis for")
    batch_size: int = Field(50, ge=10, le=200, description="Domains per batch")


class AnalyzeDomainsResponse(BaseModel):
    status: str
    domains_to_analyze: int
    message: str


# ============ Query Generation ============

@router.post("/generate-queries", response_model=GenerateQueriesResponse)
async def generate_queries(
    body: GenerateQueriesRequest,
    db: AsyncSession = Depends(get_session),
):
    """Generate search queries via OpenAI based on target segments."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")

    if not body.target_segments and not body.project_id:
        raise HTTPException(status_code=400, detail="Provide target_segments or project_id")

    try:
        queries = await search_service.generate_queries(
            session=db,
            count=body.count,
            model=body.model,
            existing_queries=body.existing_queries,
            target_segments=body.target_segments,
            project_id=body.project_id,
        )
    except Exception as e:
        logger.error(f"Query generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query generation failed: {str(e)}")

    return GenerateQueriesResponse(queries=queries, count=len(queries))


# ============ Search Jobs ============

@router.post("/jobs", response_model=SearchJobResponse)
async def create_search_job(
    body: SearchJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Create and start a search job."""
    if not body.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    # Clean and dedupe
    cleaned_queries = []
    seen = set()
    for q in body.queries:
        q_text = (q or "").strip()
        if not q_text or q_text in seen:
            continue
        seen.add(q_text)
        cleaned_queries.append(q_text)

    if not cleaned_queries:
        raise HTTPException(status_code=400, detail="All queries were empty or duplicates")

    if body.search_engine == "google_serp" and not settings.APIFY_PROXY_PASSWORD:
        raise HTTPException(status_code=400, detail="APIFY_PROXY_PASSWORD not configured")

    if body.search_engine == "yandex_api":
        if not settings.YANDEX_SEARCH_API_KEY:
            raise HTTPException(status_code=400, detail="YANDEX_SEARCH_API_KEY not configured")
        if not settings.YANDEX_SEARCH_FOLDER_ID:
            raise HTTPException(status_code=400, detail="YANDEX_SEARCH_FOLDER_ID not configured")

    engine = SearchEngine(body.search_engine)

    job_config = body.config.copy() if body.config else {}
    if body.dry_run:
        job_config["dry_run"] = True

    job = SearchJob(
        company_id=company.id,
        status=SearchJobStatus.PENDING,
        search_engine=engine,
        queries_total=len(cleaned_queries),
        config=job_config,
    )
    db.add(job)
    await db.flush()

    for q_text in cleaned_queries:
        sq = SearchQuery(
            search_job_id=job.id,
            query_text=q_text,
        )
        db.add(sq)

    await db.commit()

    background_tasks.add_task(_run_search_job_background, job.id)

    return SearchJobResponse.model_validate(job)


async def _run_search_job_background(job_id: int):
    """Background task wrapper — creates its own DB session."""
    try:
        async with async_session_maker() as session:
            await search_service.run_search_job(session, job_id)
    except Exception as e:
        logger.error(f"Background search job {job_id} crashed: {e}")
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(SearchJob).where(SearchJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = SearchJobStatus.FAILED
                    job.error_message = str(e)[:500]
                    await session.commit()
        except Exception:
            pass


@router.get("/jobs", response_model=List[SearchJobResponse])
async def list_search_jobs(
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List search jobs for the current company."""
    result = await db.execute(
        select(SearchJob)
        .where(SearchJob.company_id == company.id)
        .order_by(desc(SearchJob.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = result.scalars().all()
    return [SearchJobResponse.model_validate(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=SearchJobDetailResponse)
async def get_search_job(
    job_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get search job details with all queries."""
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    q_result = await db.execute(
        select(SearchQuery).where(SearchQuery.search_job_id == job_id)
    )
    queries = q_result.scalars().all()

    job_data = {
        "id": job.id,
        "company_id": job.company_id,
        "status": job.status,
        "search_engine": job.search_engine,
        "queries_total": job.queries_total,
        "queries_completed": job.queries_completed,
        "domains_found": job.domains_found,
        "domains_new": job.domains_new,
        "domains_trash": job.domains_trash,
        "domains_duplicate": job.domains_duplicate,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "project_id": job.project_id,
        "queries": [SearchQueryResponse.model_validate(q) for q in queries],
    }
    return SearchJobDetailResponse(**job_data)


@router.get("/jobs/{job_id}/queries")
async def get_job_queries(
    job_id: int,
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(100, ge=1, le=500),
    status: Optional[str] = QueryParam(None, description="Filter by status"),
    segment: Optional[str] = QueryParam(None, description="Filter by segment"),
    geo: Optional[str] = QueryParam(None, description="Filter by geo"),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get paginated queries for a search job. Supports segment/geo filtering."""
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Search job not found")

    base_filter = [SearchQuery.search_job_id == job_id]
    if status:
        base_filter.append(SearchQuery.status == status)
    if segment:
        base_filter.append(SearchQuery.segment == segment)
    if geo:
        base_filter.append(SearchQuery.geo == geo)

    count_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchQuery).where(*base_filter)
    )
    total = count_q.scalar() or 0

    q = (
        select(SearchQuery)
        .where(*base_filter)
        .order_by(SearchQuery.segment.nulls_last(), SearchQuery.geo.nulls_last(), SearchQuery.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = await db.execute(q)
    queries = rows.scalars().all()

    # Segment/geo breakdown for this job
    from sqlalchemy import text as sql_text
    seg_rows = await db.execute(sql_text("""
        SELECT segment, geo, COUNT(*) as cnt,
               SUM(domains_found) as domains,
               SUM(CASE WHEN status::text = 'done' THEN 1 ELSE 0 END) as done
        FROM search_queries
        WHERE search_job_id = :jid AND segment IS NOT NULL
        GROUP BY segment, geo
        ORDER BY segment, geo
    """), {"jid": job_id})
    segment_groups = [
        {"segment": r[0], "geo": r[1], "queries": r[2], "domains": r[3] or 0, "done": r[4] or 0}
        for r in seg_rows.fetchall()
    ]

    return {
        "items": [SearchQueryResponse.model_validate(q) for q in queries],
        "total": total,
        "page": page,
        "page_size": page_size,
        "segment_groups": segment_groups,
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_search_job(
    job_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Cancel a running search job."""
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    if job.status not in (SearchJobStatus.PENDING, SearchJobStatus.RUNNING):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status {job.status}")

    job.status = SearchJobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()

    return {"message": "Job cancelled"}


# ============ SSE Progress Stream ============

@router.get("/jobs/{job_id}/stream")
async def stream_search_job(
    job_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Server-Sent Events for real-time job progress.

    Note: no X-Company-ID required — EventSource (browser SSE API) cannot send
    custom headers.  The job_id is system-generated and non-guessable.
    """
    result = await db.execute(
        select(SearchJob).where(SearchJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    async def event_generator():
        start_time = datetime.utcnow()

        while True:
            # Fresh session for each poll
            async with async_session_maker() as session:
                result = await session.execute(
                    select(SearchJob).where(SearchJob.id == job_id)
                )
                current_job = result.scalar_one_or_none()

                if not current_job:
                    yield _sse_event("error", {"message": "Job not found"})
                    return

                elapsed = (datetime.utcnow() - start_time).total_seconds()

                # Calculate phase
                if current_job.status == SearchJobStatus.PENDING:
                    phase = "generating_queries"
                elif current_job.status == SearchJobStatus.RUNNING:
                    phase = "searching"
                elif current_job.status == SearchJobStatus.COMPLETED:
                    phase = "completed"
                elif current_job.status == SearchJobStatus.FAILED:
                    phase = "error"
                elif current_job.status == SearchJobStatus.CANCELLED:
                    phase = "cancelled"
                else:
                    phase = "unknown"

                # Estimate remaining time
                estimated_remaining = None
                if current_job.queries_completed and current_job.queries_total:
                    progress_ratio = current_job.queries_completed / current_job.queries_total
                    if progress_ratio > 0:
                        estimated_remaining = round(elapsed / progress_ratio - elapsed, 1)

                # Count results and targets
                results_count = 0
                targets_found = 0
                latest_targets = []
                if current_job.project_id:
                    r = await session.execute(
                        select(SearchResult).where(
                            SearchResult.search_job_id == job_id,
                        )
                    )
                    all_results = r.scalars().all()
                    results_count = len(all_results)

                    target_results = [sr for sr in all_results if sr.is_target]
                    targets_found = len(target_results)

                    # Get last 3 targets for live display
                    sorted_targets = sorted(target_results, key=lambda x: x.analyzed_at or x.scraped_at or datetime.min, reverse=True)
                    for t in sorted_targets[:3]:
                        info = t.company_info or {}
                        latest_targets.append({
                            "domain": t.domain,
                            "name": info.get("name", info.get("company_name", t.domain)),
                            "confidence": t.confidence,
                        })

                # Build phase detail
                current_phase_detail = None
                if phase == "searching" and current_job.queries_completed and current_job.queries_total:
                    current_phase_detail = f"Searching ({current_job.queries_completed}/{current_job.queries_total} queries)"
                elif phase == "generating_queries":
                    current_phase_detail = "Generating search queries with AI..."

                data = {
                    "phase": phase,
                    "status": str(current_job.status.value if hasattr(current_job.status, 'value') else current_job.status),
                    "current": current_job.queries_completed or 0,
                    "total": current_job.queries_total or 0,
                    "domains_found": current_job.domains_found or 0,
                    "domains_new": current_job.domains_new or 0,
                    "results_analyzed": results_count,
                    "targets_found": targets_found,
                    "latest_targets": latest_targets,
                    "current_phase_detail": current_phase_detail,
                    "elapsed_seconds": round(elapsed, 1),
                    "estimated_remaining_seconds": estimated_remaining,
                    "error_message": current_job.error_message,
                }

                yield _sse_event("progress", data)

                # Terminal states — send final event and stop
                if current_job.status in (
                    SearchJobStatus.COMPLETED,
                    SearchJobStatus.FAILED,
                    SearchJobStatus.CANCELLED,
                ):
                    yield _sse_event(phase, data)
                    return

            await asyncio.sleep(2)  # Poll every 2 seconds

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ============ Project-Aware Search Pipeline ============

@router.post("/projects/{project_id}/run", response_model=ProjectRunResponse)
async def run_project_search(
    project_id: int,
    body: ProjectRunRequest = ProjectRunRequest(),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run full search pipeline for a project: generate queries -> Yandex search -> scrape -> analyze."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
    if not settings.YANDEX_SEARCH_API_KEY:
        raise HTTPException(status_code=400, detail="YANDEX_SEARCH_API_KEY not configured")
    if not settings.YANDEX_SEARCH_FOLDER_ID:
        raise HTTPException(status_code=400, detail="YANDEX_SEARCH_FOLDER_ID not configured")

    # Verify project exists and belongs to company
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.target_segments:
        raise HTTPException(status_code=400, detail="Project has no target_segments configured")

    # Create a placeholder job to return immediately
    job = SearchJob(
        company_id=company.id,
        status=SearchJobStatus.PENDING,
        search_engine=SearchEngine.YANDEX_API,
        queries_total=0,  # Will be updated once queries are generated
        project_id=project_id,
        config={"max_queries": body.max_queries, "target_segments": project.target_segments},
    )
    db.add(job)
    await db.commit()

    # Run full pipeline in background
    background_tasks.add_task(_run_project_search_background, job.id, project_id, company.id, body.max_queries, body.target_goal)

    return ProjectRunResponse(job_id=job.id, status="running")


async def _run_project_search_background(job_id: int, project_id: int, company_id: int, max_queries: int, target_goal: int = None):
    """Background task for full project search pipeline."""
    try:
        async with async_session_maker() as session:
            try:
                await company_search_service.run_project_search(
                    session=session,
                    project_id=project_id,
                    company_id=company_id,
                    max_queries=max_queries,
                    target_goal=target_goal,
                    job_id=job_id,
                )
            except Exception as e:
                logger.error(f"Project search pipeline failed: {e}")
                result = await session.execute(
                    select(SearchJob).where(SearchJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job and job.status not in (SearchJobStatus.COMPLETED, SearchJobStatus.CANCELLED):
                    job.status = SearchJobStatus.FAILED
                    job.error_message = str(e)[:500]
                    await session.commit()

    except Exception as e:
        logger.error(f"Background project search crashed: {e}")


@router.post("/projects/{project_id}/batch-segments", response_model=BatchSegmentSearchResponse)
async def batch_segment_search(
    project_id: int,
    body: BatchSegmentSearchRequest = BatchSegmentSearchRequest(),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run segment search across all (or selected) segment×geo combos from search_config.

    This replaces the need for standalone scripts. Runs in background with
    configurable concurrency. Progress visible via /search/jobs endpoint.
    """
    from app.services.search_config_service import search_config_service

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = await search_config_service.get_or_create_config(db, project_id)
    if not config or not config.get("segments"):
        raise HTTPException(status_code=400, detail="No search_config found. Configure segments first.")

    # Build combos list
    combos = []
    segments_data = config["segments"]
    for seg_key, seg in segments_data.items():
        if body.segments and seg_key not in body.segments:
            continue
        for geo_key in seg.get("geos", {}):
            if body.geos and geo_key not in body.geos:
                continue
            combos.append((seg_key, geo_key))

    if not combos:
        raise HTTPException(status_code=400, detail="No matching segment×geo combos found")

    engine = SearchEngine.GOOGLE_SERP if body.search_engine == "google_serp" else SearchEngine.YANDEX_API

    background_tasks.add_task(
        _run_batch_segments_background,
        project_id, company.id, combos, engine,
        body.ai_expand_rounds, body.max_concurrent,
    )

    return BatchSegmentSearchResponse(
        status="running",
        total_combos=len(combos),
        message=f"Launched {len(combos)} segment×geo searches ({body.search_engine}, concurrency={body.max_concurrent})",
    )


async def _run_batch_segments_background(
    project_id: int,
    company_id: int,
    combos: list,
    search_engine: SearchEngine,
    ai_expand_rounds: int,
    max_concurrent: int,
):
    """Background task: run segment searches with concurrency control."""
    sem = asyncio.Semaphore(max_concurrent)
    total = len(combos)
    completed = 0
    total_targets = 0
    total_queries = 0

    async def run_one(seg_key: str, geo_key: str, idx: int):
        nonlocal completed, total_targets, total_queries
        async with sem:
            logger.info(f"Batch segment [{idx+1}/{total}]: {seg_key}/{geo_key}")
            try:
                async with async_session_maker() as session:
                    stats = await company_search_service.run_segment_search(
                        session=session,
                        project_id=project_id,
                        company_id=company_id,
                        segment_key=seg_key,
                        geo_key=geo_key,
                        search_engine=search_engine,
                        ai_expand_rounds=ai_expand_rounds,
                    )
                completed += 1
                total_targets += stats.get("targets_found", 0)
                total_queries += stats.get("total_queries", 0)
                logger.info(
                    f"Batch segment [{idx+1}/{total}] done: {seg_key}/{geo_key} — "
                    f"{stats.get('targets_found', 0)} targets, {stats.get('total_queries', 0)} queries "
                    f"(running: {completed}/{total}, {total_targets} total targets)"
                )
            except Exception as e:
                completed += 1
                logger.error(f"Batch segment [{idx+1}/{total}] {seg_key}/{geo_key} failed: {e}")

    tasks = [run_one(seg, geo, i) for i, (seg, geo) in enumerate(combos)]
    await asyncio.gather(*tasks)

    logger.info(
        f"Batch segment search complete: {completed}/{total} combos, "
        f"{total_targets} targets, {total_queries} queries"
    )


@router.post("/projects/{project_id}/analyze-domains", response_model=AnalyzeDomainsResponse)
async def analyze_unprocessed_domains(
    project_id: int,
    body: AnalyzeDomainsRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Resume analysis of unprocessed domains from an existing search job.

    Useful when a previous search found domains but analysis was interrupted.
    Rebuilds skip set and analyzes any domains not yet in search_results.
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job_result = await db.execute(
        select(SearchJob).where(SearchJob.id == body.job_id, SearchJob.project_id == project_id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    # Count unanalyzed domains
    skip_set = await company_search_service._build_skip_set(db, project_id)
    new_domains = await company_search_service._get_new_domains_from_job(db, job, skip_set)

    if not new_domains:
        return AnalyzeDomainsResponse(
            status="complete", domains_to_analyze=0,
            message="No unanalyzed domains remaining",
        )

    background_tasks.add_task(
        _analyze_domains_background, job.id, project_id, new_domains, project.target_segments, body.batch_size,
    )

    return AnalyzeDomainsResponse(
        status="running",
        domains_to_analyze=len(new_domains),
        message=f"Analyzing {len(new_domains)} domains in batches of {body.batch_size}",
    )


async def _analyze_domains_background(
    job_id: int, project_id: int, domains: list, target_segments: str, batch_size: int,
):
    """Background: analyze domains in batches."""
    try:
        async with async_session_maker() as session:
            job_result = await session.execute(select(SearchJob).where(SearchJob.id == job_id))
            job = job_result.scalar_one()

            for i in range(0, len(domains), batch_size):
                batch = domains[i:i + batch_size]
                logger.info(f"Analyze batch {i//batch_size + 1}: {len(batch)} domains (job {job_id})")
                try:
                    await company_search_service._scrape_and_analyze_domains(
                        session=session, job=job, domains=batch,
                        target_segments=target_segments,
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"Batch analysis failed: {e}")
                    await session.rollback()

            logger.info(f"Domain analysis complete for job {job_id}: {len(domains)} domains processed")
    except Exception as e:
        logger.error(f"Background domain analysis crashed: {e}")


@router.get("/projects/{project_id}/results/stats")
async def get_project_results_stats(
    project_id: int,
    job_id: Optional[int] = QueryParam(None, description="Filter by job ID"),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Fast stats endpoint — total counts and avg confidence via aggregate queries."""
    # Verify project belongs to company
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    base_filter = [SearchResult.project_id == project_id]
    if job_id:
        base_filter.append(SearchResult.search_job_id == job_id)

    # Total count
    total_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult).where(*base_filter)
    )
    total = total_q.scalar() or 0

    # Targets count
    targets_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult).where(
            *base_filter, SearchResult.is_target == True
        )
    )
    targets = targets_q.scalar() or 0

    # Avg confidence of targets
    avg_q = await db.execute(
        select(sqlfunc.avg(SearchResult.confidence)).where(
            *base_filter, SearchResult.is_target == True
        )
    )
    avg_confidence = avg_q.scalar()

    return {
        "total": total,
        "targets": targets,
        "non_targets": total - targets,
        "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
    }


@router.get("/projects/{project_id}/pipeline-summary")
async def get_project_pipeline_summary(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Comprehensive project pipeline summary — real numbers from discovered_companies + extracted_contacts."""
    from sqlalchemy import text as sql_text
    from app.api.pipeline import _running_pipelines

    # Verify project
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    row = await db.execute(sql_text("""
        SELECT
            (SELECT COUNT(*) FROM discovered_companies WHERE project_id = :pid) as total_discovered,
            (SELECT COUNT(*) FROM discovered_companies WHERE project_id = :pid AND is_target = true) as total_targets,
            (SELECT COUNT(DISTINCT dc.domain) FROM discovered_companies dc WHERE dc.project_id = :pid AND dc.is_target = true) as target_domains,
            (SELECT COUNT(*) FROM extracted_contacts ec JOIN discovered_companies dc ON ec.discovered_company_id = dc.id WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL AND ec.email != '') as contacts_with_email,
            (SELECT COUNT(*) FROM extracted_contacts ec JOIN discovered_companies dc ON ec.discovered_company_id = dc.id WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL AND ec.email != '' AND lower(ec.email) NOT IN (SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL)) as new_emails,
            (SELECT COUNT(*) FROM discovered_companies WHERE project_id = :pid AND apollo_enriched_at IS NOT NULL) as apollo_enriched,
            (SELECT COALESCE(SUM(apollo_credits_used), 0) FROM discovered_companies WHERE project_id = :pid) as apollo_credits_used,
            (SELECT COUNT(*) FROM search_jobs WHERE project_id = :pid) as total_search_jobs,
            (SELECT COUNT(*) FROM search_queries WHERE search_job_id IN (SELECT id FROM search_jobs WHERE project_id = :pid)) as total_queries,
            (SELECT COUNT(*) FROM extracted_contacts ec JOIN discovered_companies dc ON ec.discovered_company_id = dc.id WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL AND ec.email != '' AND lower(ec.email) IN (SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL)) as in_smartlead
    """), {"pid": project_id, "cid": company.id})
    stats = row.fetchone()

    # Pipeline status
    pipeline_status = None
    if project_id in _running_pipelines:
        p = _running_pipelines[project_id]
        pipeline_status = {
            "running": p.get("running", False),
            "phase": p.get("phase"),
            "started_at": p.get("started_at"),
            "target_goal": p.get("config", {}).get("target_goal"),
        }

    # Spending summary
    spending = None
    try:
        from app.services.company_search_service import company_search_service
        raw = await company_search_service.get_project_spending(db, project_id)
        spending = {
            "yandex_cost": raw.get("yandex_cost", 0),
            "google_cost": raw.get("google_cost", 0),
            "crona_cost": raw.get("crona_cost", 0),
            "ai_cost": raw.get("ai_cost_estimate", 0),
            "apollo_cost": round(stats[6] * 0.01, 2),
            "total": round(raw.get("total_estimate", 0) + stats[6] * 0.01, 2),
        }
    except Exception as e:
        logger.warning(f"Failed to get spending for pipeline summary: {e}")

    # Per-segment stats breakdown
    segment_stats = {}
    try:
        seg_rows = await db.execute(sql_text("""
            SELECT
                sr.matched_segment,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE sr.is_target = true) as targets,
                COUNT(DISTINCT sr.domain) as domains
            FROM search_results sr
            WHERE sr.project_id = :pid AND sr.matched_segment IS NOT NULL
            GROUP BY sr.matched_segment
            ORDER BY targets DESC
        """), {"pid": project_id})
        for seg_row in seg_rows.fetchall():
            segment_stats[seg_row[0]] = {
                "total_analyzed": seg_row[1],
                "targets": seg_row[2],
                "domains": seg_row[3],
            }

        # Also get query counts per segment
        q_seg_rows = await db.execute(sql_text("""
            SELECT
                sq.segment,
                COUNT(*) as query_count
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid AND sq.segment IS NOT NULL
            GROUP BY sq.segment
        """), {"pid": project_id})
        for q_row in q_seg_rows.fetchall():
            seg_name = q_row[0]
            if seg_name not in segment_stats:
                segment_stats[seg_name] = {"total_analyzed": 0, "targets": 0, "domains": 0}
            segment_stats[seg_name]["queries"] = q_row[1]
    except Exception as e:
        logger.warning(f"Failed to get segment stats: {e}")

    return {
        "project_id": project_id,
        "total_discovered": stats[0],
        "total_targets": stats[1],
        "target_domains": stats[2],
        "contacts_with_email": stats[3],
        "new_emails_not_in_campaigns": stats[4],
        "in_smartlead": stats[9],
        "apollo_enriched": stats[5],
        "apollo_credits_used": stats[6],
        "total_search_jobs": stats[7],
        "total_queries": stats[8],
        "spending": spending,
        "pipeline": pipeline_status,
        "segment_stats": segment_stats,
    }


@router.get("/projects/{project_id}/knowledge")
async def get_project_knowledge(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Project knowledge base — target segments, per-segment stats, top domains, contacts breakdown."""
    from sqlalchemy import text as sql_text

    # Verify project
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse target_segments
    target_segments = []
    if project.target_segments:
        try:
            target_segments = json.loads(project.target_segments) if isinstance(project.target_segments, str) else project.target_segments
        except Exception:
            target_segments = [s.strip() for s in project.target_segments.split(",") if s.strip()]

    # Overall totals
    totals_row = await db.execute(sql_text("""
        SELECT
            COUNT(*) as total_discovered,
            COUNT(*) FILTER (WHERE is_target = true) as total_targets,
            COUNT(DISTINCT domain) FILTER (WHERE is_target = true) as target_domains
        FROM discovered_companies
        WHERE project_id = :pid
    """), {"pid": project_id})
    totals = totals_row.fetchone()

    # Per-segment breakdown from search_results
    seg_rows = await db.execute(sql_text("""
        SELECT
            COALESCE(sr.matched_segment, 'unclassified') as segment,
            COUNT(*) as total_analyzed,
            COUNT(*) FILTER (WHERE sr.is_target = true) as targets,
            COUNT(DISTINCT sr.domain) as domains,
            COUNT(DISTINCT sr.domain) FILTER (WHERE sr.is_target = true) as target_domains
        FROM search_results sr
        WHERE sr.project_id = :pid
        GROUP BY COALESCE(sr.matched_segment, 'unclassified')
        ORDER BY targets DESC
    """), {"pid": project_id})
    segments = {}
    for r in seg_rows.fetchall():
        segments[r[0]] = {
            "total_analyzed": r[1],
            "targets": r[2],
            "domains": r[3],
            "target_domains": r[4],
            "contacts_with_email": 0,
            "contacts_total": 0,
            "top_domains": [],
        }

    # Contacts per segment (via discovered_companies -> search_result -> matched_segment)
    contact_rows = await db.execute(sql_text("""
        SELECT
            COALESCE(sr.matched_segment, 'unclassified') as segment,
            COUNT(ec.id) as contacts_total,
            COUNT(ec.id) FILTER (WHERE ec.email IS NOT NULL AND ec.email != '') as contacts_with_email
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        JOIN search_results sr ON dc.search_result_id = sr.id
        WHERE dc.project_id = :pid AND dc.is_target = true
        GROUP BY COALESCE(sr.matched_segment, 'unclassified')
    """), {"pid": project_id})
    for r in contact_rows.fetchall():
        seg_key = r[0]
        if seg_key in segments:
            segments[seg_key]["contacts_total"] = r[1]
            segments[seg_key]["contacts_with_email"] = r[2]

    # Top target domains per segment (limit 10 per segment)
    top_rows = await db.execute(sql_text("""
        SELECT
            COALESCE(sr.matched_segment, 'unclassified') as segment,
            sr.domain,
            sr.company_info->>'name' as company_name,
            sr.confidence,
            (SELECT COUNT(*) FROM extracted_contacts ec2 JOIN discovered_companies dc2 ON ec2.discovered_company_id = dc2.id WHERE dc2.domain = sr.domain AND dc2.project_id = :pid AND ec2.email IS NOT NULL AND ec2.email != '') as emails
        FROM search_results sr
        WHERE sr.project_id = :pid AND sr.is_target = true
        ORDER BY sr.confidence DESC NULLS LAST
    """), {"pid": project_id})
    for r in top_rows.fetchall():
        seg_key = r[0]
        if seg_key in segments and len(segments[seg_key]["top_domains"]) < 10:
            segments[seg_key]["top_domains"].append({
                "domain": r[1],
                "name": r[2],
                "confidence": round(r[3], 2) if r[3] else None,
                "emails": r[4],
            })

    # Query counts per segment
    q_rows = await db.execute(sql_text("""
        SELECT sq.segment, COUNT(*) as cnt
        FROM search_queries sq
        JOIN search_jobs sj ON sq.search_job_id = sj.id
        WHERE sj.project_id = :pid AND sq.segment IS NOT NULL
        GROUP BY sq.segment
    """), {"pid": project_id})
    for r in q_rows.fetchall():
        seg_key = r[0]
        if seg_key in segments:
            segments[seg_key]["queries"] = r[1]
        else:
            segments[seg_key] = {
                "total_analyzed": 0, "targets": 0, "domains": 0, "target_domains": 0,
                "contacts_with_email": 0, "contacts_total": 0, "top_domains": [], "queries": r[1],
            }

    # Overall contacts total
    ec_totals = await db.execute(sql_text("""
        SELECT
            COUNT(ec.id) as total,
            COUNT(ec.id) FILTER (WHERE ec.email IS NOT NULL AND ec.email != '') as with_email
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        WHERE dc.project_id = :pid AND dc.is_target = true
    """), {"pid": project_id})
    ec_row = ec_totals.fetchone()

    return {
        "project_id": project_id,
        "project_name": project.name,
        "target_segments": target_segments,
        "totals": {
            "discovered": totals[0],
            "targets": totals[1],
            "target_domains": totals[2],
            "contacts_total": ec_row[0] if ec_row else 0,
            "contacts_with_email": ec_row[1] if ec_row else 0,
        },
        "segments": segments,
    }


@router.get("/projects/{project_id}/results")
async def get_project_results(
    project_id: int,
    targets_only: bool = QueryParam(False, description="Show only targets"),
    job_id: Optional[int] = QueryParam(None, description="Filter by job ID"),
    segment: Optional[str] = QueryParam(None, description="Filter by matched_segment"),
    page: int = QueryParam(1, ge=1, description="Page number"),
    page_size: int = QueryParam(100, ge=1, le=500, description="Results per page"),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get analyzed search results for a project (paginated). Supports segment filter."""
    # Verify project belongs to company
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    base_filter = [SearchResult.project_id == project_id]
    if job_id:
        base_filter.append(SearchResult.search_job_id == job_id)
    if targets_only:
        base_filter.append(SearchResult.is_target == True)
    if segment:
        base_filter.append(SearchResult.matched_segment == segment)

    # Total count
    count_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult).where(*base_filter)
    )
    total = count_q.scalar() or 0

    # Fetch page
    query = (
        select(SearchResult)
        .where(*base_filter)
        .order_by(SearchResult.is_target.desc(), SearchResult.confidence.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    results = result.scalars().all()

    # Build source query text + segment map
    qids = [r.source_query_id for r in results if r.source_query_id]
    qmap: dict[int, tuple[str, str | None]] = {}  # id -> (query_text, segment)
    if qids:
        qrows = (await db.execute(
            select(SearchQuery.id, SearchQuery.query_text, SearchQuery.segment).where(SearchQuery.id.in_(qids))
        )).fetchall()
        qmap = {row[0]: (row[1], row[2]) for row in qrows}

    items = []
    for r in results:
        resp = SearchResultResponse.model_validate(r)
        if r.source_query_id and r.source_query_id in qmap:
            resp.source_query_text = qmap[r.source_query_id][0]
            resp.source_query_segment = qmap[r.source_query_id][1]
        items.append(resp)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/projects/{project_id}/spending", response_model=SpendingInfo)
async def get_project_spending(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get cost tracking for a project's search jobs."""
    # Verify project belongs to company
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    spending = await company_search_service.get_project_spending(db, project_id)
    return SpendingInfo(**spending)


# ============ Review Endpoints ============

@router.post("/results/{result_id}/review")
async def review_result(
    result_id: int,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Human confirms/rejects a single search result."""
    from app.services.review_service import review_service

    if body.verdict not in ("confirmed", "rejected", "flagged"):
        raise HTTPException(status_code=400, detail="verdict must be: confirmed, rejected, or flagged")

    # Verify result belongs to company's job
    result = await db.execute(
        select(SearchResult).where(SearchResult.id == result_id)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=404, detail="Search result not found")

    job_result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == sr.search_job_id,
            SearchJob.company_id == company.id,
        )
    )
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Search result not found")

    sr = await review_service.manual_review(db, result_id, body.verdict, body.note)
    await db.commit()

    return {
        "id": sr.id,
        "review_status": sr.review_status,
        "review_note": sr.review_note,
        "is_target": sr.is_target,
        "confidence": sr.confidence,
    }


@router.get("/jobs/{job_id}/review-summary")
async def get_review_summary(
    job_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get review statistics for a search job."""
    from app.services.review_service import review_service

    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Search job not found")

    summary = await review_service.get_review_summary(db, job_id)
    return summary


# ============ Google Sheet Export ============

class ExportSheetRequest(BaseModel):
    targets_only: bool = Field(False, description="Export only target domains")
    exclude_contacted: bool = Field(False, description="Exclude domains already in campaigns")


@router.post("/projects/{project_id}/export-sheet", response_model=ExportSheetResponse)
async def export_to_google_sheet(
    project_id: int,
    body: ExportSheetRequest = ExportSheetRequest(),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export search results to a new Google Sheet."""
    from app.services.google_sheets_service import google_sheets_service as sheets_service
    from sqlalchemy import func as sqlfunc

    if not sheets_service._initialize():
        raise HTTPException(status_code=503, detail="Google Sheets not configured")

    # Verify project
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get results
    results = await company_search_service.get_project_results(
        db, project_id, targets_only=body.targets_only,
    )
    if not results:
        raise HTTPException(status_code=400, detail="No search results to export")

    # Filter out contacted domains if requested
    if body.exclude_contacted:
        result_domains = [r.domain.lower() for r in results if r.domain]
        contacted_result = await db.execute(
            select(sqlfunc.lower(Contact.domain)).where(
                Contact.company_id == company.id,
                Contact.domain.isnot(None),
                sqlfunc.lower(Contact.domain).in_(result_domains),
            ).distinct()
        )
        contacted_domains = {row[0] for row in contacted_result.fetchall()}
        results = [r for r in results if r.domain and r.domain.lower() not in contacted_domains]

    if not results:
        raise HTTPException(status_code=400, detail="No results after filtering (all domains already contacted)")

    # Build title
    label_parts = []
    if body.targets_only:
        label_parts.append("Targets")
    else:
        label_parts.append("Results")
    if body.exclude_contacted:
        label_parts.append("Fresh")
    sheet_title = f"{' '.join(label_parts)} - {project.name} ({len(results)}) - {datetime.utcnow().strftime('%Y-%m-%d')}"

    # Build source query map
    query_ids = [r.source_query_id for r in results if r.source_query_id]
    query_map: dict[int, str] = {}
    if query_ids:
        from sqlalchemy import func as sqlfunc2
        qrows = (await db.execute(
            select(SearchQuery.id, SearchQuery.query_text).where(
                SearchQuery.id.in_(query_ids)
            )
        )).fetchall()
        query_map = {row[0]: row[1] for row in qrows}

    # Create Google Sheet
    try:
        headers = ["Domain", "Website", "Company", "Confidence", "Industry",
                    "Services", "Location", "Description", "Source Query", "Reasoning"]
        rows = [headers]

        project_name_lower = (project.name or "").lower()
        for r in results:
            info = r.company_info or {}
            services = ", ".join(info.get("services", [])) if isinstance(info.get("services"), list) else info.get("services", "")
            desc = info.get("description", "") or ""
            company_name = info.get("name", info.get("company_name", ""))
            # Fix: don't use project name as company name
            if company_name and company_name.lower() == project_name_lower:
                company_name = ""
            source_query = query_map.get(r.source_query_id, "") if r.source_query_id else ""
            rows.append([
                r.domain,
                f"https://{r.domain}",
                company_name,
                f"{(r.confidence or 0) * 100:.0f}%",
                info.get("industry", ""),
                services,
                info.get("location", ""),
                desc[:200],
                source_query,
                (r.reasoning or "")[:300],
            ])

        sheet_url = sheets_service.create_and_populate(
            title=sheet_title,
            data=rows,
            share_with=["pn@getsally.io", "pavel.l@getsally.io"],
        )

        if not sheet_url:
            raise HTTPException(status_code=500, detail="Failed to create Google Sheet")

        return ExportSheetResponse(sheet_url=sheet_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Sheet export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============ Search History & Extended Detail ============

@router.get("/history")
async def get_search_history(
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(20, ge=1, le=100),
    project_id: Optional[int] = QueryParam(None, description="Filter by project"),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List all past search jobs with summary stats (paginated)."""
    from sqlalchemy import func as sqlfunc

    filters = [SearchJob.company_id == company.id]
    if project_id is not None:
        filters.append(SearchJob.project_id == project_id)

    # Count total
    count_result = await db.execute(
        select(sqlfunc.count()).select_from(SearchJob).where(*filters)
    )
    total = count_result.scalar() or 0

    # Fetch jobs
    result = await db.execute(
        select(SearchJob)
        .where(*filters)
        .order_by(desc(SearchJob.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = result.scalars().all()

    # For each job, get results summary
    items = []
    for job in jobs:
        # Count results
        results_count = await db.execute(
            select(sqlfunc.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job.id,
            )
        )
        total_results = results_count.scalar() or 0

        targets_count = await db.execute(
            select(sqlfunc.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        total_targets = targets_count.scalar() or 0

        # Get project name
        project_name = None
        if job.project_id:
            p_result = await db.execute(
                select(Project.name).where(Project.id == job.project_id)
            )
            row = p_result.first()
            if row:
                project_name = row[0]

        config = job.config or {}
        ai_tokens = config.get("openai_tokens_used", 0) + config.get("query_gen_tokens", 0)
        crona_credits = config.get("crona_credits_used", 0)
        analysis_model = config.get("analysis_model", "gpt-4o-mini")

        # Estimate cost per job
        queries = job.queries_total or 0
        engine_str = str(job.search_engine.value if hasattr(job.search_engine, 'value') else job.search_engine)
        if engine_str == "yandex_api":
            search_cost = round(queries * 0.25 / 1000, 3)
        elif engine_str == "google_serp":
            search_cost = round(queries * 3.50 / 1000, 3)
        else:
            search_cost = 0
        ai_cost = round(ai_tokens * 0.15 / 1_000_000, 3) if ai_tokens else 0
        crona_cost = round(crona_credits * 0.005, 3) if crona_credits else 0

        items.append({
            "id": job.id,
            "company_id": job.company_id,
            "status": str(job.status.value if hasattr(job.status, 'value') else job.status),
            "search_engine": engine_str,
            "project_id": job.project_id,
            "project_name": project_name,
            "queries_total": queries,
            "queries_completed": job.queries_completed or 0,
            "domains_found": job.domains_found or 0,
            "domains_new": job.domains_new or 0,
            "domains_trash": job.domains_trash or 0,
            "domains_duplicate": job.domains_duplicate or 0,
            "results_total": total_results,
            "targets_found": total_targets,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "error_message": job.error_message,
            "ai_tokens_used": ai_tokens,
            "analysis_model": analysis_model,
            "crona_credits_used": crona_credits,
            # Cost estimates
            "search_cost": search_cost,
            "ai_cost": ai_cost,
            "crona_cost": crona_cost,
            "total_cost": round(search_cost + ai_cost + crona_cost, 3),
            # Segment info (from config)
            "segment": config.get("segment"),
            "geo": config.get("geo"),
            "query_source": config.get("query_source"),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/jobs/{job_id}/full")
async def get_search_job_full(
    job_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get extended job detail with config, results summary, spending."""
    from sqlalchemy import func as sqlfunc

    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    # Results summary
    results_count = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult).where(
            SearchResult.search_job_id == job.id,
        )
    )
    total_results = results_count.scalar() or 0

    targets_count = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult).where(
            SearchResult.search_job_id == job.id,
            SearchResult.is_target == True,
        )
    )
    total_targets = targets_count.scalar() or 0

    avg_conf = await db.execute(
        select(sqlfunc.avg(SearchResult.confidence)).where(
            SearchResult.search_job_id == job.id,
            SearchResult.is_target == True,
        )
    )
    avg_confidence = avg_conf.scalar()

    # Project name
    project_name = None
    if job.project_id:
        p_result = await db.execute(
            select(Project.name).where(Project.id == job.project_id)
        )
        row = p_result.first()
        if row:
            project_name = row[0]

    # Spending — split Gemini vs OpenAI
    config = job.config or {}
    analysis_tokens = config.get("openai_tokens_used", 0)
    query_gen_tokens = config.get("query_gen_tokens", 0)
    review_tokens = config.get("review_tokens", 0)
    crona_credits = config.get("crona_credits_used", 0)
    analysis_model = config.get("analysis_model", "gpt-4o-mini")
    query_gen_model = config.get("query_gen_model", "gpt-4o-mini")

    yandex_requests = (job.queries_total or 0) * 3
    yandex_cost = (yandex_requests / 1000) * 0.25

    # Split tokens by model
    openai_tokens = review_tokens
    gemini_tokens = 0
    if "gemini" in analysis_model:
        gemini_tokens += max(0, analysis_tokens - review_tokens)
    else:
        openai_tokens += max(0, analysis_tokens - review_tokens)
    if "gemini" in query_gen_model:
        gemini_tokens += query_gen_tokens
    else:
        openai_tokens += query_gen_tokens

    openai_cost = (openai_tokens / 1_000_000) * 0.15
    gemini_cost = (gemini_tokens / 1_000_000) * 2.50
    crona_cost = crona_credits * 0.001
    ai_cost = openai_cost + gemini_cost

    return {
        "id": job.id,
        "company_id": job.company_id,
        "status": str(job.status.value if hasattr(job.status, 'value') else job.status),
        "search_engine": str(job.search_engine.value if hasattr(job.search_engine, 'value') else job.search_engine),
        "project_id": job.project_id,
        "project_name": project_name,
        "queries_total": job.queries_total or 0,
        "queries_completed": job.queries_completed or 0,
        "domains_found": job.domains_found or 0,
        "domains_new": job.domains_new or 0,
        "domains_trash": job.domains_trash or 0,
        "domains_duplicate": job.domains_duplicate or 0,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "error_message": job.error_message,
        "config": config,
        "results_total": total_results,
        "targets_found": total_targets,
        "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
        "analysis_model": analysis_model,
        "query_gen_model": query_gen_model,
        "yandex_cost": round(yandex_cost, 4),
        "openai_tokens_used": openai_tokens,
        "openai_cost_estimate": round(openai_cost, 4),
        "gemini_tokens_used": gemini_tokens,
        "gemini_cost_estimate": round(gemini_cost, 4),
        "ai_cost_estimate": round(ai_cost, 4),
        "crona_credits_used": crona_credits,
        "crona_cost": round(crona_cost, 4),
        "total_cost_estimate": round(yandex_cost + ai_cost + crona_cost, 4),
    }


@router.get("/jobs/{job_id}/results")
async def get_job_results(
    job_id: int,
    targets_only: bool = QueryParam(False),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get all results for a job with source query text."""
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Search job not found")

    query = select(SearchResult).where(SearchResult.search_job_id == job_id)
    if targets_only:
        query = query.where(SearchResult.is_target == True)
    query = query.order_by(SearchResult.is_target.desc(), SearchResult.confidence.desc())

    results_q = await db.execute(query)
    results = results_q.scalars().all()

    # Build query_id -> query_text map for source tracking
    q_result = await db.execute(
        select(SearchQuery.id, SearchQuery.query_text).where(
            SearchQuery.search_job_id == job_id
        )
    )
    query_map = {row[0]: row[1] for row in q_result.fetchall()}

    items = []
    for r in results:
        info = r.company_info or {}
        items.append({
            "id": r.id,
            "domain": r.domain,
            "url": r.url,
            "is_target": r.is_target,
            "confidence": r.confidence,
            "reasoning": r.reasoning,
            "company_info": info,
            "scores": r.scores,
            "review_status": r.review_status,
            "review_note": r.review_note,
            "source_query_id": r.source_query_id,
            "source_query_text": query_map.get(r.source_query_id) if r.source_query_id else None,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
        })

    return {"items": items, "total": len(items)}


@router.get("/jobs/{job_id}/results/download")
async def download_job_results_csv(
    job_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Download job results as CSV."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    results_q = await db.execute(
        select(SearchResult).where(SearchResult.search_job_id == job_id)
        .order_by(SearchResult.is_target.desc(), SearchResult.confidence.desc())
    )
    results = results_q.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Domain", "URL", "Company Name", "Is Target", "Confidence",
        "Reasoning", "Services", "Location", "Industry",
        "Scraped At", "Analyzed At",
    ])

    for r in results:
        info = r.company_info or {}
        services = ", ".join(info.get("services", [])) if info.get("services") else ""
        writer.writerow([
            r.domain,
            r.url or "",
            info.get("name", ""),
            "Yes" if r.is_target else "No",
            f"{(r.confidence or 0) * 100:.0f}%",
            r.reasoning or "",
            services,
            info.get("location", ""),
            info.get("industry", ""),
            r.scraped_at.isoformat() if r.scraped_at else "",
            r.analyzed_at.isoformat() if r.analyzed_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=search_job_{job_id}_results.csv"},
    )


# ============ Domain-Campaign Lookup ============

class DomainCampaignsRequest(BaseModel):
    domains: List[str] = Field(..., min_length=1, max_length=500, description="List of domains to look up")


@router.post("/domain-campaigns")
async def get_domain_campaigns(
    body: DomainCampaignsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Batch lookup: for a list of domains, find contacts with campaign data.
    Matches by TWO methods:
    1. Email domain match: contact.domain (from email) == search result domain
    2. Website domain match: contact.company_name contains the domain root
    Returns campaign info grouped by domain with match_type indicator.
    """
    from sqlalchemy import func as sqlfunc, or_

    # Normalize domains
    domains = [d.lower().strip() for d in body.domains if d and d.strip()]
    if not domains:
        return {}

    # --- Match 1: Email domain (contact.domain == search domain) ---
    result = await db.execute(
        select(Contact).where(
            Contact.company_id == company.id,
            Contact.domain.in_(domains),
            Contact.is_deleted == False,
        )
    )
    email_contacts = result.scalars().all()

    # Build email domain match map
    email_matched: dict[str, list] = {}
    for c in email_contacts:
        d = c.domain.lower() if c.domain else None
        if d:
            email_matched.setdefault(d, []).append(c)

    # --- Match 2: Website domain (extract root from domain, check company_name) ---
    # e.g., domain "alfacapital.ru" → root "alfacapital" → search in company_name
    website_matched: dict[str, list] = {}
    domain_roots = {}
    for d in domains:
        parts = d.split(".")
        if len(parts) >= 2:
            root = parts[0] if len(parts[0]) > 3 else ".".join(parts[:2])
            domain_roots[d] = root

    # Only search for domains NOT already matched by email
    unmatched_domains = [d for d in domains if d not in email_matched and d in domain_roots]
    if unmatched_domains:
        # Build OR conditions for company_name ILIKE '%root%'
        from sqlalchemy import or_ as sql_or
        conditions = []
        for d in unmatched_domains:
            root = domain_roots[d]
            if len(root) >= 4:  # avoid too-short matches
                conditions.append(
                    sqlfunc.lower(Contact.company_name).contains(root.lower())
                )

        if conditions:
            result2 = await db.execute(
                select(Contact).where(
                    Contact.company_id == company.id,
                    Contact.is_deleted == False,
                    sql_or(*conditions),
                )
            )
            website_contacts = result2.scalars().all()

            for c in website_contacts:
                cn = (c.company_name or "").lower()
                for d in unmatched_domains:
                    root = domain_roots.get(d, "")
                    if len(root) >= 4 and root.lower() in cn:
                        website_matched.setdefault(d, []).append(c)

    # --- Combine results ---
    domain_map: dict = {}

    def add_contacts_to_map(d: str, contacts: list, match_type: str):
        if d not in domain_map:
            domain_map[d] = {
                "contacts_count": 0,
                "has_replies": False,
                "first_contacted_at": None,
                "campaigns": [],
                "contacts": [],
                "match_type": match_type,
            }

        entry = domain_map[d]
        seen_ids = {ct["id"] for ct in entry["contacts"]}

        for c in contacts:
            if c.id in seen_ids:
                continue
            entry["contacts_count"] += 1
            if c.has_replied:
                entry["has_replies"] = True

            if c.created_at:
                created_str = c.created_at.isoformat()
                if entry["first_contacted_at"] is None or created_str < entry["first_contacted_at"]:
                    entry["first_contacted_at"] = created_str

            if c.campaigns:
                seen_campaigns = {(cp.get("name"), cp.get("source")) for cp in entry["campaigns"]}
                for cp in parse_campaigns(c.campaigns):
                    key = (cp.get("name"), cp.get("source"))
                    if key not in seen_campaigns:
                        entry["campaigns"].append({
                            "name": cp.get("name"),
                            "source": cp.get("source"),
                            "status": cp.get("status"),
                        })
                        seen_campaigns.add(key)

            name_parts = [c.first_name or "", c.last_name or ""]
            name = " ".join(p for p in name_parts if p).strip() or None
            entry["contacts"].append({
                "id": c.id,
                "name": name,
                "email": c.email if c.email and "@placeholder" not in c.email else None,
                "status": c.status,
                "has_replied": c.has_replied or False,
                "match_type": match_type,
            })
            seen_ids.add(c.id)

    for d, contacts in email_matched.items():
        add_contacts_to_map(d, contacts, "email_domain")
    for d, contacts in website_matched.items():
        add_contacts_to_map(d, contacts, "website_domain")

    return domain_map
