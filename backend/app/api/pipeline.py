"""
Pipeline API — Discovered companies, contact extraction, Apollo enrichment, CRM promotion.

All endpoints are company-scoped (require X-Company-ID header).
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import asyncio
import csv
import io
import json
import logging
from datetime import datetime

from sqlalchemy import select
from app.db import get_session, async_session_maker
from app.api.companies import get_required_company
from app.models.user import Company
from app.core.config import settings
from app.schemas.pipeline import (
    DiscoveredCompanyResponse, DiscoveredCompanyDetail,
    ExtractedContactResponse, PipelineEventResponse,
    PipelineStats, SpendingDetail,
    ExtractContactsRequest, ApolloEnrichRequest, ProjectEnrichRequest,
    PromoteToContactsRequest, BulkStatusUpdateRequest,
    PipelineExportSheetRequest, PipelineExportSheetResponse,
)
from app.services.pipeline_service import pipeline_service
from pydantic import BaseModel, Field

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger(__name__)

# In-memory registry of running full-pipeline tasks (cache — DB is source of truth)
_running_pipelines: dict[int, dict] = {}


# ---- DB-backed pipeline state helpers ----

async def _create_pipeline_run(project_id: int, company_id: int, config: dict) -> int:
    """Create a PipelineRun in DB, return its ID."""
    from app.models.pipeline_run import PipelineRun, PipelineRunStatus
    async with async_session_maker() as session:
        run = PipelineRun(
            project_id=project_id,
            company_id=company_id,
            status=PipelineRunStatus.RUNNING,
            config=config,
            progress={},
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def _update_pipeline_run(run_id: int, **kwargs):
    """Update a PipelineRun's fields."""
    from app.models.pipeline_run import PipelineRun
    async with async_session_maker() as session:
        result = await session.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            for k, v in kwargs.items():
                setattr(run, k, v)
            await session.commit()


async def _log_phase(run_id: int, phase: str, status: str, **kwargs):
    """Log a pipeline phase transition."""
    from app.models.pipeline_run import PipelinePhaseLog, PipelinePhase, PipelinePhaseStatus
    phase_enum = PipelinePhase(phase) if phase in [p.value for p in PipelinePhase] else None
    if not phase_enum:
        return
    async with async_session_maker() as session:
        log = PipelinePhaseLog(
            pipeline_run_id=run_id,
            phase=phase_enum,
            status=PipelinePhaseStatus(status),
            started_at=kwargs.get("started_at"),
            completed_at=kwargs.get("completed_at"),
            stats=kwargs.get("stats"),
            cost_usd=kwargs.get("cost_usd", 0),
            error_message=kwargs.get("error_message"),
        )
        session.add(log)
        await session.commit()


async def _check_stop_requested(run_id: int) -> bool:
    """Check if a pipeline run has been requested to stop (via DB)."""
    from app.models.pipeline_run import PipelineRun, PipelineRunStatus
    async with async_session_maker() as session:
        result = await session.execute(select(PipelineRun.status).where(PipelineRun.id == run_id))
        status = result.scalar_one_or_none()
        return status == PipelineRunStatus.STOPPED


async def _mark_interrupted_runs():
    """On startup, mark any RUNNING pipeline runs as FAILED."""
    from app.models.pipeline_run import PipelineRun, PipelineRunStatus
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.status == PipelineRunStatus.RUNNING)
            )
            runs = result.scalars().all()
            for run in runs:
                run.status = PipelineRunStatus.FAILED
                run.error_message = "Server restarted while pipeline was running"
                run.completed_at = datetime.utcnow()
            if runs:
                await session.commit()
                logger.info(f"Marked {len(runs)} interrupted pipeline runs as FAILED")
    except Exception as e:
        logger.error(f"Failed to mark interrupted runs: {e}")


# ============ Full Pipeline (background task) ============

class FullPipelineRequest(BaseModel):
    max_queries: int = Field(1500, ge=1, le=5000)
    target_goal: int = Field(2000, ge=1, le=50000)
    apollo_search: bool = Field(False, description="Use Apollo as search engine (off by default)")
    apollo_credits: int = Field(500, ge=0, le=10000)
    apollo_max_people: int = Field(5, ge=1, le=20)
    apollo_titles: List[str] = Field(
        default=["CEO", "Founder", "Managing Director", "Partner", "Head of Business Development"]
    )
    skip_search: bool = False
    skip_extraction: bool = False
    skip_enrichment: bool = False
    skip_smartlead_push: bool = True  # Off by default, enable explicitly
    # Segment-based search (new template system)
    use_segment_search: bool = Field(False, description="Use template-based segment search instead of AI-random")
    skip_google: bool = Field(True, description="Skip Google search (Yandex only for testing)")
    segments: Optional[List[str]] = Field(None, description="Specific segments to run (None = all by priority)")
    geos: Optional[List[str]] = Field(None, description="Specific geos to run (None = all for each segment)")


