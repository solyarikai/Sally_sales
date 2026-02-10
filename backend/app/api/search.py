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
from sqlalchemy import select, desc
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
    company: Company = Depends(get_required_company),
):
    """Server-Sent Events for real-time job progress."""
    # Verify access
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == job_id,
            SearchJob.company_id == company.id,
        )
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

                # Count results
                results_count = 0
                if current_job.project_id:
                    r = await session.execute(
                        select(SearchResult).where(
                            SearchResult.search_job_id == job_id,
                        )
                    )
                    results_count = len(r.scalars().all())

                data = {
                    "phase": phase,
                    "status": str(current_job.status.value if hasattr(current_job.status, 'value') else current_job.status),
                    "current": current_job.queries_completed or 0,
                    "total": current_job.queries_total or 0,
                    "domains_found": current_job.domains_found or 0,
                    "domains_new": current_job.domains_new or 0,
                    "results_analyzed": results_count,
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


@router.get("/projects/{project_id}/results", response_model=List[SearchResultResponse])
async def get_project_results(
    project_id: int,
    targets_only: bool = QueryParam(False, description="Show only targets"),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get analyzed search results for a project."""
    # Verify project belongs to company
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(SearchResult).where(SearchResult.project_id == project_id)
    if targets_only:
        query = query.where(SearchResult.is_target == True)

    query = query.order_by(
        SearchResult.is_target.desc(),
        SearchResult.confidence.desc(),
    )

    result = await db.execute(query)
    results = result.scalars().all()
    return [SearchResultResponse.model_validate(r) for r in results]


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

@router.post("/projects/{project_id}/export-sheet", response_model=ExportSheetResponse)
async def export_to_google_sheet(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export search results to a new Google Sheet."""
    from app.services.google_sheets_service import google_sheets_service as sheets_service

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
    results = await company_search_service.get_project_results(db, project_id)
    if not results:
        raise HTTPException(status_code=400, detail="No search results to export")

    # Create Google Sheet
    try:
        sheet_title = f"Search Results - {project.name} - {datetime.utcnow().strftime('%Y-%m-%d')}"

        spreadsheet = sheets_service.sheets_service.spreadsheets().create(
            body={
                "properties": {"title": sheet_title},
                "sheets": [{"properties": {"title": "Results"}}],
            }
        ).execute()

        spreadsheet_id = spreadsheet["spreadsheetId"]
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        # Make sheet accessible
        sheets_service.drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        # Write headers
        headers = ["Domain", "Company", "Is Target", "Confidence", "Reasoning", "Services", "Location", "Industry"]
        rows = [headers]

        for r in results:
            info = r.company_info or {}
            services = ", ".join(info.get("services", [])) if info.get("services") else ""
            rows.append([
                r.domain,
                info.get("name", ""),
                "Yes" if r.is_target else "No",
                f"{(r.confidence or 0) * 100:.0f}%",
                r.reasoning or "",
                services,
                info.get("location", ""),
                info.get("industry", ""),
            ])

        sheets_service.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Results!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        return ExportSheetResponse(sheet_url=sheet_url)

    except Exception as e:
        logger.error(f"Google Sheet export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============ Search History & Extended Detail ============

@router.get("/history")
async def get_search_history(
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List all past search jobs with summary stats (paginated)."""
    from sqlalchemy import func as sqlfunc

    # Count total
    count_result = await db.execute(
        select(sqlfunc.count()).select_from(SearchJob).where(
            SearchJob.company_id == company.id,
        )
    )
    total = count_result.scalar() or 0

    # Fetch jobs
    result = await db.execute(
        select(SearchJob)
        .where(SearchJob.company_id == company.id)
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
        tokens_used = config.get("openai_tokens_used", 0) + config.get("query_gen_tokens", 0)
        crona_credits = config.get("crona_credits_used", 0)

        items.append({
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
            "results_total": total_results,
            "targets_found": total_targets,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "error_message": job.error_message,
            "openai_tokens_used": tokens_used,
            "crona_credits_used": crona_credits,
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

    # Spending
    config = job.config or {}
    tokens_used = config.get("openai_tokens_used", 0)
    query_gen_tokens = config.get("query_gen_tokens", 0)
    all_tokens = tokens_used + query_gen_tokens
    crona_credits = config.get("crona_credits_used", 0)
    yandex_requests = (job.queries_total or 0) * 3  # 3 pages per query
    yandex_cost = (yandex_requests / 1000) * 0.25
    openai_cost = (all_tokens / 1_000_000) * 0.15
    crona_cost = crona_credits * 0.001

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
        "yandex_cost": round(yandex_cost, 4),
        "openai_tokens_used": all_tokens,
        "openai_cost_estimate": round(openai_cost, 4),
        "crona_credits_used": crona_credits,
        "crona_cost": round(crona_cost, 4),
        "total_cost_estimate": round(yandex_cost + openai_cost + crona_cost, 4),
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
    Returns campaign info grouped by domain for domains that have matches.
    """
    from sqlalchemy import func as sqlfunc, or_

    # Normalize domains
    domains = [d.lower().strip() for d in body.domains if d and d.strip()]
    if not domains:
        return {}

    # Query contacts with matching domains that have campaign data
    result = await db.execute(
        select(Contact).where(
            Contact.company_id == company.id,
            Contact.domain.in_(domains),
            Contact.is_deleted == False,
        )
    )
    contacts = result.scalars().all()

    # Group by domain
    domain_map: dict = {}
    for c in contacts:
        d = c.domain.lower() if c.domain else None
        if not d:
            continue

        if d not in domain_map:
            domain_map[d] = {
                "contacts_count": 0,
                "has_replies": False,
                "first_contacted_at": None,
                "campaigns": [],
                "contacts": [],
            }

        entry = domain_map[d]
        entry["contacts_count"] += 1

        if c.has_replied:
            entry["has_replies"] = True

        # Track first contact date
        if c.created_at:
            created_str = c.created_at.isoformat()
            if entry["first_contacted_at"] is None or created_str < entry["first_contacted_at"]:
                entry["first_contacted_at"] = created_str

        # Add campaigns (deduplicate)
        if c.campaigns:
            seen_campaigns = {(cp.get("name"), cp.get("source")) for cp in entry["campaigns"]}
            for cp in c.campaigns:
                key = (cp.get("name"), cp.get("source"))
                if key not in seen_campaigns:
                    entry["campaigns"].append({
                        "name": cp.get("name"),
                        "source": cp.get("source"),
                        "status": cp.get("status"),
                    })
                    seen_campaigns.add(key)

        # Add contact summary
        name_parts = [c.first_name or "", c.last_name or ""]
        name = " ".join(p for p in name_parts if p).strip() or None

        entry["contacts"].append({
            "id": c.id,
            "name": name,
            "email": c.email if c.email and "@placeholder" not in c.email else None,
            "status": c.status,
            "has_replied": c.has_replied or False,
        })

    return domain_map
