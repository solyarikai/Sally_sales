"""
Lookalike / TAM API — Cluster qualified leads, generate search strategies,
execute lookalike search across Apollo/Yandex/Google.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.db import get_session, async_session_maker
from app.api.companies import get_required_company
from app.models.user import Company
from app.models.contact import Project
from app.models.lookalike import (
    LookalikeCluster, ClusterMember, LookalikeRun,
    LookalikeRunStatus, LookalikePhase,
)
from app.models.domain import SearchResult
from app.services.lookalike_service import lookalike_service
from app.services.project_knowledge_service import project_knowledge_service

router = APIRouter(prefix="/lookalike", tags=["lookalike"])
logger = logging.getLogger(__name__)


# ============ Request/Response schemas ============

class AnalyzeRequest(BaseModel):
    offers: Optional[List[dict]] = Field(None, description="Override offers (otherwise loaded from ProjectKnowledge)")


class RunSearchRequest(BaseModel):
    budget_apollo_credits: int = Field(500, ge=0, le=5000)
    budget_yandex_queries: int = Field(200, ge=0, le=2000)
    budget_google_queries: int = Field(50, ge=0, le=500)


class UpdateClusterRequest(BaseModel):
    name: Optional[str] = None
    business_model: Optional[str] = None
    offer_fit: Optional[List[str]] = None
    search_strategy: Optional[dict] = None
    is_active: Optional[bool] = None


# ============ Endpoints ============

@router.post("/projects/{project_id}/analyze")
async def analyze_project(
    project_id: int,
    req: AnalyzeRequest = AnalyzeRequest(),
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Trigger Phase 1+2: analyze qualified leads and cluster them."""
    # Load project
    result = await db.execute(select(Project).where(
        Project.id == project_id, Project.company_id == company.id
    ))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    # Load offers from request or ProjectKnowledge
    offers = req.offers
    if not offers:
        offers = await _load_offers(db, project_id)
    if not offers:
        raise HTTPException(400, "No offers configured. Set them in ProjectKnowledge (category=tam, key=offers) or pass in request body.")

    # Delete existing clusters for this project (re-analysis)
    existing = await db.execute(
        select(LookalikeCluster).where(LookalikeCluster.project_id == project_id)
    )
    for c in existing.scalars().all():
        await db.delete(c)
    await db.commit()

    # Phase 1: Analyze + Cluster
    clusters = await lookalike_service.analyze_and_cluster(
        db, project_id, company.id, offers
    )

    # Phase 2: Generate strategy for each cluster
    for cluster in clusters:
        await lookalike_service.generate_cluster_strategy(db, cluster.id)

    # Reload with strategies
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.project_id == project_id,
            LookalikeCluster.is_active == True,
        )
    )
    clusters = list(result.scalars().all())

    return {
        "status": "ok",
        "clusters_created": len(clusters),
        "clusters": [_cluster_to_dict(c) for c in clusters],
    }