@router.post("/full-pipeline/{project_id}")
async def run_full_pipeline(
    project_id: int,
    body: FullPipelineRequest = FullPipelineRequest(),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Launch full pipeline: parallel search → website extraction → Apollo enrichment.

    Runs as a background task inside the backend process. Progress tracked in-memory
    and queryable via GET /pipeline/full-pipeline/{project_id}/status.
    """
    from app.models.contact import Project
    from sqlalchemy import select

    proj = await db.execute(select(Project).where(Project.id == project_id, Project.company_id == company.id))
    project = proj.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.target_segments:
        raise HTTPException(status_code=400, detail="Project has no target_segments configured")

    if project_id in _running_pipelines and _running_pipelines[project_id].get("running"):
        return {"status": "already_running", "progress": _running_pipelines[project_id]}

    # Create DB-backed pipeline run
    run_id = await _create_pipeline_run(project_id, company.id, body.model_dump())

    _running_pipelines[project_id] = {
        "running": True,
        "phase": "starting",
        "started_at": datetime.utcnow().isoformat(),
        "config": body.model_dump(),
        "pipeline_run_id": run_id,
    }

    background_tasks.add_task(
        _run_full_pipeline_bg, project_id, company.id, body
    )

    return {"status": "started", "project_id": project_id, "pipeline_run_id": run_id}


@router.get("/full-pipeline/{project_id}/status")
async def get_full_pipeline_status(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get status of a running full pipeline."""
    if project_id in _running_pipelines and _running_pipelines[project_id].get("running"):
        return _running_pipelines[project_id]

    # Fall back to DB for historical/restarted runs
    from app.models.pipeline_run import PipelineRun
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.project_id == project_id, PipelineRun.company_id == company.id)
        .order_by(PipelineRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run:
        return {
            "pipeline_run_id": run.id,
            "running": run.status.value == "RUNNING",
            "phase": run.current_phase.value if run.current_phase else None,
            "status": run.status.value,
            "progress": run.progress or {},
            "config": run.config or {},
            "total_cost_usd": float(run.total_cost_usd or 0),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error_message": run.error_message,
        }
    return {"status": "not_running"}


@router.post("/full-pipeline/{project_id}/stop")
async def stop_full_pipeline(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Request stop for a running pipeline (checked between phases)."""
    if project_id in _running_pipelines:
        _running_pipelines[project_id]["stop_requested"] = True
        # Also mark in DB
        run_id = _running_pipelines[project_id].get("pipeline_run_id")
        if run_id:
            from app.models.pipeline_run import PipelineRunStatus
            await _update_pipeline_run(run_id, status=PipelineRunStatus.STOPPED)
        return {"status": "stop_requested"}
    return {"status": "not_running"}


async def _run_full_pipeline_bg(project_id: int, company_id: int, cfg: FullPipelineRequest):
    """Background task: full pipeline orchestration with DB-backed state."""
    from app.models.pipeline_run import PipelineRunStatus, PipelinePhase

    progress = _running_pipelines.get(project_id, {})
    run_id = progress.get("pipeline_run_id")

    async def _transition_phase(phase_name: str, phase_enum_val: str):
        """Update both in-memory cache and DB."""
        progress["phase"] = phase_name
        if run_id:
            try:
                phase_enum = PipelinePhase(phase_enum_val)
                await _update_pipeline_run(run_id, current_phase=phase_enum, progress=progress)
                await _log_phase(run_id, phase_enum_val, "STARTED", started_at=datetime.utcnow())
            except Exception:
                pass

    async def _complete_phase(phase_enum_val: str, stats: dict = None):
        if run_id:
            try:
                await _log_phase(run_id, phase_enum_val, "COMPLETED", completed_at=datetime.utcnow(), stats=stats)
            except Exception:
                pass
        # Send chat notification
        try:
            from app.services.chat_notification_service import chat_notification_service
            await chat_notification_service.on_pipeline_phase_complete(project_id, phase_enum_val, stats)
        except Exception:
            pass

    def _is_stopped():
        return progress.get("stop_requested", False)

    try:
        # --- Phase 1: Parallel Search ---
        if not cfg.skip_search:
            await _transition_phase("search", "SEARCH")
            await _bg_phase_search(project_id, company_id, cfg, progress)
            await _complete_phase("SEARCH", progress.get("search_results"))
            if _is_stopped():
                progress.update({"running": False, "phase": "stopped"})
                if run_id:
                    await _update_pipeline_run(run_id, status=PipelineRunStatus.STOPPED, completed_at=datetime.utcnow())
                return

        # --- Phase 2: Website Contact Extraction ---
        if not cfg.skip_extraction:
            await _transition_phase("extraction", "EXTRACTION")
            await _bg_phase_extraction(project_id, company_id, progress)
            await _complete_phase("EXTRACTION", progress.get("extraction_stats"))
            if _is_stopped():
                progress.update({"running": False, "phase": "stopped"})
                if run_id:
                    await _update_pipeline_run(run_id, status=PipelineRunStatus.STOPPED, completed_at=datetime.utcnow())
                return

        # --- Phase 3: Apollo Enrichment ---
        if not cfg.skip_enrichment:
            await _transition_phase("enrichment", "ENRICHMENT")
            await _bg_phase_enrichment(project_id, company_id, cfg, progress)
            await _complete_phase("ENRICHMENT", progress.get("enrichment_stats"))
            if _is_stopped():
                progress.update({"running": False, "phase": "stopped"})
                if run_id:
                    await _update_pipeline_run(run_id, status=PipelineRunStatus.STOPPED, completed_at=datetime.utcnow())
                return

        # --- Phase 4: SmartLead Push ---
        if not cfg.skip_smartlead_push:
            await _transition_phase("smartlead_push", "SMARTLEAD_PUSH")
            await _bg_phase_smartlead_push(project_id, company_id, progress)
            await _complete_phase("SMARTLEAD_PUSH", progress.get("smartlead_push_stats"))

        # --- Phase 5: Auto-promote all target contacts to CRM ---
        await _transition_phase("crm_promote", "CRM_PROMOTE")
        await _bg_phase_crm_promote(project_id, company_id, progress)
        await _complete_phase("CRM_PROMOTE")

        progress.update({"running": False, "phase": "completed", "completed_at": datetime.utcnow().isoformat()})
        if run_id:
            await _update_pipeline_run(
                run_id,
                status=PipelineRunStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                progress=progress,
            )
        logger.info(f"Full pipeline completed for project {project_id}")

        # Notify chat
        try:
            from app.services.chat_notification_service import chat_notification_service
            await chat_notification_service.on_pipeline_complete(project_id)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Full pipeline crashed for project {project_id}: {e}", exc_info=True)
        progress.update({"running": False, "phase": "error", "error": str(e)[:500]})
        if run_id:
            await _update_pipeline_run(
                run_id,
                status=PipelineRunStatus.FAILED,
                error_message=str(e)[:500],
                completed_at=datetime.utcnow(),
                progress=progress,
            )
        # Notify chat of error
        try:
            from app.services.chat_notification_service import chat_notification_service
            await chat_notification_service.on_error(
                project_id, "pipeline", str(e)[:300],
                suggestion="Check logs and retry",
            )
        except Exception:
            pass


async def _bg_phase_search(project_id: int, company_id: int, cfg: FullPipelineRequest, progress: dict):
    """Run search — either segment-based (templates) or legacy AI-random."""
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service

    async with async_session_maker() as session:
        targets_before = await company_search_service._count_project_targets(session, project_id)
    progress["targets_before_search"] = targets_before

    if cfg.use_segment_search:
        # ── NEW: Segment-based template search ──
        await _bg_phase_segment_search(project_id, company_id, cfg, progress, targets_before)
    else:
        # ── Legacy: AI-random parallel search ──
        engines = [
            ("yandex", SearchEngine.YANDEX_API),
        ]
        if not cfg.skip_google:
            engines.append(("google", SearchEngine.GOOGLE_SERP))
        if cfg.apollo_search:
            engines.append(("apollo", SearchEngine.APOLLO_ORG))

        async def run_engine(name: str, engine: SearchEngine):
            try:
                async with async_session_maker() as session:
                    job = await company_search_service.run_project_search(
                        session=session,
                        project_id=project_id,
                        company_id=company_id,
                        max_queries=cfg.max_queries,
                        target_goal=cfg.target_goal,
                        search_engine=engine,
                    )
                    return name, job
            except Exception as e:
                logger.error(f"[{name}] search failed: {e}", exc_info=True)
                return name, None

        results = await asyncio.gather(*[run_engine(n, e) for n, e in engines])

        progress["search_results"] = {
            name: {"job_id": job.id, "status": str(job.status)} if job else {"error": "failed"}
            for name, job in results
        }

    async with async_session_maker() as session:
        targets_after = await company_search_service._count_project_targets(session, project_id)
    progress["targets_after_search"] = targets_after
    progress["new_targets_from_search"] = targets_after - targets_before
    logger.info(f"Search done for project {project_id}: {targets_before} → {targets_after} targets")


async def _bg_phase_segment_search(
    project_id: int, company_id: int, cfg: FullPipelineRequest,
    progress: dict, targets_before: int,
):
    """Parallel segment search — all segments run concurrently, geos sequential within each."""
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service
    from app.services.query_templates import SEGMENTS, SEGMENT_KEYS
    from app.services.search_config_service import search_config_service

    engine = SearchEngine.YANDEX_API
    if not cfg.skip_google:
        engine = SearchEngine.GOOGLE_SERP

    # Load per-project search config from DB (falls back to hardcoded SEGMENTS)
    async with async_session_maker() as session:
        db_config = await search_config_service.get_or_create_config(session, project_id)
    db_segments = db_config.get("segments") if db_config else None
    segments_source = db_segments or SEGMENTS

    # Determine which segments to run
    if cfg.segments:
        segment_order = [s for s in cfg.segments if s in segments_source]
    else:
        if db_segments:
            # Sort by priority (lower = higher priority)
            segment_order = sorted(db_segments.keys(), key=lambda k: db_segments[k].get("priority", 99))
        else:
            segment_order = SEGMENT_KEYS  # All by priority

    progress["segment_search"] = {
        "mode": "parallel",
        "engine": engine.value,
        "segments_planned": segment_order,
        "segments_completed": [],
        "segment_stats": {},
        "active_segments": [],
    }

    # Initialize stats for all segments upfront
    for seg_key in segment_order:
        progress["segment_search"]["segment_stats"][seg_key] = {
            "geos": {},
            "total_queries": 0,
            "total_targets": 0,
        }

    async def _run_one_segment(seg_key: str):
        """Run all geos for one segment sequentially."""
        seg_def = segments_source.get(seg_key, {})
        geo_keys = list(seg_def.get("geos", {}).keys())

        # Filter geos if specified in config
        if cfg.geos:
            geo_keys = [g for g in geo_keys if g in cfg.geos]
            if not geo_keys:
                logger.info(f"Skipping segment {seg_key}: no matching geos from {cfg.geos}")
                return

        progress["segment_search"]["active_segments"].append(seg_key)
        logger.info(f"Starting parallel segment: {seg_key} ({len(geo_keys)} geos)")

        for geo_key in geo_keys:
            if progress.get("stop_requested"):
                break

            try:
                async with async_session_maker() as session:
                    stats = await company_search_service.run_segment_search(
                        session=session,
                        project_id=project_id,
                        company_id=company_id,
                        segment_key=seg_key,
                        geo_key=geo_key,
                        search_engine=engine,
                    )
            except Exception as e:
                logger.error(f"Segment search {seg_key}/{geo_key} failed: {e}", exc_info=True)
                stats = {"segment": seg_key, "geo": geo_key, "error": str(e)}

            # Update progress (each segment writes to its own key — no race)
            seg_stats = progress["segment_search"]["segment_stats"][seg_key]
            seg_stats["geos"][geo_key] = stats
            seg_stats["total_queries"] += stats.get("total_queries", 0)
            seg_stats["total_targets"] += stats.get("targets_found", 0)

            logger.info(
                f"Segment {seg_key}/{geo_key}: "
                f"{stats.get('doc_keyword_queries', 0)} doc + {stats.get('ai_queries', 0)} AI = "
                f"{stats.get('total_queries', 0)} queries, {stats.get('targets_found', 0)} targets"
            )

        progress["segment_search"]["segments_completed"].append(seg_key)
        if seg_key in progress["segment_search"]["active_segments"]:
            progress["segment_search"]["active_segments"].remove(seg_key)
        logger.info(f"Segment {seg_key} completed")

    # Launch ALL segments in parallel
    logger.info(f"Launching {len(segment_order)} segments in parallel: {segment_order}")
    await asyncio.gather(*[_run_one_segment(seg) for seg in segment_order])

    progress["segment_search"]["finished"] = True
    progress["search_results"] = progress["segment_search"]["segment_stats"]


async def _bg_phase_extraction(project_id: int, company_id: int, progress: dict):
    """Extract contacts from target company websites."""
    from sqlalchemy import select, or_
    from app.models.pipeline import DiscoveredCompany

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.company_id == company_id,
                DiscoveredCompany.is_target == True,
                or_(DiscoveredCompany.contacts_count == 0, DiscoveredCompany.contacts_count.is_(None)),
            )
        )
        ids = [r[0] for r in result.fetchall()]

    progress["extraction_total"] = len(ids)
    if not ids:
        progress["extraction_stats"] = {"processed": 0, "contacts_found": 0}
        return

    BATCH = 20
    stats = {"processed": 0, "contacts_found": 0, "errors": 0}
    for i in range(0, len(ids), BATCH):
        if progress.get("stop_requested"):
            break
        batch = ids[i:i + BATCH]
        try:
            async with async_session_maker() as session:
                r = await pipeline_service.extract_contacts_batch(session, batch, company_id=company_id)
            stats["processed"] += r.get("processed", 0)
            stats["contacts_found"] += r.get("contacts_found", 0)
            stats["errors"] += r.get("errors", 0)
            progress["extraction_stats"] = stats.copy()
        except Exception as e:
            logger.error(f"Extraction batch failed: {e}", exc_info=True)
            stats["errors"] += len(batch)

    logger.info(f"Extraction done for project {project_id}: {stats}")


async def _bg_phase_enrichment(project_id: int, company_id: int, cfg: FullPipelineRequest, progress: dict):
    """Apollo people enrichment for unenriched targets.

    Includes budget guardrail: pauses at apollo_credit_limit (default 200) from auto_enrich_config.
    """
    from sqlalchemy import select
    from app.models.pipeline import DiscoveredCompany
    from app.models.contact import Project

    # Load project's auto_enrich_config for credit limit
    apollo_credit_limit = cfg.apollo_credits  # Default from pipeline request
    async with async_session_maker() as session:
        proj_result = await session.execute(select(Project).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()
        if project and project.auto_enrich_config:
            apollo_credit_limit = project.auto_enrich_config.get("apollo_credit_limit", apollo_credit_limit)

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.company_id == company_id,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.apollo_enriched_at.is_(None),
            ).order_by(DiscoveredCompany.confidence.desc())
        )
        ids = [r[0] for r in result.fetchall()]

    progress["enrichment_total"] = len(ids)
    if not ids:
        progress["enrichment_stats"] = {"processed": 0, "people_found": 0, "credits_used": 0}
        return

    BATCH = 10
    stats = {"processed": 0, "people_found": 0, "credits_used": 0, "errors": 0, "skipped": 0}
    for i in range(0, len(ids), BATCH):
        if progress.get("stop_requested"):
            break
        remaining = apollo_credit_limit - stats["credits_used"]
        if remaining <= 0:
            # Budget pause: log and stop
            logger.warning(
                f"Apollo credit limit reached ({apollo_credit_limit} credits) for project {project_id}. "
                f"Used: {stats['credits_used']}. Pausing enrichment."
            )
            progress["enrichment_paused"] = True
            progress["enrichment_pause_reason"] = f"Apollo credit limit reached ({apollo_credit_limit})"
            # Save a chat message for the user
            try:
                from sqlalchemy import text as sql_text
                async with async_session_maker() as session:
                    await session.execute(sql_text("""
                        INSERT INTO project_chat_messages (project_id, role, content, created_at)
                        VALUES (:pid, 'system', :content, NOW())
                    """), {
                        "pid": project_id,
                        "content": (
                            f"Apollo enrichment paused: credit limit of {apollo_credit_limit} reached "
                            f"({stats['credits_used']} credits used, {stats['people_found']} people found). "
                            f"Resume via pipeline API or increase limit in auto_enrich_config."
                        ),
                    })
                    await session.commit()
            except Exception as chat_err:
                logger.debug(f"Failed to save enrichment pause chat message: {chat_err}")
            break

        batch = ids[i:i + BATCH]
        try:
            async with async_session_maker() as session:
                r = await pipeline_service.enrich_apollo_batch(
                    session, batch, company_id=company_id,
                    max_people=cfg.apollo_max_people,
                    max_credits=remaining,
                    titles=cfg.apollo_titles or None,
                )
            stats["processed"] += r.get("processed", 0)
            stats["people_found"] += r.get("people_found", 0)
            stats["credits_used"] += r.get("credits_used", 0)
            stats["errors"] += r.get("errors", 0)
            stats["skipped"] += r.get("skipped", 0)
            progress["enrichment_stats"] = stats.copy()
        except Exception as e:
            logger.error(f"Enrichment batch failed: {e}", exc_info=True)
            stats["errors"] += len(batch)

    logger.info(f"Enrichment done for project {project_id}: {stats}")


async def _bg_phase_smartlead_push(project_id: int, company_id: int, progress: dict):
    """Phase 4: Push contacts to SmartLead campaigns based on push rules."""
    from sqlalchemy import select, text as sql_text
    from app.models.pipeline import CampaignPushRule, PipelineEvent, PipelineEventType
    from app.services.name_classifier import classify_contact, match_rule
    stats = {"campaigns_created": 0, "leads_pushed": 0, "errors": 0, "rules_matched": {}}
    progress["smartlead_push_stats"] = stats

    # 1. Load active push rules for project
    async with async_session_maker() as session:
        result = await session.execute(
            select(CampaignPushRule).where(
                CampaignPushRule.project_id == project_id,
                CampaignPushRule.company_id == company_id,
                CampaignPushRule.is_active == True,
            ).order_by(CampaignPushRule.priority.desc())
        )
        rules = result.scalars().all()

    if not rules:
        logger.info(f"No push rules for project {project_id}, skipping SmartLead push")
        progress["smartlead_push_stats"] = {"skipped": "no_rules"}
        return

    # 2. Query target contacts not yet pushed to SmartLead.
    #    Include contacts already in CRM if they have no campaigns assigned
    #    (i.e. CRM-promoted but never pushed to SmartLead).
    async with async_session_maker() as session:
        rows = await session.execute(sql_text("""
            SELECT ec.id, ec.email, ec.first_name, ec.last_name, ec.job_title,
                   dc.domain, dc.name as company_name, dc.url,
                   sr.matched_segment
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            LEFT JOIN search_results sr ON dc.search_result_id = sr.id
            WHERE dc.project_id = :pid AND dc.company_id = :cid
            AND dc.is_target = true
            AND ec.email IS NOT NULL AND ec.email != ''
            AND lower(ec.email) NOT IN (
                SELECT DISTINCT lower(c.email) FROM contacts c
                WHERE c.email IS NOT NULL
                AND c.campaigns IS NOT NULL
                AND c.campaigns::text NOT IN ('null', '[]', '')
            )
            ORDER BY ec.id
        """), {"pid": project_id, "cid": company_id})
        contacts = rows.fetchall()

    if not contacts:
        logger.info(f"No new contacts to push for project {project_id}")
        progress["smartlead_push_stats"]["skipped"] = "no_contacts"
        return

    # Filter out junk emails before classifying
    from app.services.contact_extraction_service import is_valid_email
    valid_contacts = [c for c in contacts if is_valid_email(c.email)]
    junk_count = len(contacts) - len(valid_contacts)
    if junk_count > 0:
        logger.info(f"SmartLead push: filtered out {junk_count} junk emails")
    contacts = valid_contacts

    if not contacts:
        logger.info(f"No valid contacts to push for project {project_id}")
        progress["smartlead_push_stats"]["skipped"] = "no_valid_contacts"
        return

    logger.info(f"SmartLead push: {len(contacts)} contacts to classify, {len(rules)} rules")

    # 3. Classify and bucket contacts
    buckets: dict[int, list] = {rule.id: [] for rule in rules}
    unmatched = []

    for contact in contacts:
        classification = classify_contact(
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
        )
        matched = False
        for rule in rules:
            if match_rule(classification, rule):
                buckets[rule.id].append((contact, classification))
                matched = True
                break
        if not matched:
            unmatched.append(contact)

    for rule in rules:
        count = len(buckets[rule.id])
        stats["rules_matched"][rule.name] = count
        logger.info(f"  Rule '{rule.name}': {count} contacts")
    if unmatched:
        logger.info(f"  Unmatched: {len(unmatched)} contacts")

    # 4. Push each bucket to SmartLead
    import os
    from app.services.smartlead_service import smartlead_service as _sl_svc, smartlead_request as _sl_req
    api_key = os.environ.get("SMARTLEAD_API_KEY") or getattr(_sl_svc, "_api_key", None)
    if not api_key:
        logger.error("SMARTLEAD_API_KEY not configured, cannot push")
        stats["errors"] += 1
        return

    for rule in rules:
        bucket_contacts = buckets.get(rule.id, [])
        if not bucket_contacts:
            continue

        if progress.get("stop_requested"):
            break

        try:
            campaign_id = await _ensure_campaign_for_rule(
                None, api_key, rule, len(bucket_contacts), session=None
            )
            if not campaign_id:
                logger.error(f"Failed to create/get campaign for rule '{rule.name}'")
                stats["errors"] += len(bucket_contacts)
                continue

            stats["campaigns_created"] += 1 if not rule.current_campaign_id else 0

            # Upload leads in batches of 100, track actually pushed emails
            LEAD_BATCH = 100
            actually_pushed_contacts = []
            total_uploaded = 0
            total_duplicates = 0
            total_invalid = 0

            for i in range(0, len(bucket_contacts), LEAD_BATCH):
                batch = bucket_contacts[i:i + LEAD_BATCH]
                leads = []
                for contact, cls in batch:
                    lead = {
                        "email": contact.email,
                        "first_name": contact.first_name or "",
                        "last_name": contact.last_name or "",
                        "company_name": contact.company_name or "",
                        "website": contact.url or f"https://{contact.domain}" if contact.domain else "",
                    }
                    if contact.job_title:
                        lead["custom_fields"] = {"job_title": contact.job_title}
                    leads.append(lead)

                # Push to SmartLead (API expects {lead_list: [...]})
                resp = await _sl_req(
                    "POST",
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                    params={"api_key": api_key},
                    json={"lead_list": leads},
                    timeout=60,
                )
                if resp.status_code == 200:
                    resp_data = resp.json() if resp.text else {}
                    upload_count = resp_data.get("upload_count", len(leads))
                    duplicate_count = resp_data.get("duplicate_count", 0)
                    invalid_count = resp_data.get("invalid_email_count", 0)

                    total_uploaded += upload_count
                    total_duplicates += duplicate_count
                    total_invalid += invalid_count
                    stats["leads_pushed"] += upload_count

                    logger.info(
                        f"Pushed batch to campaign {campaign_id}: "
                        f"uploaded={upload_count}, duplicates={duplicate_count}, "
                        f"invalid={invalid_count} (sent {len(leads)})"
                    )

                    # Only record contacts as pushed if some were actually uploaded
                    if upload_count > 0:
                        actually_pushed_contacts.extend(batch)
                else:
                    logger.error(f"Failed to push leads: {resp.status_code} {resp.text[:200]}")
                    stats["errors"] += len(leads)

                await asyncio.sleep(3)  # Rate limit — SmartLead allows 200 req/min

            # Verification: check actual lead count in SmartLead campaign
            verified_count = None
            try:
                verify_resp = await _sl_req(
                    "GET",
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                    params={"api_key": api_key, "offset": 0, "limit": 1},
                    timeout=30,
                )
                if verify_resp.status_code == 200:
                    verify_data = verify_resp.json()
                    if isinstance(verify_data, dict):
                        verified_count = verify_data.get("totalCount", verify_data.get("total", None))
                    elif isinstance(verify_data, list):
                        # Some endpoints return list; check headers or len
                        verified_count = len(verify_data)
                    logger.info(
                        f"Verification for campaign {campaign_id}: "
                        f"API reported={total_uploaded}, verified_in_campaign={verified_count}"
                    )
            except Exception as ve:
                logger.warning(f"Verification check failed for campaign {campaign_id}: {ve}")

            # Record event with detailed push results (use raw SQL to avoid enum mismatch)
            async with async_session_maker() as session:
                await session.execute(sql_text("""
                    INSERT INTO pipeline_events (company_id, event_type, detail, created_at)
                    VALUES (:cid, 'smartlead_leads_pushed', CAST(:detail AS jsonb), NOW())
                """), {
                    "cid": company_id,
                    "detail": json.dumps({
                        "rule_name": rule.name,
                        "campaign_id": str(campaign_id),
                        "leads_sent": len(bucket_contacts),
                        "leads_uploaded": total_uploaded,
                        "leads_duplicate": total_duplicates,
                        "leads_invalid": total_invalid,
                        "verified_count": verified_count,
                    }),
                })
                await session.commit()

            # Upsert actually-pushed contacts into contacts table
            if actually_pushed_contacts:
                campaign_entry = [{
                    "name": rule.campaign_name_template,
                    "id": str(campaign_id),
                    "source": "smartlead",
                }]
                async with async_session_maker() as session:
                    for contact, cls in actually_pushed_contacts:
                        domain = contact.email.split("@")[-1] if "@" in contact.email else None
                        seg = getattr(contact, "matched_segment", None) or None
                        # Check if contact already exists
                        existing = await session.execute(sql_text("""
                            SELECT id, campaigns FROM contacts
                            WHERE company_id = :cid AND lower(email) = lower(:email)
                            AND deleted_at IS NULL
                            LIMIT 1
                        """), {"cid": company_id, "email": contact.email})
                        row = existing.fetchone()
                        if row:
                            # Update existing contact with pipeline data
                            old_campaigns = row.campaigns or []
                            if isinstance(old_campaigns, str):
                                try:
                                    old_campaigns = json.loads(old_campaigns)
                                except Exception:
                                    old_campaigns = []
                            merged_campaigns = old_campaigns + campaign_entry
                            await session.execute(sql_text("""
                                UPDATE contacts SET
                                    project_id = COALESCE(project_id, :project_id),
                                    segment = COALESCE(segment, :segment),
                                    company_name = COALESCE(company_name, :company_name),
                                    job_title = COALESCE(job_title, :job_title),
                                    campaigns = CAST(:campaigns AS jsonb),
                                    updated_at = NOW()
                                WHERE id = :id
                            """), {
                                "id": row.id,
                                "project_id": project_id,
                                "segment": seg,
                                "company_name": contact.company_name or None,
                                "job_title": contact.job_title or None,
                                "campaigns": json.dumps(merged_campaigns),
                            })
                        else:
                            # Insert new contact
                            await session.execute(sql_text("""
                                INSERT INTO contacts (company_id, email, first_name, last_name, domain,
                                                      company_name, job_title, project_id, segment,
                                                      source, status, campaigns, is_active,
                                                      created_at, updated_at)
                                VALUES (:cid, :email, :fname, :lname, :domain,
                                        :company_name, :job_title, :project_id, :segment,
                                        'smartlead_pipeline_push', 'contacted', CAST(:campaigns AS jsonb), true,
                                        NOW(), NOW())
                            """), {
                                "cid": company_id, "email": contact.email,
                                "fname": contact.first_name or "", "lname": contact.last_name or "",
                                "domain": domain,
                                "company_name": contact.company_name or "",
                                "job_title": contact.job_title or "",
                                "project_id": project_id,
                                "segment": seg,
                                "campaigns": json.dumps(campaign_entry),
                            })
                    await session.commit()

            # Update rule's lead count
            async with async_session_maker() as session:
                await session.execute(sql_text("""
                    UPDATE campaign_push_rules
                    SET current_campaign_lead_count = COALESCE(current_campaign_lead_count, 0) + :cnt,
                        updated_at = NOW()
                    WHERE id = :rid
                """), {"cnt": total_uploaded, "rid": rule.id})
                await session.commit()

        except Exception as e:
            logger.error(f"SmartLead push error for rule '{rule.name}': {e}", exc_info=True)
            stats["errors"] += len(bucket_contacts)

    progress["smartlead_push_stats"] = stats
    logger.info(f"SmartLead push done for project {project_id}: {stats}")


async def _bg_phase_crm_promote(project_id: int, company_id: int, progress: dict):
    """Phase 5: Auto-promote ALL target extracted contacts to CRM contacts table.

    Ensures every extracted contact from a target company appears in the CRM,
    with project_id, segment, company_name, job_title, gathering_details populated.
    Contacts already in CRM are updated (fill NULLs), new ones are inserted.
    """
    import json as _json
    from sqlalchemy import text as sql_text
    from app.services.contact_extraction_service import is_valid_email

    stats = {"inserted": 0, "updated": 0, "skipped_invalid": 0, "errors": 0}
    progress["crm_promote_stats"] = stats

    try:
        async with async_session_maker() as session:
            # Get all extracted contacts with gathering context
            rows = await session.execute(sql_text("""
                SELECT ec.id, ec.email, ec.first_name, ec.last_name, ec.job_title,
                       ec.source as extraction_source, ec.created_at as extracted_at,
                       dc.domain, dc.name as company_name,
                       dc.apollo_enriched_at, dc.url as company_url,
                       sr.matched_segment,
                       sj.id as search_job_id, sj.config as job_config,
                       sq.query_text, sq.geo
                FROM extracted_contacts ec
                JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
                LEFT JOIN search_results sr ON dc.search_result_id = sr.id
                LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
                LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
                WHERE dc.project_id = :pid AND dc.company_id = :cid
                AND dc.is_target = true
                AND ec.email IS NOT NULL AND ec.email != ''
                ORDER BY ec.id
            """), {"pid": project_id, "cid": company_id})
            contacts = rows.fetchall()

        if not contacts:
            logger.info(f"CRM promote: no extracted contacts for project {project_id}")
            return

        logger.info(f"CRM promote: processing {len(contacts)} extracted contacts for project {project_id}")

        for contact in contacts:
            if not is_valid_email(contact.email):
                stats["skipped_invalid"] += 1
                continue

            try:
                # Build gathering_details JSON
                gathering = {}
                if getattr(contact, "extracted_at", None):
                    gathering["gathered_at"] = contact.extracted_at.isoformat() if hasattr(contact.extracted_at, 'isoformat') else str(contact.extracted_at)
                if getattr(contact, "extraction_source", None):
                    gathering["source"] = str(contact.extraction_source)
                if getattr(contact, "search_job_id", None):
                    gathering["search_job_id"] = contact.search_job_id
                if getattr(contact, "query_text", None):
                    gathering["query"] = contact.query_text
                if getattr(contact, "geo", None):
                    gathering["geo"] = contact.geo
                if getattr(contact, "domain", None):
                    gathering["domain"] = contact.domain
                if getattr(contact, "apollo_enriched_at", None):
                    gathering["apollo_enriched"] = True

                seg = getattr(contact, "matched_segment", None) or None
                if seg:
                    gathering["segment"] = seg

                gathering_json = _json.dumps(gathering) if gathering else None

                # Use a fresh session per contact to avoid cascading transaction errors
                async with async_session_maker() as session:
                    # Check if contact already exists in CRM
                    existing = await session.execute(sql_text("""
                        SELECT id, project_id, segment, company_name, job_title, gathering_details
                        FROM contacts
                        WHERE company_id = :cid AND lower(email) = lower(:email)
                        AND deleted_at IS NULL
                        LIMIT 1
                    """), {"cid": company_id, "email": contact.email})
                    row = existing.fetchone()

                    if row:
                        # Update existing — fill NULL fields only
                        needs_update = (
                            row.project_id is None or row.segment is None
                            or row.company_name is None or row.job_title is None
                            or row.gathering_details is None
                        )
                        if needs_update:
                            await session.execute(sql_text("""
                                UPDATE contacts SET
                                    project_id = COALESCE(project_id, :project_id),
                                    segment = COALESCE(segment, :segment),
                                    company_name = COALESCE(company_name, :company_name),
                                    job_title = COALESCE(job_title, :job_title),
                                    gathering_details = COALESCE(gathering_details, CAST(:gathering AS jsonb)),
                                    updated_at = NOW()
                                WHERE id = :id
                            """), {
                                "id": row.id,
                                "project_id": project_id,
                                "segment": seg,
                                "company_name": contact.company_name or None,
                                "job_title": contact.job_title or None,
                                "gathering": gathering_json,
                            })
                            stats["updated"] += 1
                    else:
                        # Insert new contact
                        domain = contact.email.split("@")[-1] if "@" in contact.email else None
                        await session.execute(sql_text("""
                            INSERT INTO contacts (company_id, email, first_name, last_name, domain,
                                                  company_name, job_title, project_id, segment,
                                                  source, status, is_active, gathering_details,
                                                  created_at, updated_at)
                            VALUES (:cid, :email, :fname, :lname, :domain,
                                    :company_name, :job_title, :project_id, :segment,
                                    'pipeline', 'lead', true, CAST(:gathering AS jsonb), NOW(), NOW())
                        """), {
                            "cid": company_id, "email": contact.email,
                            "fname": contact.first_name or "", "lname": contact.last_name or "",
                            "domain": domain,
                            "company_name": contact.company_name or "",
                            "job_title": contact.job_title or "",
                            "project_id": project_id,
                            "segment": seg,
                            "gathering": gathering_json,
                        })
                        stats["inserted"] += 1
                    await session.commit()
            except Exception as e:
                logger.warning(f"CRM promote error for {contact.email}: {e}")
                stats["errors"] += 1

        progress["crm_promote_stats"] = stats
        logger.info(f"CRM promote done for project {project_id}: {stats}")

    except Exception as e:
        logger.error(f"CRM promote phase failed for project {project_id}: {e}", exc_info=True)
        stats["errors"] += 1
        progress["crm_promote_stats"] = stats


async def _ensure_campaign_for_rule(
    client,  # unused now, kept for signature compat
    api_key: str,
    rule: "CampaignPushRule",
    contacts_count: int,
    session=None,
) -> Optional[str]:
    """
    Get existing SmartLead campaign for a push rule.
    No campaign creation — campaigns are set up manually in SmartLead,
    and the rule just points to them via current_campaign_id.
    """
    from app.services.smartlead_service import smartlead_request as _sl_req

    if not rule.current_campaign_id:
        logger.warning(
            f"Rule '{rule.name}' has no current_campaign_id set. "
            f"Set campaign_id in the push rule to use an existing SmartLead campaign."
        )
        return None

    try:
        resp = await _sl_req(
            "GET",
            f"https://server.smartlead.ai/api/v1/campaigns/{rule.current_campaign_id}",
            params={"api_key": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            campaign_name = data.get("name", "unknown")
            logger.info(
                f"Using existing campaign '{campaign_name}' (ID: {rule.current_campaign_id}) "
                f"for rule '{rule.name}'"
            )
            return rule.current_campaign_id
        else:
            logger.error(
                f"Campaign {rule.current_campaign_id} not found in SmartLead "
                f"(status {resp.status_code}). Fix the push rule."
            )
            return None
    except Exception as e:
        logger.error(f"Failed to verify campaign {rule.current_campaign_id}: {e}")
        # Still return the campaign_id — we trust the user set it correctly
        return rule.current_campaign_id


# ============ Projects (for dropdown) ============

@router.get("/projects")
async def list_pipeline_projects(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List projects that have discovered companies (fast, for dropdown)."""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT DISTINCT dc.project_id as id, p.name
        FROM discovered_companies dc
        JOIN projects p ON p.id = dc.project_id
        WHERE dc.company_id = :company_id
        ORDER BY p.name
    """), {"company_id": company.id})
    return [{"id": row.id, "name": row.name} for row in result.fetchall()]


# ============ Campaign Push Rules CRUD ============

class PushRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    language: str = "any"  # "ru", "en", "any"
    has_first_name: Optional[bool] = None
    name_pattern: Optional[str] = None
    campaign_name_template: str
    sequence_language: str = "ru"
    sequence_template: Optional[list] = None
    use_first_name_var: bool = True
    email_account_ids: Optional[list] = None
    schedule_config: Optional[dict] = None
    campaign_settings: Optional[dict] = None
    max_leads_per_campaign: int = 500
    priority: int = 0
    is_active: bool = True


class PushRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    has_first_name: Optional[bool] = None
    name_pattern: Optional[str] = None
    campaign_name_template: Optional[str] = None
    sequence_language: Optional[str] = None
    sequence_template: Optional[list] = None
    use_first_name_var: Optional[bool] = None
    email_account_ids: Optional[list] = None
    schedule_config: Optional[dict] = None
    campaign_settings: Optional[dict] = None
    max_leads_per_campaign: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/projects/{project_id}/push-rules")
async def list_push_rules(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List campaign push rules for a project."""
    from app.models.pipeline import CampaignPushRule
    result = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.project_id == project_id,
            CampaignPushRule.company_id == company.id,
        ).order_by(CampaignPushRule.priority.desc(), CampaignPushRule.id)
    )
    rules = result.scalars().all()
    return [_rule_to_dict(r) for r in rules]


