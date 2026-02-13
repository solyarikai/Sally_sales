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

# In-memory registry of running full-pipeline tasks
_running_pipelines: dict[int, dict] = {}


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

    _running_pipelines[project_id] = {
        "running": True,
        "phase": "starting",
        "started_at": datetime.utcnow().isoformat(),
        "config": body.model_dump(),
    }

    background_tasks.add_task(
        _run_full_pipeline_bg, project_id, company.id, body
    )

    return {"status": "started", "project_id": project_id}


@router.get("/full-pipeline/{project_id}/status")
async def get_full_pipeline_status(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get status of a running full pipeline."""
    if project_id not in _running_pipelines:
        return {"status": "not_running"}
    return _running_pipelines[project_id]


@router.post("/full-pipeline/{project_id}/stop")
async def stop_full_pipeline(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Request stop for a running pipeline (checked between phases)."""
    if project_id in _running_pipelines:
        _running_pipelines[project_id]["stop_requested"] = True
        return {"status": "stop_requested"}
    return {"status": "not_running"}


async def _run_full_pipeline_bg(project_id: int, company_id: int, cfg: FullPipelineRequest):
    """Background task: full pipeline orchestration."""
    progress = _running_pipelines[project_id]
    try:
        # --- Phase 1: Parallel Search ---
        if not cfg.skip_search:
            progress["phase"] = "search"
            await _bg_phase_search(project_id, company_id, cfg, progress)
            if progress.get("stop_requested"):
                progress.update({"running": False, "phase": "stopped"})
                return

        # --- Phase 2: Website Contact Extraction ---
        if not cfg.skip_extraction:
            progress["phase"] = "extraction"
            await _bg_phase_extraction(project_id, company_id, progress)
            if progress.get("stop_requested"):
                progress.update({"running": False, "phase": "stopped"})
                return

        # --- Phase 3: Apollo Enrichment ---
        if not cfg.skip_enrichment:
            progress["phase"] = "enrichment"
            await _bg_phase_enrichment(project_id, company_id, cfg, progress)
            if progress.get("stop_requested"):
                progress.update({"running": False, "phase": "stopped"})
                return

        # --- Phase 4: SmartLead Push ---
        if not cfg.skip_smartlead_push:
            progress["phase"] = "smartlead_push"
            await _bg_phase_smartlead_push(project_id, company_id, progress)

        progress.update({"running": False, "phase": "completed", "completed_at": datetime.utcnow().isoformat()})
        logger.info(f"Full pipeline completed for project {project_id}: {progress}")

    except Exception as e:
        logger.error(f"Full pipeline crashed for project {project_id}: {e}", exc_info=True)
        progress.update({"running": False, "phase": "error", "error": str(e)[:500]})


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
    """Segment-by-segment template search with Phase A (templates) + Phase B (AI expand)."""
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service
    from app.services.query_templates import SEGMENTS, SEGMENT_KEYS

    engine = SearchEngine.YANDEX_API
    if not cfg.skip_google:
        engine = SearchEngine.GOOGLE_SERP  # Can switch to Google after Yandex validation

    # Determine which segments to run
    if cfg.segments:
        segment_order = [s for s in cfg.segments if s in SEGMENTS]
    else:
        segment_order = SEGMENT_KEYS  # All by priority

    progress["segment_search"] = {
        "mode": "template",
        "engine": engine.value,
        "segments_planned": segment_order,
        "segments_completed": [],
        "segment_stats": {},
    }

    total_targets = targets_before
    for seg_key in segment_order:
        if progress.get("stop_requested"):
            break

        seg_def = SEGMENTS[seg_key]
        geo_keys = list(seg_def["geos"].keys())

        progress["segment_search"]["current_segment"] = seg_key
        progress["segment_search"]["segment_stats"][seg_key] = {
            "geos": {},
            "total_queries": 0,
            "total_targets": 0,
        }

        for geo_key in geo_keys:
            if progress.get("stop_requested"):
                break

            progress["segment_search"]["current_geo"] = geo_key

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

            # Update progress
            seg_stats = progress["segment_search"]["segment_stats"][seg_key]
            seg_stats["geos"][geo_key] = stats
            seg_stats["total_queries"] += stats.get("total_queries", 0)
            seg_stats["total_targets"] += stats.get("targets_found", 0)

            logger.info(
                f"Segment {seg_key}/{geo_key}: "
                f"{stats.get('template_queries', 0)} tmpl + {stats.get('ai_queries', 0)} AI = "
                f"{stats.get('total_queries', 0)} queries, {stats.get('targets_found', 0)} targets"
            )

            # Check if we've hit the overall target goal
            async with async_session_maker() as session:
                total_targets = await company_search_service._count_project_targets(session, project_id)
            if total_targets >= cfg.target_goal:
                logger.info(f"Target goal reached: {total_targets}/{cfg.target_goal}")
                break

        progress["segment_search"]["segments_completed"].append(seg_key)

        if total_targets >= cfg.target_goal:
            break

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
    """Apollo people enrichment for unenriched targets."""
    from sqlalchemy import select
    from app.models.pipeline import DiscoveredCompany

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
        remaining = cfg.apollo_credits - stats["credits_used"]
        if remaining <= 0:
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
    from app.services.smartlead_service import smartlead_service
    import httpx

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

    # 2. Query new target contacts (email-only exclusion)
    async with async_session_maker() as session:
        rows = await session.execute(sql_text("""
            SELECT ec.id, ec.email, ec.first_name, ec.last_name, ec.job_title,
                   dc.domain, dc.name as company_name, dc.url
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.company_id = :cid
            AND dc.is_target = true
            AND ec.email IS NOT NULL AND ec.email != ''
            AND lower(ec.email) NOT IN (
                SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL
            )
            ORDER BY ec.id
        """), {"pid": project_id, "cid": company_id})
        contacts = rows.fetchall()

    if not contacts:
        logger.info(f"No new contacts to push for project {project_id}")
        progress["smartlead_push_stats"]["skipped"] = "no_contacts"
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
    api_key = settings.SMARTLEAD_API_KEY
    if not api_key:
        logger.error("SMARTLEAD_API_KEY not configured, cannot push")
        stats["errors"] += 1
        return

    async with httpx.AsyncClient(timeout=60) as client:
        for rule in rules:
            bucket_contacts = buckets.get(rule.id, [])
            if not bucket_contacts:
                continue

            if progress.get("stop_requested"):
                break

            try:
                campaign_id = await _ensure_campaign_for_rule(
                    client, api_key, rule, len(bucket_contacts), session=None
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
                    resp = await client.post(
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

                    await asyncio.sleep(1)  # Rate limit

                # Verification: check actual lead count in SmartLead campaign
                verified_count = None
                try:
                    verify_resp = await client.get(
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

                # Record event with detailed push results
                async with async_session_maker() as session:
                    event = PipelineEvent(
                        company_id=company_id,
                        event_type=PipelineEventType.SMARTLEAD_LEADS_PUSHED,
                        detail={
                            "rule_name": rule.name,
                            "campaign_id": str(campaign_id),
                            "leads_sent": len(bucket_contacts),
                            "leads_uploaded": total_uploaded,
                            "leads_duplicate": total_duplicates,
                            "leads_invalid": total_invalid,
                            "verified_count": verified_count,
                        },
                    )
                    session.add(event)
                    await session.commit()

                # Insert only actually-pushed contacts into contacts table
                if actually_pushed_contacts:
                    async with async_session_maker() as session:
                        for contact, cls in actually_pushed_contacts:
                            domain = contact.email.split("@")[-1] if "@" in contact.email else None
                            await session.execute(sql_text("""
                                INSERT INTO contacts (company_id, email, first_name, last_name, domain,
                                                      source, status, is_active, created_at, updated_at)
                                VALUES (:cid, :email, :fname, :lname, :domain,
                                        'smartlead_pipeline_push', 'contacted', true, NOW(), NOW())
                                ON CONFLICT DO NOTHING
                            """), {
                                "cid": company_id, "email": contact.email,
                                "fname": contact.first_name or "", "lname": contact.last_name or "",
                                "domain": domain,
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


async def _ensure_campaign_for_rule(
    client: "httpx.AsyncClient",
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
    if not rule.current_campaign_id:
        logger.warning(
            f"Rule '{rule.name}' has no current_campaign_id set. "
            f"Set campaign_id in the push rule to use an existing SmartLead campaign."
        )
        return None

    # Verify the campaign exists
    try:
        resp = await client.get(
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
    import httpx
    api_key = settings.SMARTLEAD_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="SmartLead API key not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://server.smartlead.ai/api/v1/email-accounts",
            params={"api_key": api_key},
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


# ============ SmartLead Push Verification ============

@router.get("/projects/{project_id}/verify-smartlead-push")
async def verify_smartlead_push(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Verify leads actually arrived in SmartLead campaigns.
    Compares local DB records vs actual SmartLead campaign lead counts.
    """
    from app.models.pipeline import CampaignPushRule
    from app.services.smartlead_service import smartlead_service

    # Get rules with active campaigns
    result = await db.execute(
        select(CampaignPushRule).where(
            CampaignPushRule.project_id == project_id,
            CampaignPushRule.company_id == company.id,
            CampaignPushRule.current_campaign_id.isnot(None),
        )
    )
    rules = result.scalars().all()

    verifications = []
    for rule in rules:
        campaign_id = rule.current_campaign_id
        expected = rule.current_campaign_lead_count or 0
        actual = None
        status = "unknown"
        try:
            leads_data = await smartlead_service.get_campaign_leads(
                campaign_id, offset=0, limit=1
            )
            if isinstance(leads_data, dict):
                actual = leads_data.get("totalCount", leads_data.get("total", 0))
            elif isinstance(leads_data, list):
                # If it returns paginated list, we need the total
                actual = len(leads_data)  # Only first page; not reliable for total
        except Exception as e:
            status = f"error: {str(e)[:100]}"

        if actual is not None:
            if actual == 0 and expected > 0:
                status = "EMPTY - leads did not arrive"
            elif actual < expected:
                status = f"MISMATCH - expected {expected}, got {actual}"
            elif actual >= expected:
                status = "OK"

        verifications.append({
            "rule_name": rule.name,
            "campaign_id": campaign_id,
            "expected_count": expected,
            "actual_count": actual,
            "status": status,
        })

    return {
        "project_id": project_id,
        "verifications": verifications,
        "summary": {
            "total_rules": len(verifications),
            "ok": sum(1 for v in verifications if v["status"] == "OK"),
            "empty": sum(1 for v in verifications if "EMPTY" in v["status"]),
            "mismatch": sum(1 for v in verifications if "MISMATCH" in v["status"]),
            "errors": sum(1 for v in verifications if "error" in v["status"]),
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