@router.get("/projects/{project_id}/clusters")
async def list_clusters(
    project_id: int,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """List clusters with KPI summaries."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.project_id == project_id,
            LookalikeCluster.company_id == company.id,
            LookalikeCluster.is_active == True,
        ).order_by(LookalikeCluster.qualified_lead_count.desc())
    )
    clusters = list(result.scalars().all())
    return [_cluster_to_dict(c) for c in clusters]


@router.get("/clusters/{cluster_id}")
async def get_cluster(
    cluster_id: int,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Cluster detail: members, strategy, runs."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.id == cluster_id,
            LookalikeCluster.company_id == company.id,
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    # Get members with contact info
    from app.models.contact import Contact
    members_result = await db.execute(
        select(ClusterMember, Contact).join(
            Contact, ClusterMember.contact_id == Contact.id
        ).where(ClusterMember.cluster_id == cluster_id)
    )
    members = []
    for member, contact in members_result.fetchall():
        members.append({
            "id": member.id,
            "contact_id": member.contact_id,
            "company_name": contact.company_name,
            "domain": contact.domain,
            "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            "title": contact.job_title,
            "business_model_description": member.business_model_description,
            "offer_fit": member.offer_fit,
            "website_scraped": member.website_scraped,
        })

    # Get runs
    runs_result = await db.execute(
        select(LookalikeRun).where(
            LookalikeRun.cluster_id == cluster_id
        ).order_by(LookalikeRun.created_at.desc())
    )
    runs = [_run_to_dict(r) for r in runs_result.scalars().all()]

    data = _cluster_to_dict(cluster)
    data["members"] = members
    data["runs"] = runs
    return data


@router.post("/clusters/{cluster_id}/run")
async def run_cluster_search(
    cluster_id: int,
    req: RunSearchRequest = RunSearchRequest(),
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Trigger Phase 3: execute search for this cluster."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.id == cluster_id,
            LookalikeCluster.company_id == company.id,
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Cluster not found")
    if not cluster.search_strategy:
        raise HTTPException(400, "No search strategy. Call POST /clusters/{id}/strategy first.")

    run_id = await lookalike_service.run_cluster_search(
        cluster_id=cluster_id,
        company_id=company.id,
        budget_apollo=req.budget_apollo_credits,
        budget_yandex=req.budget_yandex_queries,
        budget_google=req.budget_google_queries,
    )

    return {"status": "started", "run_id": run_id}


@router.get("/clusters/{cluster_id}/run/{run_id}/stream")
async def stream_run_progress(
    cluster_id: int,
    run_id: int,
):
    """SSE progress for a running search."""
    async def event_generator():
        while True:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(LookalikeRun).where(LookalikeRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if not run:
                    yield _sse_event("error", {"message": "Run not found"})
                    return

                data = _run_to_dict(run)

                # Add search job progress if available
                for phase, job_id_attr in [
                    ("apollo", "apollo_job_id"),
                    ("yandex", "yandex_job_id"),
                    ("google", "google_job_id"),
                ]:
                    job_id = getattr(run, job_id_attr)
                    if job_id:
                        from app.models.domain import SearchJob
                        job_result = await session.execute(
                            select(SearchJob).where(SearchJob.id == job_id)
                        )
                        job = job_result.scalar_one_or_none()
                        if job:
                            data[f"{phase}_job"] = {
                                "status": job.status.value if job.status else None,
                                "queries_total": job.queries_total,
                                "queries_completed": job.queries_completed,
                                "domains_found": job.domains_found,
                            }

                yield _sse_event("progress", data)

                if run.status in (LookalikeRunStatus.COMPLETED, LookalikeRunStatus.FAILED):
                    yield _sse_event("done", data)
                    return

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/clusters/{cluster_id}/strategy")
async def regenerate_strategy(
    cluster_id: int,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Re-generate search strategy for a cluster."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.id == cluster_id,
            LookalikeCluster.company_id == company.id,
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    cluster = await lookalike_service.generate_cluster_strategy(db, cluster_id)
    return _cluster_to_dict(cluster)


@router.get("/projects/{project_id}/dashboard")
async def get_dashboard(
    project_id: int,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """KPI dashboard for TAM analysis."""
    return await lookalike_service.get_project_dashboard(db, project_id)


@router.patch("/clusters/{cluster_id}")
async def update_cluster(
    cluster_id: int,
    req: UpdateClusterRequest,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Edit cluster name/strategy/offers."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.id == cluster_id,
            LookalikeCluster.company_id == company.id,
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    if req.name is not None:
        cluster.name = req.name
    if req.business_model is not None:
        cluster.business_model = req.business_model
    if req.offer_fit is not None:
        cluster.offer_fit = req.offer_fit
    if req.search_strategy is not None:
        cluster.search_strategy = req.search_strategy
    if req.is_active is not None:
        cluster.is_active = req.is_active

    await db.commit()
    return _cluster_to_dict(cluster)


@router.post("/projects/{project_id}/run-all")
async def run_all_clusters(
    project_id: int,
    req: RunSearchRequest = RunSearchRequest(),
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Trigger search for ALL active non-Misc clusters in a project."""
    result = await db.execute(
        select(LookalikeCluster).where(
            LookalikeCluster.project_id == project_id,
            LookalikeCluster.company_id == company.id,
            LookalikeCluster.is_active == True,
        ).order_by(LookalikeCluster.qualified_lead_count.desc())
    )
    clusters = list(result.scalars().all())

    # Skip Misc clusters and clusters without strategy
    eligible = [c for c in clusters if c.search_strategy and not c.name.lower().startswith('misc')]
    run_ids = []
    for cluster in eligible:
        run_id = await lookalike_service.run_cluster_search(
            cluster_id=cluster.id,
            company_id=company.id,
            budget_apollo=req.budget_apollo_credits,
            budget_yandex=req.budget_yandex_queries,
            budget_google=req.budget_google_queries,
        )
        run_ids.append({"cluster_id": cluster.id, "cluster_name": cluster.name, "run_id": run_id})

    return {"status": "started", "runs": run_ids, "total_clusters": len(eligible)}


@router.get("/projects/{project_id}/results")
async def get_project_results(
    project_id: int,
    cluster_id: Optional[int] = None,
    is_target: Optional[bool] = True,
    limit: int = 100,
    offset: int = 0,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Get all lookalike search results for a project, filterable by cluster."""
    from app.models.domain import SearchJob

    query = (
        select(SearchResult, SearchJob.cluster_id)
        .join(SearchJob, SearchResult.search_job_id == SearchJob.id)
        .where(
            SearchResult.project_id == project_id,
            SearchJob.cluster_id.isnot(None),
        )
    )

    if cluster_id:
        query = query.where(SearchJob.cluster_id == cluster_id)
    if is_target is not None:
        query = query.where(SearchResult.is_target == is_target)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch
    query = query.order_by(SearchResult.confidence.desc()).offset(offset).limit(limit)
    rows = (await db.execute(query)).fetchall()

    results = []
    for sr, clust_id in rows:
        results.append({
            "id": sr.id,
            "domain": sr.domain,
            "company_name": (sr.company_info or {}).get("name", sr.domain),
            "company_description": (sr.company_info or {}).get("description", ""),
            "cluster_id": clust_id,
            "is_target": sr.is_target,
            "confidence": sr.confidence,
            "reasoning": sr.reasoning,
            "scores": sr.scores,
            "matched_segment": sr.matched_segment,
            "source": "apollo",
            "analyzed_at": sr.analyzed_at.isoformat() if sr.analyzed_at else None,
        })

    return {"total": total, "results": results}


@router.post("/projects/{project_id}/export")
async def export_to_sheets(
    project_id: int,
    cluster_id: Optional[int] = None,
    company: Company = Depends(get_required_company),
    db: AsyncSession = Depends(get_session),
):
    """Export lookalike results to a new Google Sheet."""
    from app.services.google_sheets_service import google_sheets_service
    from app.models.domain import SearchJob

    # Fetch results
    query = (
        select(SearchResult, SearchJob.cluster_id)
        .join(SearchJob, SearchResult.search_job_id == SearchJob.id)
        .where(
            SearchResult.project_id == project_id,
            SearchJob.cluster_id.isnot(None),
            SearchResult.is_target == True,
        )
    )
    if cluster_id:
        query = query.where(SearchJob.cluster_id == cluster_id)
    query = query.order_by(SearchResult.confidence.desc())
    rows = (await db.execute(query)).fetchall()

    if not rows:
        raise HTTPException(400, "No target results to export")

    # Load cluster names
    cluster_result = await db.execute(
        select(LookalikeCluster).where(LookalikeCluster.project_id == project_id)
    )
    cluster_map = {c.id: c.name for c in cluster_result.scalars().all()}

    # Build sheet data
    headers = [
        "Domain", "Company Name", "Description", "Cluster",
        "Confidence", "Matched Segment", "Reasoning",
        "Industry Score", "Service Score", "Geography Score",
        "Analyzed At",
    ]
    data = [headers]
    for sr, clust_id in rows:
        scores = sr.scores or {}
        info = sr.company_info or {}
        data.append([
            sr.domain,
            info.get("name", sr.domain),
            info.get("description", ""),
            cluster_map.get(clust_id, f"#{clust_id}"),
            sr.confidence,
            sr.matched_segment or "",
            sr.reasoning or "",
            scores.get("industry_match", ""),
            scores.get("service_match", ""),
            scores.get("geography_match", ""),
            sr.analyzed_at.isoformat() if sr.analyzed_at else "",
        ])

    # Load project name for title
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    title = f"TAM Lookalikes — {project.name if project else f'Project {project_id}'} — {datetime.utcnow().strftime('%Y-%m-%d')}"

    sheet_url = google_sheets_service.create_and_populate(
        title=title,
        data=data,
    )

    if not sheet_url:
        raise HTTPException(500, "Failed to create Google Sheet — check service account config")

    return {"sheet_url": sheet_url, "rows_exported": len(data) - 1}


# ============ Helpers ============

def _cluster_to_dict(c: LookalikeCluster) -> dict:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "name": c.name,
        "business_model": c.business_model,
        "offer_fit": c.offer_fit,
        "search_strategy": c.search_strategy,
        "qualified_lead_count": c.qualified_lead_count or 0,
        "apollo_companies_found": c.apollo_companies_found or 0,
        "yandex_targets_found": c.yandex_targets_found or 0,
        "google_targets_found": c.google_targets_found or 0,
        "total_lookalikes": c.total_lookalikes or 0,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _run_to_dict(r: LookalikeRun) -> dict:
    return {
        "id": r.id,
        "cluster_id": r.cluster_id,
        "status": r.status.value if r.status else None,
        "current_phase": r.current_phase.value if r.current_phase else None,
        "apollo_job_id": r.apollo_job_id,
        "yandex_job_id": r.yandex_job_id,
        "google_job_id": r.google_job_id,
        "budget_apollo_credits": r.budget_apollo_credits,
        "budget_yandex_queries": r.budget_yandex_queries,
        "budget_google_queries": r.budget_google_queries,
        "stats": r.stats,
        "total_lookalikes_found": r.total_lookalikes_found or 0,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "error_message": r.error_message,
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _load_offers(db: AsyncSession, project_id: int) -> Optional[List[dict]]:
    """Load offers from ProjectKnowledge (category=tam, key=offers)."""
    try:
        entry = await project_knowledge_service.get_entry(db, project_id, "tam", "offers")
        if entry and entry.get("value"):
            value = entry["value"]
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get("offers", [])
            if isinstance(value, list):
                return value
    except Exception:
        pass
    return None