@router.post("/projects/{project_id}/push-rules")
async def create_push_rule(
    project_id: int,
    body: PushRuleCreate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Create a new campaign push rule."""
    from app.models.pipeline import CampaignPushRule
    rule = CampaignPushRule(
        company_id=company.id,
        project_id=project_id,
        **body.model_dump(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.put("/push-rules/{rule_id}")
async def update_push_rule(
    rule_id: int,
    body: PushRuleUpdate,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update a campaign push rule."""
    from app.models.pipeline import CampaignPushRule
    result = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.id == rule_id,
            CampaignPushRule.company_id == company.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/push-rules/{rule_id}")
async def delete_push_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete a campaign push rule."""
    from app.models.pipeline import CampaignPushRule
    result = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.id == rule_id,
            CampaignPushRule.company_id == company.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "id": rule_id}


@router.post("/projects/{project_id}/push-to-smartlead")
async def push_to_smartlead(
    project_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run SmartLead push phase only (Phase 4) as a standalone action."""
    if project_id in _running_pipelines and _running_pipelines[project_id].get("running"):
        return {"status": "already_running", "progress": _running_pipelines[project_id]}

    _running_pipelines[project_id] = {
        "running": True,
        "phase": "smartlead_push",
        "started_at": datetime.utcnow().isoformat(),
        "config": {"standalone_push": True},
    }

    async def run_push():
        progress = _running_pipelines[project_id]
        try:
            await _bg_phase_smartlead_push(project_id, company.id, progress)
            # Also auto-promote all target contacts to CRM
            progress["phase"] = "crm_promote"
            await _bg_phase_crm_promote(project_id, company.id, progress)
            progress.update({"running": False, "phase": "completed", "completed_at": datetime.utcnow().isoformat()})
        except Exception as e:
            logger.error(f"SmartLead push crashed: {e}", exc_info=True)
            progress.update({"running": False, "phase": "error", "error": str(e)[:500]})

    background_tasks.add_task(run_push)
    return {"status": "started", "project_id": project_id}


@router.get("/smartlead/email-accounts")
async def list_smartlead_email_accounts(
    company: Company = Depends(get_required_company),
):
    """List available SmartLead email accounts for rule configuration."""
    from app.services.smartlead_service import smartlead_request as _sl_req
    api_key = settings.SMARTLEAD_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="SmartLead API key not configured")

    resp = await _sl_req(
        "GET", "https://server.smartlead.ai/api/v1/email-accounts",
        params={"api_key": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch email accounts")
    accounts = resp.json()

    return [
        {
            "id": acc.get("id"),
            "email": acc.get("from_email", acc.get("email", "")),
            "name": acc.get("from_name", ""),
        }
        for acc in (accounts if isinstance(accounts, list) else [])
    ]


def _rule_to_dict(rule) -> dict:
    return {
        "id": rule.id,
        "project_id": rule.project_id,
        "name": rule.name,
        "description": rule.description,
        "language": rule.language,
        "has_first_name": rule.has_first_name,
        "name_pattern": rule.name_pattern,
        "campaign_name_template": rule.campaign_name_template,
        "sequence_language": rule.sequence_language,
        "sequence_template": rule.sequence_template,
        "use_first_name_var": rule.use_first_name_var,
        "email_account_ids": rule.email_account_ids,
        "schedule_config": rule.schedule_config,
        "campaign_settings": rule.campaign_settings,
        "max_leads_per_campaign": rule.max_leads_per_campaign,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "current_campaign_id": rule.current_campaign_id,
        "current_campaign_lead_count": rule.current_campaign_lead_count,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


# ============ Push History / Tracker ============

@router.get("/projects/{project_id}/push-history")
async def get_push_history(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get SmartLead push history for a project — campaigns created,
    leads pushed, dates, and rule used. Used by the tracker UI.
    """
    from sqlalchemy import text as sql_text

    # Get push events from pipeline_events
    events = await db.execute(sql_text("""
        SELECT pe.id, pe.event_type, pe.detail, pe.created_at
        FROM pipeline_events pe
        WHERE pe.company_id = :cid
        AND pe.event_type IN ('smartlead_campaign_created', 'smartlead_leads_pushed')
        ORDER BY pe.created_at DESC
        LIMIT 200
    """), {"cid": company.id})
    event_rows = events.fetchall()

    # Get contacts pushed per day from contacts table
    daily = await db.execute(sql_text("""
        SELECT DATE(created_at) as push_date,
               COUNT(*) as count,
               source
        FROM contacts
        WHERE company_id = :cid
        AND source LIKE 'smartlead%%'
        GROUP BY DATE(created_at), source
        ORDER BY push_date DESC
        LIMIT 90
    """), {"cid": company.id})
    daily_rows = daily.fetchall()

    # Get push rules with current campaign stats
    from app.models.pipeline import CampaignPushRule
    rules = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.project_id == project_id,
            CampaignPushRule.company_id == company.id,
        )
    )
    rule_list = rules.scalars().all()

    # Aggregate campaigns from SmartLead events
    campaigns = {}
    for row in event_rows:
        detail = row.detail or {}
        campaign_id = detail.get("campaign_id", "")
        if not campaign_id:
            continue
        if campaign_id not in campaigns:
            campaigns[campaign_id] = {
                "campaign_id": campaign_id,
                "campaign_name": detail.get("campaign_name", ""),
                "rule_name": detail.get("rule_name", ""),
                "leads_pushed": 0,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        if row.event_type == "smartlead_leads_pushed":
            # Support both old format (leads_pushed) and new format (leads_uploaded)
            campaigns[campaign_id]["leads_pushed"] += detail.get("leads_uploaded", detail.get("leads_pushed", 0))

    return {
        "campaigns": list(campaigns.values()),
        "daily_pushes": [
            {
                "date": str(row.push_date),
                "count": row.count,
                "source": row.source,
            }
            for row in daily_rows
        ],
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "current_campaign_id": r.current_campaign_id,
                "current_campaign_lead_count": r.current_campaign_lead_count or 0,
                "is_active": r.is_active,
            }
            for r in rule_list
        ],
        "total_pushed": sum(row.count for row in daily_rows if 'push' in (row.source or '')),
        "total_synced": sum(row.count for row in daily_rows if 'sync' in (row.source or '')),
    }


@router.get("/projects/{project_id}/push-history-detail")
async def get_push_history_detail(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Detailed push history — every push event with segment/geo/query breakdown.
    Returns a flat list of push batches suitable for a table view.
    """
    from sqlalchemy import text as sql_text

    # 1. Get all push events for this project
    events = await db.execute(sql_text("""
        SELECT pe.id, pe.detail, pe.created_at
        FROM pipeline_events pe
        WHERE pe.company_id = :cid
        AND pe.event_type::text = 'smartlead_leads_pushed'
        ORDER BY pe.created_at DESC
        LIMIT 500
    """), {"cid": company.id})
    event_rows = events.fetchall()

    # 2. For each push event, get segment/geo breakdown from contacts
    pushes = []
    for row in event_rows:
        detail = row.detail or {}
        campaign_id = detail.get("campaign_id", "")
        if not campaign_id:
            continue

        # Get segment/geo breakdown for contacts pushed to this campaign
        # that were created around the same time as the push event
        breakdown = await db.execute(sql_text("""
            SELECT
                c.gathering_details->>'segment' as segment,
                c.gathering_details->>'geo' as geo,
                c.gathering_details->>'query' as sample_query,
                c.gathering_details->>'source' as extraction_source,
                COUNT(*) as contact_count
            FROM contacts c
            WHERE c.company_id = :cid
            AND c.project_id = :pid
            AND c.campaigns::text ILIKE :camp_pattern
            AND c.gathering_details IS NOT NULL
            GROUP BY 1, 2, 3, 4
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """), {
            "cid": company.id,
            "pid": project_id,
            "camp_pattern": f"%{campaign_id}%",
        })
        segments = []
        for seg_row in breakdown.fetchall():
            segments.append({
                "segment": seg_row.segment,
                "geo": seg_row.geo,
                "sample_query": (seg_row.sample_query or "")[:80],
                "extraction_source": seg_row.extraction_source,
                "count": seg_row.contact_count,
            })

        # Get campaign name from contacts
        camp_name_row = await db.execute(sql_text("""
            SELECT c.campaigns::text
            FROM contacts c
            WHERE c.company_id = :cid
            AND c.campaigns::text ILIKE :camp_pattern
            LIMIT 1
        """), {"cid": company.id, "camp_pattern": f"%{campaign_id}%"})
        camp_name_raw = camp_name_row.scalar()
        campaign_name = ""
        if camp_name_raw:
            import json as _json
            try:
                camps = _json.loads(camp_name_raw)
                for cp in (camps if isinstance(camps, list) else []):
                    if str(cp.get("id", "")) == str(campaign_id):
                        campaign_name = cp.get("name", "")
                        break
            except Exception:
                pass

        pushes.append({
            "id": row.id,
            "date": row.created_at.isoformat() if row.created_at else None,
            "rule_name": detail.get("rule_name", ""),
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "leads_sent": detail.get("leads_sent", 0),
            "leads_uploaded": detail.get("leads_uploaded", 0),
            "leads_duplicate": detail.get("leads_duplicate", 0),
            "leads_invalid": detail.get("leads_invalid", 0),
            "segments": segments,
        })

    # 3. Summary
    total_sent = sum(p.get("leads_sent", 0) or 0 for p in pushes)
    total_uploaded = sum(p.get("leads_uploaded", 0) or 0 for p in pushes)
    total_dupes = sum(p.get("leads_duplicate", 0) or 0 for p in pushes)

    return {
        "pushes": pushes,
        "summary": {
            "total_pushes": len(pushes),
            "total_sent": total_sent,
            "total_uploaded": total_uploaded,
            "total_duplicates": total_dupes,
        },
    }


# ============ SmartLead Push Verification ============

@router.get("/projects/{project_id}/verify-smartlead-push")
async def verify_smartlead_push(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Verify leads actually arrived in SmartLead campaigns.
    Uses campaign analytics for total counts + per-email spot-checks.
    Also reports how many DB contacts match each rule.
    """
    import random
    from sqlalchemy import text as sql_text
    from app.models.pipeline import CampaignPushRule
    from app.services.smartlead_service import smartlead_service

    # Get active rules with campaign IDs
    result = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.project_id == project_id,
            CampaignPushRule.company_id == company.id,
            CampaignPushRule.current_campaign_id.isnot(None),
            CampaignPushRule.is_active == True,
        )
    )
    rules = result.scalars().all()

    verifications = []
    for rule in rules:
        campaign_id = rule.current_campaign_id
        db_pushed_count = rule.current_campaign_lead_count or 0
        sl_total = None
        spot_check = {"checked": 0, "found": 0, "missing_emails": []}
        status = "unknown"

        # --- Step 1: Get total lead count from SmartLead campaign analytics ---
        try:
            stats_data = await smartlead_service.get_campaign_statistics(campaign_id)
            # Analytics returns various stats; look for total leads
            if isinstance(stats_data, dict):
                # Try common keys returned by SmartLead analytics
                sl_total = (
                    stats_data.get("total_leads")
                    or stats_data.get("total_lead_count")
                    or stats_data.get("totalCount")
                )
            # Fallback: use get_campaign to check lead count
            if sl_total is None:
                campaign_data = await smartlead_service.get_campaign(campaign_id)
                if isinstance(campaign_data, dict):
                    sl_total = campaign_data.get("lead_count", campaign_data.get("total_leads"))
        except Exception as e:
            status = f"error_count: {str(e)[:100]}"

        # --- Step 2: Per-email spot-check (up to 5 random contacts) ---
        try:
            # Get emails that were pushed to this campaign from our DB
            email_rows = await db.execute(sql_text("""
                SELECT email FROM contacts
                WHERE project_id = :pid AND company_id = :cid
                AND campaigns::text ILIKE :campaign_pattern
                AND email IS NOT NULL
                LIMIT 50
            """), {
                "pid": project_id,
                "cid": company.id,
                "campaign_pattern": f"%{campaign_id}%",
            })
            pushed_emails = [r[0] for r in email_rows.fetchall()]

            if pushed_emails:
                sample = random.sample(pushed_emails, min(5, len(pushed_emails)))
                for email in sample:
                    spot_check["checked"] += 1
                    try:
                        lead = await smartlead_service.get_lead_by_email(campaign_id, email)
                        if lead:
                            spot_check["found"] += 1
                        else:
                            spot_check["missing_emails"].append(email)
                    except Exception:
                        spot_check["missing_emails"].append(email)
        except Exception as e:
            spot_check["error"] = str(e)[:100]

        # --- Step 3: Count DB contacts matching this campaign ---
        try:
            db_count_row = await db.execute(sql_text("""
                SELECT COUNT(*) FROM contacts
                WHERE project_id = :pid AND company_id = :cid
                AND campaigns::text ILIKE :campaign_pattern
            """), {
                "pid": project_id,
                "cid": company.id,
                "campaign_pattern": f"%{campaign_id}%",
            })
            db_campaign_count = db_count_row.scalar() or 0
        except Exception:
            db_campaign_count = None

        # --- Determine status ---
        if "error" not in status:
            if sl_total is not None:
                if sl_total == 0 and db_pushed_count > 0:
                    status = "EMPTY - leads did not arrive"
                elif spot_check["checked"] > 0 and spot_check["found"] < spot_check["checked"]:
                    status = f"PARTIAL - {spot_check['found']}/{spot_check['checked']} spot-check passed"
                else:
                    status = "OK"
            else:
                status = "UNKNOWN - could not get SmartLead count"

        verifications.append({
            "rule_name": rule.name,
            "rule_id": rule.id,
            "campaign_id": campaign_id,
            "db_pushed_count": db_pushed_count,
            "db_campaign_contacts": db_campaign_count,
            "smartlead_total": sl_total,
            "spot_check": spot_check,
            "status": status,
        })

    return {
        "project_id": project_id,
        "verifications": verifications,
        "summary": {
            "total_rules": len(verifications),
            "ok": sum(1 for v in verifications if v["status"] == "OK"),
            "issues": sum(1 for v in verifications if v["status"] != "OK"),
        },
    }


# ============ Gemini Sequence Generation ============

class GenerateSequencesRequest(BaseModel):
    project_id: int
    language: str = "ru"  # "ru" or "en"
    use_first_name: bool = True
    tone: str = "professional"  # "professional", "friendly", "casual"
    num_steps: int = 3
    custom_instructions: Optional[str] = None


@router.post("/generate-sequences")
async def generate_sequences(
    body: GenerateSequencesRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Generate email sequences using Gemini 2.5 Pro, with project context from knowledge base."""
    from app.models.contact import Project
    from app.models.knowledge_base import Product, Segment, CompanyProfile
    from app.services.gemini_client import gemini_generate, extract_json_from_gemini, is_gemini_available
    import json as json_module

    if not is_gemini_available():
        raise HTTPException(status_code=400, detail="Gemini API key not configured")

    # Load project
    result = await db.execute(
        select(Project).where(Project.id == body.project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load KB context
    products = await db.execute(select(Product).where(Product.company_id == company.id).limit(5))
    products_list = products.scalars().all()
    segments = await db.execute(select(Segment).where(Segment.company_id == company.id).limit(5))
    segments_list = segments.scalars().all()
    profile = await db.execute(select(CompanyProfile).where(CompanyProfile.company_id == company.id))
    company_profile = profile.scalar_one_or_none()

    # Build context
    context_parts = []
    if company_profile:
        context_parts.append(f"Company: {company_profile.name or ''}\nDescription: {company_profile.description or ''}\nValue proposition: {company_profile.value_proposition or ''}")
    if products_list:
        context_parts.append("Products/Services:\n" + "\n".join(f"- {p.name}: {p.description or ''}" for p in products_list))
    if segments_list:
        context_parts.append("Target Segments:\n" + "\n".join(f"- {s.name}: {s.description or ''}" for s in segments_list))
    context_parts.append(f"Project: {project.name}\nTarget segments: {project.target_segments or ''}")

    context = "\n\n".join(context_parts)

    lang_name = "Russian" if body.language == "ru" else "English"
    first_name_note = "Use {{first_name}} placeholder for personalization." if body.use_first_name else "Do NOT use {{first_name}} — these emails go to generic addresses (info@, contact@). Use formal greetings without names."

    system_prompt = f"""You are an expert cold email copywriter. Generate a {body.num_steps}-step email sequence for B2B outreach.

Requirements:
- Language: {lang_name}
- Tone: {body.tone}
- {first_name_note}
- Each step should be concise (2-4 sentences for the body)
- First email introduces the value proposition
- Follow-ups are shorter and reference the previous email
- Use HTML formatting (wrap paragraphs in <p> tags)
- Return ONLY a JSON array

Output format (strict JSON array):
[
  {{
    "seq_number": 1,
    "seq_delay_details": {{"delay_in_days": 0}},
    "subject": "...",
    "email_body": "<p>...</p><p>...</p>"
  }},
  {{
    "seq_number": 2,
    "seq_delay_details": {{"delay_in_days": 3}},
    "subject": "Re: ...",
    "email_body": "<p>...</p>"
  }}
]"""

    user_prompt = f"""Company and product context:
{context}

{f'Additional instructions: {body.custom_instructions}' if body.custom_instructions else ''}

Generate the {body.num_steps}-step email sequence now."""

    try:
        result = await gemini_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=4000,
            model="gemini-2.5-pro",
        )

        raw = extract_json_from_gemini(result["content"])
        sequences = json_module.loads(raw)

        return {
            "sequences": sequences,
            "language": body.language,
            "use_first_name": body.use_first_name,
            "tokens": result.get("tokens"),
        }

    except json_module.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini sequence output: {e}")
        raise HTTPException(status_code=502, detail="AI generated invalid JSON. Try again.")
    except Exception as e:
        logger.error(f"Gemini sequence generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)[:200]}")


# ============ Discovered Companies ============

@router.get("/discovered-companies")
async def list_discovered_companies(
    project_id: Optional[int] = QueryParam(None),
    status: Optional[str] = QueryParam(None),
    is_target: Optional[bool] = QueryParam(None),
    search: Optional[str] = QueryParam(None),
    sort_by: Optional[str] = QueryParam(None),
    sort_order: Optional[str] = QueryParam("desc"),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List discovered companies with filters."""
    result = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=project_id,
        status=status,
        is_target=is_target,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [DiscoveredCompanyResponse.model_validate(item) for item in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get("/discovered-companies/{discovered_company_id}", response_model=DiscoveredCompanyDetail)
async def get_discovered_company(
    discovered_company_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get discovered company detail with contacts and events."""
    dc = await pipeline_service.get_discovered_company_detail(
        session=db,
        company_id=company.id,
        discovered_company_id=discovered_company_id,
    )
    if not dc:
        raise HTTPException(status_code=404, detail="Discovered company not found")

    return DiscoveredCompanyDetail.model_validate(dc)


# ============ Contact Extraction ============

@router.post("/extract-contacts")
async def extract_contacts(
    body: ExtractContactsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run GPT contact extraction on selected discovered companies."""
    stats = await pipeline_service.extract_contacts_batch(
        session=db,
        discovered_company_ids=body.discovered_company_ids,
        company_id=company.id,
    )
    return stats


# ============ Apollo Enrichment ============

# Only allow Apollo enrichment for these projects (to limit credit usage)
APOLLO_ALLOWED_PROJECTS = {"archistruct", "deliryo"}


@router.post("/enrich-apollo")
async def enrich_apollo(
    body: ApolloEnrichRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run Apollo enrichment on selected discovered companies."""
    from app.models.pipeline import DiscoveredCompany
    from app.models.contact import Project
    from sqlalchemy import select

    # Check that all selected companies belong to allowed projects
    result = await db.execute(
        select(DiscoveredCompany.project_id)
        .where(DiscoveredCompany.id.in_(body.discovered_company_ids))
        .distinct()
    )
    project_ids = [row[0] for row in result.fetchall()]

    proj_result = await db.execute(
        select(Project.id, Project.name).where(Project.id.in_(project_ids))
    )
    proj_names = {row.id: row.name for row in proj_result.fetchall()}

    blocked = [name for pid, name in proj_names.items() if name.lower() not in APOLLO_ALLOWED_PROJECTS]
    if blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Apollo enrichment is restricted to archistruct and deliryo projects. Blocked: {', '.join(blocked)}",
        )

    stats = await pipeline_service.enrich_apollo_batch(
        session=db,
        discovered_company_ids=body.discovered_company_ids,
        company_id=company.id,
        max_people=body.max_people,
        titles=body.titles,
        max_credits=body.max_credits,
    )
    return stats


@router.post("/enrich-project/{project_id}")
async def enrich_project_apollo(
    project_id: int,
    body: ProjectEnrichRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Server-side Apollo enrichment for an entire project — no pagination gap.

    Queries ALL unenriched target companies server-side, batches internally,
    enforces credit budget, and returns total stats.
    """
    from app.models.pipeline import DiscoveredCompany
    from app.models.contact import Project
    from sqlalchemy import select

    # Verify project belongs to allowed projects
    proj = await db.execute(select(Project).where(Project.id == project_id))
    project = proj.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.name.lower() not in APOLLO_ALLOWED_PROJECTS:
        raise HTTPException(
            status_code=400,
            detail=f"Apollo enrichment is restricted to {', '.join(APOLLO_ALLOWED_PROJECTS)}. Project: {project.name}",
        )

    # Query ALL unenriched targets — server-side, no pagination gap
    result = await db.execute(
        select(DiscoveredCompany.id).where(
            DiscoveredCompany.project_id == project_id,
            DiscoveredCompany.company_id == company.id,
            DiscoveredCompany.is_target == True,
            DiscoveredCompany.apollo_enriched_at.is_(None),
        ).order_by(DiscoveredCompany.confidence.desc())
    )
    all_ids = [r[0] for r in result.fetchall()]

    if not all_ids:
        return {"processed": 0, "people_found": 0, "errors": 0, "credits_used": 0, "skipped": 0,
                "total_unenriched": 0, "message": "All targets already enriched"}

    logger.info(f"Project {project_id} ({project.name}): {len(all_ids)} unenriched targets, "
                f"max_credits={body.max_credits}, max_people={body.max_people}")

    # Process in batches of 10 server-side
    BATCH_SIZE = 10
    total_stats = {"processed": 0, "people_found": 0, "errors": 0, "credits_used": 0, "skipped": 0,
                   "total_unenriched": len(all_ids)}

    for i in range(0, len(all_ids), BATCH_SIZE):
        batch_ids = all_ids[i:i + BATCH_SIZE]

        # Check remaining credit budget
        remaining_credits = None
        if body.max_credits is not None:
            remaining_credits = body.max_credits - total_stats["credits_used"]
            if remaining_credits <= 0:
                logger.info(f"Credit budget exhausted ({body.max_credits}), stopping at batch {i // BATCH_SIZE + 1}")
                break

        batch_stats = await pipeline_service.enrich_apollo_batch(
            session=db,
            discovered_company_ids=batch_ids,
            company_id=company.id,
            max_people=body.max_people,
            titles=body.titles,
            max_credits=remaining_credits,
        )

        total_stats["processed"] += batch_stats.get("processed", 0)
        total_stats["people_found"] += batch_stats.get("people_found", 0)
        total_stats["errors"] += batch_stats.get("errors", 0)
        total_stats["credits_used"] += batch_stats.get("credits_used", 0)
        total_stats["skipped"] += batch_stats.get("skipped", 0)

    logger.info(f"Project {project_id} enrichment complete: {total_stats}")
    return total_stats


# ============ Promote to CRM ============

@router.post("/promote-to-crm")
async def promote_to_crm(
    body: PromoteToContactsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Promote extracted contacts to CRM Contact records."""
    stats = await pipeline_service.promote_to_crm(
        session=db,
        extracted_contact_ids=body.extracted_contact_ids,
        company_id=company.id,
        project_id=body.project_id,
        segment=body.segment,
    )
    return stats


# ============ Enrichment Tracking ============

@router.get("/enrichment/stats")
async def get_enrichment_stats(
    project_id: int = QueryParam(...),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get enrichment effectiveness stats by source for a project."""
    from app.services.enrichment_intelligence_service import enrichment_intelligence_service
    stats = await enrichment_intelligence_service.get_effectiveness_stats(db, project_id)
    return {"project_id": project_id, "stats": stats}


@router.get("/enrichment/history/{dc_id}")
async def get_enrichment_history(
    dc_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get all enrichment attempts for a discovered company."""
    from app.models.pipeline import DiscoveredCompany, EnrichmentAttempt
    from app.services.enrichment_intelligence_service import enrichment_intelligence_service

    # Verify company access
    dc = await db.execute(
        select(DiscoveredCompany).where(
            DiscoveredCompany.id == dc_id,
            DiscoveredCompany.company_id == company.id,
        )
    )
    if not dc.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Discovered company not found")

    attempts = await enrichment_intelligence_service.get_attempts_for_company(db, dc_id)
    return {
        "discovered_company_id": dc_id,
        "attempts": [
            {
                "id": a.id,
                "source_type": a.source_type,
                "method": a.method,
                "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None,
                "credits_used": a.credits_used or 0,
                "cost_usd": float(a.cost_usd) if a.cost_usd else 0.0,
                "contacts_found": a.contacts_found or 0,
                "emails_found": a.emails_found or 0,
                "status": a.status,
                "error_message": a.error_message,
                "config": a.config,
                "result_summary": a.result_summary,
            }
            for a in attempts
        ],
    }


@router.post("/enrichment/retry")
async def retry_enrichment(
    body: dict,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Retry enrichment with a different strategy.

    Body: {discovered_company_ids, source_type, max_people, titles, max_credits}
    """
    dc_ids = body.get("discovered_company_ids", [])
    source_type = body.get("source_type", "APOLLO_PEOPLE")
    if not dc_ids:
        raise HTTPException(status_code=400, detail="discovered_company_ids required")

    if source_type == "APOLLO_PEOPLE":
        stats = await pipeline_service.enrich_apollo_batch(
            session=db,
            discovered_company_ids=dc_ids,
            company_id=company.id,
            max_people=body.get("max_people", 5),
            titles=body.get("titles"),
            max_credits=body.get("max_credits", 50),
            force_retry=True,
        )
        return stats
    elif source_type in ("WEBSITE_SCRAPE", "SUBPAGE_SCRAPE"):
        stats = await pipeline_service.extract_contacts_batch(
            session=db,
            discovered_company_ids=dc_ids,
            company_id=company.id,
        )
        return stats
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type: {source_type}")


@router.post("/enrichment/recompute/{project_id}")
async def recompute_enrichment_effectiveness(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Recompute enrichment effectiveness stats from attempt history."""
    from app.services.enrichment_intelligence_service import enrichment_intelligence_service
    await enrichment_intelligence_service.update_effectiveness(db, project_id)
    await db.commit()
    stats = await enrichment_intelligence_service.get_effectiveness_stats(db, project_id)
    return {"project_id": project_id, "recomputed": True, "stats": stats}


@router.get("/enrichment/recommend/{project_id}")
async def recommend_enrichment_strategy(
    project_id: int,
    segment: Optional[str] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get recommended enrichment strategy based on historical effectiveness."""
    from app.services.enrichment_intelligence_service import enrichment_intelligence_service
    strategy = await enrichment_intelligence_service.recommend_strategy(db, project_id, segment)
    return {"project_id": project_id, "segment": segment, "strategy": strategy}


# ============ Pipeline Stats ============

@router.get("/stats", response_model=PipelineStats)
async def get_pipeline_stats(
    project_id: Optional[int] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get pipeline stats for a project, including spending when project_id provided."""
    stats = await pipeline_service.get_pipeline_stats(
        session=db,
        company_id=company.id,
        project_id=project_id,
    )

    spending = None
    if project_id:
        try:
            from app.services.company_search_service import company_search_service
            raw = await company_search_service.get_project_spending(db, project_id)

            # Count actual Apollo credits used (not people count)
            from sqlalchemy import select, func
            from app.models.pipeline import DiscoveredCompany
            apollo_q = await db.execute(
                select(func.coalesce(func.sum(DiscoveredCompany.apollo_credits_used), 0))
                .where(
                    DiscoveredCompany.company_id == company.id,
                    DiscoveredCompany.project_id == project_id,
                )
            )
            apollo_credits = apollo_q.scalar() or 0
            apollo_cost = apollo_credits * 0.01  # ~$0.01 per Apollo credit

            spending = SpendingDetail(
                yandex_cost=raw.get("yandex_cost", 0),
                google_cost=raw.get("google_cost", 0),
                openai_cost_estimate=raw.get("openai_cost_estimate", 0),
                gemini_cost_estimate=raw.get("gemini_cost_estimate", 0),
                ai_cost_estimate=raw.get("ai_cost_estimate", 0),
                crona_cost=raw.get("crona_cost", 0),
                apollo_credits_used=apollo_credits,
                apollo_cost_estimate=round(apollo_cost, 4),
                total_estimate=round(raw.get("total_estimate", 0) + apollo_cost, 4),
            )
        except Exception as e:
            logger.warning(f"Failed to get spending for project {project_id}: {e}")

    return PipelineStats(**stats, spending=spending)


# ============ Cost Breakdown ============

@router.get("/cost-breakdown/{project_id}")
async def get_cost_breakdown(
    project_id: int,
    pipeline_run_id: Optional[int] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get detailed cost breakdown from cost_events table."""
    from app.services.cost_service import cost_service
    return await cost_service.get_spending_breakdown(db, project_id, pipeline_run_id)


@router.get("/pipeline-runs/{project_id}")
async def list_pipeline_runs(
    project_id: int,
    limit: int = QueryParam(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List pipeline runs for a project."""
    from app.models.pipeline_run import PipelineRun
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.project_id == project_id, PipelineRun.company_id == company.id)
        .order_by(PipelineRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "status": r.status.value,
            "current_phase": r.current_phase.value if r.current_phase else None,
            "total_cost_usd": float(r.total_cost_usd or 0),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        }
        for r in runs
    ]


# ============ Bulk Status Update ============

@router.post("/update-status")
async def update_status(
    body: BulkStatusUpdateRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Bulk update status for discovered companies."""
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select

    result = await db.execute(
        select(DiscoveredCompany).where(
            DiscoveredCompany.id.in_(body.discovered_company_ids),
            DiscoveredCompany.company_id == company.id,
        )
    )
    companies = result.scalars().all()

    updated = 0
    for dc in companies:
        dc.status = DiscoveredCompanyStatus(body.status.value.upper())
        updated += 1

    await db.commit()
    return {"updated": updated}


# ============ Export ============

@router.get("/export-csv")
async def export_csv(
    project_id: Optional[int] = QueryParam(None),
    is_target: Optional[bool] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export discovered companies as CSV."""
    data = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=project_id,
        is_target=is_target,
        page=1,
        page_size=10000,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Domain", "Company Name", "Is Target", "Confidence", "Status",
        "Reasoning", "Services", "Location", "Industry",
        "Contacts Count", "Emails", "Phones", "Apollo People",
    ])

    for dc in data["items"]:
        info = dc.company_info or {}
        services = ", ".join(info.get("services", [])) if info.get("services") else ""
        emails = ", ".join(dc.emails_found or [])
        phones = ", ".join(dc.phones_found or [])

        writer.writerow([
            dc.domain,
            dc.name or info.get("name", ""),
            "Yes" if dc.is_target else "No",
            f"{(dc.confidence or 0) * 100:.0f}%",
            dc.status.value if hasattr(dc.status, 'value') else str(dc.status),
            dc.reasoning or "",
            services,
            info.get("location", ""),
            info.get("industry", ""),
            dc.contacts_count or 0,
            emails,
            phones,
            dc.apollo_people_count or 0,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pipeline_companies.csv"},
    )


@router.post("/export-sheet", response_model=PipelineExportSheetResponse)
async def export_google_sheet(
    body: PipelineExportSheetRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export discovered companies to a new Google Sheet."""
    from app.services.google_sheets_service import GoogleSheetsService
    from datetime import datetime as dt

    data = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=body.project_id,
        is_target=body.is_target,
        page=1,
        page_size=10000,
    )

    headers = [
        "Domain", "Website", "Company Name", "Is Target", "Confidence", "Status",
        "Industry", "Services", "Location", "Description",
        "Contacts Count", "Emails", "Phones", "Apollo People", "Reasoning", "Tracking",
    ]
    rows = [headers]

    import json as _json
    for dc in data["items"]:
        info = dc.company_info or {}
        services = ", ".join(info.get("services", [])) if info.get("services") else ""
        emails = ", ".join(dc.emails_found or [])
        phones = ", ".join(dc.phones_found or [])
        desc = info.get("description", "") or ""

        # Build tracking JSON
        tracking = {}
        if dc.created_at:
            tracking["discovered_at"] = dc.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(dc.created_at, 'strftime') else str(dc.created_at)
        if dc.scraped_at:
            tracking["scraped_at"] = dc.scraped_at.strftime("%Y-%m-%d %H:%M") if hasattr(dc.scraped_at, 'strftime') else str(dc.scraped_at)
        if dc.apollo_enriched_at:
            tracking["apollo_enriched_at"] = dc.apollo_enriched_at.strftime("%Y-%m-%d %H:%M") if hasattr(dc.apollo_enriched_at, 'strftime') else str(dc.apollo_enriched_at)
        if getattr(dc, 'apollo_credits_used', None):
            tracking["apollo_credits"] = dc.apollo_credits_used

        rows.append([
            dc.domain,
            f"https://{dc.domain}",
            dc.name or info.get("name", ""),
            "Yes" if dc.is_target else "No",
            f"{(dc.confidence or 0) * 100:.0f}%",
            dc.status.value if hasattr(dc.status, 'value') else str(dc.status),
            info.get("industry", ""),
            services,
            info.get("location", ""),
            desc[:200],
            dc.contacts_count or 0,
            emails,
            phones,
            dc.apollo_people_count or 0,
            (dc.reasoning or "")[:300],
            _json.dumps(tracking, ensure_ascii=False, default=str) if tracking else "",
        ])

    sheets_service = GoogleSheetsService()
    title = f"Pipeline Export — {dt.now().strftime('%Y-%m-%d %H:%M')}"
    try:
        sheet_url = sheets_service.create_and_populate(
            title=title,
            data=rows,
            share_with=["pn@getsally.io", "pavel.l@getsally.io"],
        )
    except Exception as e:
        logger.error(f"Google Sheet export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create Google Sheet: {str(e)}")

    if not sheet_url:
        raise HTTPException(status_code=500, detail="Failed to create Google Sheet (returned None)")

    return PipelineExportSheetResponse(sheet_url=sheet_url)


# ============ Auto-Enrich Config ============

@router.get("/auto-enrich-config/{project_id}")
async def get_auto_enrich_config(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get auto-enrichment config for a project."""
    from app.models.contact import Project
    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project.auto_enrich_config or {
        "auto_extract": True,
        "auto_apollo": False,
        "apollo_titles": ["CEO", "Founder", "Managing Director", "Owner"],
        "apollo_max_people": 5,
        "apollo_max_credits": 50,
    }


@router.put("/auto-enrich-config/{project_id}")
async def update_auto_enrich_config(
    project_id: int,
    body: dict,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update auto-enrichment config for a project."""
    from app.models.contact import Project
    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    allowed_keys = {"auto_extract", "auto_apollo", "apollo_titles", "apollo_max_people", "apollo_max_credits"}
    config = {k: v for k, v in body.items() if k in allowed_keys}
    project.auto_enrich_config = config
    await db.commit()
    return config


# ============ Contacts Export ============

CONTACTS_HEADERS = [
    "Domain", "URL", "Company Name", "Description", "Industry", "Location", "Confidence",
    "Reasoning", "First Name", "Last Name", "Email", "Phone", "Job Title", "LinkedIn",
    "Source", "Source Details", "Campaign Status", "Smartlead Info", "Tracking",
]


async def _query_contacts(db: AsyncSession, company_id: int, project_id: Optional[int],
                          email_only: bool, phone_only: bool, new_only: bool = False,
                          exclude_smartlead: bool = False,
                          exclude_emails_only: bool = False):
    """Shared query for contacts export (CSV + Google Sheets)."""
    from sqlalchemy import text

    where_clauses = ["dc.company_id = :company_id", "dc.is_target = true"]
    params = {"company_id": company_id}

    if project_id is not None:
        where_clauses.append("dc.project_id = :project_id")
        params["project_id"] = project_id
    if email_only:
        where_clauses.append("ec.email IS NOT NULL AND ec.email != ''")
    if phone_only:
        where_clauses.append("ec.phone IS NOT NULL")
    if new_only:
        where_clauses.append(
            "lower(dc.domain) NOT IN (SELECT DISTINCT lower(c.domain) FROM contacts c WHERE c.domain IS NOT NULL AND c.domain != '')"
        )
    if exclude_emails_only:
        # Exclude only exact email matches. Different person at same company is OK.
        where_clauses.append(
            "lower(ec.email) NOT IN ("
            "  SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL"
            ")"
        )
    elif exclude_smartlead:
        # Exclude contacts whose email OR domain already exists in ANY contacts record.
        where_clauses.append("""(
            lower(ec.email) NOT IN (
                SELECT DISTINCT lower(c.email) FROM contacts c
                WHERE c.email IS NOT NULL
            )
            AND lower(dc.domain) NOT IN (
                SELECT DISTINCT lower(c.domain) FROM contacts c
                WHERE c.domain IS NOT NULL AND c.domain != ''
            )
        )""")

    query = text(f"""
        SELECT
            dc.domain,
            'https://' || dc.domain as url,
            dc.company_info->>'name' as company_name,
            dc.company_info->>'description' as description,
            dc.company_info->>'industry' as industry,
            dc.company_info->>'location' as location,
            dc.confidence,
            dc.reasoning,
            ec.first_name,
            ec.last_name,
            ec.email,
            ec.phone,
            ec.job_title,
            ec.linkedin_url,
            CAST(ec.source AS text) as source,
            ec.raw_data,
            COALESCE(sq.query_text, sq2.query_text) as search_query,
            sj.search_engine as search_engine,
            sl_info.campaign_status,
            sl_info.smartlead_json,
            dc.created_at as discovered_at,
            dc.scraped_at,
            dc.apollo_enriched_at,
            COALESCE(dc.apollo_credits_used, 0) as apollo_credits_used,
            dc.apollo_people_count,
            CAST(dc.status AS text) as pipeline_status
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        LEFT JOIN search_results sr ON sr.id = dc.search_result_id
        LEFT JOIN search_queries sq ON sq.id = sr.source_query_id
        LEFT JOIN search_jobs sj ON sj.id = dc.search_job_id
        LEFT JOIN LATERAL (
            SELECT sq3.query_text FROM search_queries sq3
            WHERE sq3.search_job_id = dc.search_job_id
            AND sq3.id = (
                SELECT sr2.source_query_id FROM search_results sr2
                WHERE sr2.domain = dc.domain AND sr2.search_job_id = dc.search_job_id
                AND sr2.source_query_id IS NOT NULL
                LIMIT 1
            )
            LIMIT 1
        ) sq2 ON sq.id IS NULL
        LEFT JOIN LATERAL (
            SELECT
                'ADDED_TO_SMARTLEAD' as campaign_status,
                jsonb_build_object(
                    'smartlead_status', c.smartlead_status,
                    'campaigns', c.campaigns,
                    'added_at', c.created_at,
                    'last_synced_at', c.last_synced_at,
                    'contact_status', c.status
                )::text as smartlead_json
            FROM contacts c
            WHERE lower(c.domain) = lower(dc.domain)
              AND c.domain IS NOT NULL AND c.domain != ''
            ORDER BY c.last_synced_at DESC NULLS LAST
            LIMIT 1
        ) sl_info ON true
        WHERE {' AND '.join(where_clauses)}
        ORDER BY dc.confidence DESC, dc.domain
    """)
    result = await db.execute(query, params)
    return result.fetchall()


def _build_source_details(row) -> str:
    """Build source details JSON from search query + raw_data."""
    import json
    details = {}

    if row.search_query:
        details["query"] = row.search_query

    if getattr(row, 'search_engine', None):
        details["engine"] = row.search_engine

    if row.raw_data:
        raw = row.raw_data if isinstance(row.raw_data, dict) else {}
        if isinstance(row.raw_data, str):
            try:
                raw = json.loads(row.raw_data)
            except Exception:
                raw = {}
        if row.source == "APOLLO":
            for k in ("organization", "seniority", "departments", "city", "country"):
                if raw.get(k):
                    details[k] = raw[k]
        elif row.source == "WEBSITE_SCRAPE":
            if raw.get("is_generic"):
                details["generic_email"] = True

    if not details:
        return ""
    return json.dumps(details, ensure_ascii=False, default=str)


def _build_tracking_json(row) -> str:
    """Build tracking JSON with enrichment audit data (timestamps, credits, status, engine)."""
    import json
    tracking = {}

    if getattr(row, 'discovered_at', None):
        tracking["discovered_at"] = row.discovered_at.strftime("%Y-%m-%d %H:%M") if hasattr(row.discovered_at, 'strftime') else str(row.discovered_at)
    if getattr(row, 'scraped_at', None):
        tracking["scraped_at"] = row.scraped_at.strftime("%Y-%m-%d %H:%M") if hasattr(row.scraped_at, 'strftime') else str(row.scraped_at)
    if getattr(row, 'apollo_enriched_at', None):
        tracking["apollo_enriched_at"] = row.apollo_enriched_at.strftime("%Y-%m-%d %H:%M") if hasattr(row.apollo_enriched_at, 'strftime') else str(row.apollo_enriched_at)
    if getattr(row, 'apollo_credits_used', None):
        tracking["apollo_credits"] = row.apollo_credits_used
    if getattr(row, 'apollo_people_count', None):
        tracking["apollo_people"] = row.apollo_people_count
    if getattr(row, 'pipeline_status', None):
        tracking["status"] = row.pipeline_status
    if getattr(row, 'search_engine', None):
        tracking["search_engine"] = row.search_engine

    if not tracking:
        return ""
    return json.dumps(tracking, ensure_ascii=False, default=str)


def _contacts_to_rows(rows) -> List[List[str]]:
    """Convert DB rows to list-of-lists (for CSV or Sheets)."""
    data = [CONTACTS_HEADERS]
    for r in rows:
        campaign_status = r.campaign_status or "NEW"
        smartlead_json = r.smartlead_json or ""
        data.append([
            r.domain, r.url, r.company_name or "", r.description or "",
            r.industry or "", r.location or "", f"{(r.confidence or 0) * 100:.0f}%",
            r.reasoning or "",
            r.first_name or "", r.last_name or "", r.email or "", r.phone or "",
            r.job_title or "", r.linkedin_url or "", r.source or "",
            _build_source_details(r),
            campaign_status,
            smartlead_json,
            _build_tracking_json(r),
        ])
    return data


@router.get("/export-contacts-csv")
async def export_contacts_csv(
    project_id: Optional[int] = QueryParam(None),
    email_only: bool = QueryParam(False),
    phone_only: bool = QueryParam(False),
    new_only: bool = QueryParam(False),
    exclude_smartlead: bool = QueryParam(False),
    exclude_emails_only: bool = QueryParam(False),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export contacts as CSV (one row per contact)."""
    rows = await _query_contacts(db, company.id, project_id, email_only, phone_only, new_only, exclude_smartlead, exclude_emails_only)
    data = _contacts_to_rows(rows)

    output = io.StringIO()
    writer = csv.writer(output)
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"},
    )


@router.post("/export-contacts-sheet")
async def export_contacts_sheet(
    project_id: Optional[int] = QueryParam(None),
    email_only: bool = QueryParam(False),
    phone_only: bool = QueryParam(False),
    new_only: bool = QueryParam(False),
    exclude_smartlead: bool = QueryParam(False),
    exclude_emails_only: bool = QueryParam(False),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export contacts to Google Sheets. Returns sheet URL."""
    from app.services.google_sheets_service import google_sheets_service

    rows = await _query_contacts(db, company.id, project_id, email_only, phone_only, new_only, exclude_smartlead, exclude_emails_only)
    if not rows:
        raise HTTPException(status_code=400, detail="No contacts to export")

    data = _contacts_to_rows(rows)

    proj_name = "All"
    if project_id:
        from sqlalchemy import text
        pq = await db.execute(text("SELECT name FROM projects WHERE id = :id"), {"id": project_id})
        prow = pq.fetchone()
        if prow:
            proj_name = prow.name

    filters = []
    if new_only:
        filters.append("new")
    if email_only:
        filters.append("email")
    if phone_only:
        filters.append("phone")
    if exclude_emails_only:
        filters.append("excl-emails")
    elif exclude_smartlead:
        filters.append("excl-smartlead")
    filter_str = f" ({'+'.join(filters)})" if filters else ""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    title = f"{proj_name} Contacts{filter_str} — {ts}"

    url = google_sheets_service.create_and_populate(
        title=title,
        data=data,
        share_with=["pn@getsally.io", "pavel.l@getsally.io", "danuta@getsally.io"],
    )
    if not url:
        raise HTTPException(status_code=500, detail="Google Sheets export failed")

    return {"url": url, "rows": len(data) - 1}


# ============ Email Verification Endpoints ============

class VerifyEmailsRequest(BaseModel):
    extracted_contact_ids: List[int] = Field(..., min_length=1)
    max_credits: int = Field(100, ge=1, le=10000)


class VerifyAllRequest(BaseModel):
    max_credits: int = Field(100, ge=1, le=10000)


@router.post("/verify-emails")
async def verify_emails(
    body: VerifyEmailsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
    project_id: Optional[int] = QueryParam(None),
):
    """Verify a batch of extracted contacts' emails via Findymail."""
    stats = await pipeline_service.verify_emails_batch(
        db, body.extracted_contact_ids, company.id,
        project_id=project_id,
        max_credits=body.max_credits,
    )
    return stats


@router.get("/verification-stats")
async def get_verification_stats(
    project_id: Optional[int] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get email verification statistics for a project."""
    from app.services.email_verification_service import email_verification_service
    stats = await email_verification_service.get_stats(
        db, project_id=project_id, company_id=company.id,
    )
    return stats


@router.post("/project/{project_id}/verify-all")
async def verify_all_project_emails(
    project_id: int,
    body: VerifyAllRequest = VerifyAllRequest(),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Verify all unverified emails for a project. Runs in background."""
    from app.models.contact import Project
    from app.models.pipeline import ExtractedContact, DiscoveredCompany

    proj = await db.execute(select(Project).where(Project.id == project_id, Project.company_id == company.id))
    project = proj.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = project.auto_enrich_config or {}
    if not config.get("findymail_enabled", False):
        raise HTTPException(status_code=400, detail="Findymail is disabled for this project. Enable it via chat first.")

    # Get all unverified extracted contacts with emails
    dc_ids_subq = (
        select(DiscoveredCompany.id)
        .where(DiscoveredCompany.company_id == company.id, DiscoveredCompany.project_id == project_id)
        .scalar_subquery()
    )
    unverified_q = await db.execute(
        select(ExtractedContact.id)
        .where(
            ExtractedContact.discovered_company_id.in_(dc_ids_subq),
            ExtractedContact.email.isnot(None),
            ExtractedContact.is_verified == False,
        )
    )
    ec_ids = [row[0] for row in unverified_q.fetchall()]

    if not ec_ids:
        return {"status": "no_unverified_emails", "count": 0}

    async def _bg_verify():
        from app.db import async_session_maker
        async with async_session_maker() as session:
            await pipeline_service.verify_emails_batch(
                session, ec_ids, company.id,
                project_id=project_id,
                max_credits=body.max_credits,
            )

    background_tasks.add_task(_bg_verify)
    return {"status": "started", "emails_to_verify": len(ec_ids), "max_credits": body.max_credits}
