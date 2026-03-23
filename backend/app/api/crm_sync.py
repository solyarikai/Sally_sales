"""
CRM Sync API endpoints.

Provides:
- Manual sync triggers
- Webhook endpoints for Smartlead and GetSales
- Activity history endpoints
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, String, func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator
from datetime import datetime
import logging
import json
import hashlib
import hmac

from app.db import get_session
from app.db.database import async_session_maker
from app.models import Company, Contact, ContactActivity
from app.api.companies import get_required_company
from app.services.crm_sync_service import get_crm_sync_service, CRMSyncService, get_getsales_flow_name, parse_campaigns
from app.services.notification_service import send_telegram_notification

logger = logging.getLogger(__name__)

# Cached disabled-project data (campaign names + project names), 60s TTL
_disabled_cache: dict | None = None
_disabled_cache_ts: float = 0


async def _get_disabled_project_info(session: AsyncSession) -> dict:
    """Get campaign names and project names from projects with webhooks_enabled=False. Cached 60s."""
    global _disabled_cache, _disabled_cache_ts
    import time
    now = time.time()
    if _disabled_cache is not None and (now - _disabled_cache_ts) < 60:
        return _disabled_cache

    from app.models.contact import Project
    result = await session.execute(
        select(Project.campaign_filters, Project.name).where(
            Project.webhooks_enabled == False,
            Project.deleted_at.is_(None),
        )
    )
    campaign_names = set()
    project_names = set()
    for filters, pname in result.all():
        if pname:
            project_names.add(pname.lower())
        if isinstance(filters, list):
            campaign_names.update(filters)
    _disabled_cache = {"campaigns": campaign_names, "projects": project_names}
    _disabled_cache_ts = now
    return _disabled_cache


def _extract_linkedin_handle(url: str) -> str:
    """Extract just the LinkedIn handle for matching."""
    if not url or url == '--':
        return None
    url = url.lower().strip()
    if 'linkedin.com/in/' in url:
        return url.split('linkedin.com/in/')[-1].split('/')[0].split('?')[0].strip() or None
    if '/in/' in url:
        return url.split('/in/')[-1].split('/')[0].split('?')[0].strip() or None
    # Assume it is already just a handle
    return url.rstrip('/').split('?')[0] or None


def _normalize_linkedin(url: str) -> str:
    """Normalize LinkedIn URL for storage - keeps full URL format."""
    if not url or url == '--':
        return None
    import re
    url = url.lower().strip()
    url = re.sub(r'^https?://(www\.)?', '', url)
    # Extract clean handle and rebuild URL
    if 'linkedin.com/in/' in url:
        handle = url.split('linkedin.com/in/')[-1].split('/')[0].split('?')[0].strip()
        return f"linkedin.com/in/{handle}" if handle else None
    if '/in/' in url:
        handle = url.split('/in/')[-1].split('/')[0].split('?')[0].strip()
        return f"linkedin.com/in/{handle}" if handle else None
    # Return as-is if not a standard LinkedIn URL
    return url.rstrip('/') if url else None


def _extract_location(location_data) -> str:
    """Extract location string from dict or return as-is if string."""
    if location_data is None:
        return None
    if isinstance(location_data, str):
        return location_data
    if isinstance(location_data, dict):
        parts = [
            location_data.get("city"),
            location_data.get("region"),
            location_data.get("country")
        ]
        return ", ".join(filter(None, parts)) or location_data.get("address_string")
    return str(location_data)

router = APIRouter(prefix="/crm-sync", tags=["CRM Sync"])
def _truncate(value, max_len: int = 500):
    """Truncate string to max length."""
    if value is None:
        return None
    s = str(value)
    return s[:max_len] if len(s) > max_len else s




# ============= Schemas =============

class SyncRequest(BaseModel):
    sources: List[str] = ["smartlead", "getsales"]  # Which sources to sync
    full_sync: bool = True  # Full sync vs incremental


class SyncResponse(BaseModel):
    success: bool
    message: str
    results: Optional[Dict[str, Any]] = None


class ActivityResponse(BaseModel):
    id: int
    contact_id: int
    activity_type: str
    channel: str
    direction: Optional[str] = None
    source: str
    subject: Optional[str] = None
    snippet: Optional[str] = None
    activity_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class ContactWithActivitiesResponse(BaseModel):
    """Clean API contract — no deprecated DB fields exposed."""
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: str
    status: str
    last_reply_at: Optional[datetime] = None
    has_replied: bool = False
    provenance: Optional[dict] = None
    platform_state: Optional[dict] = None
    activities: List[ActivityResponse] = []

    @field_validator('has_replied', mode='before')
    @classmethod
    def compute_has_replied(cls, v, info):
        if info.data.get('last_reply_at') is not None:
            return True
        return bool(v)
    
    class Config:
        from_attributes = True


# ============= Sync Endpoints =============

@router.post("/trigger", response_model=SyncResponse)
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Trigger a CRM sync from external sources.
    
    Runs in background to avoid timeout.
    """
    sync_service = get_crm_sync_service()
    
    # Run sync in background
    async def run_sync():
        # Use async_session_maker directly for background tasks
        from app.db.database import async_session_maker
        async with async_session_maker() as bg_session:
            try:
                results = await sync_service.full_sync(bg_session, company.id)
                await bg_session.commit()
                logger.info(f"Sync completed for company {company.id}: {results}")
            except Exception as e:
                await bg_session.rollback()
                logger.error(f"Sync failed for company {company.id}: {e}")
    
    background_tasks.add_task(run_sync)
    
    return SyncResponse(
        success=True,
        message="Sync started in background. Check logs for progress.",
        results={"started_at": datetime.utcnow().isoformat()}
    )


@router.post("/sync-now", response_model=SyncResponse)
async def sync_now(
    request: SyncRequest = Body(default=SyncRequest()),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Run sync synchronously (blocking). Use for smaller syncs or testing.
    """
    sync_service = get_crm_sync_service()
    
    try:
        results = await sync_service.full_sync(session, company.id)
        return SyncResponse(
            success=results.get("success", False),
            message="Sync completed",
            results=results
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/setup-webhooks")
async def setup_webhooks(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Trigger webhook setup via the centralized scheduler function.
    
    All webhook registration goes through setup_crm_webhooks_on_startup()
    which uses the correct URLs (/api/smartlead/webhook, /api/crm-sync/webhook/getsales)
    and prevents duplicate registrations.
    """
    from app.services.crm_scheduler import setup_crm_webhooks_on_startup
    try:
        await setup_crm_webhooks_on_startup()
        return {"success": True, "message": "Webhook setup triggered via scheduler"}
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/fetch-replies")
async def fetch_smartlead_replies(
    background_tasks: BackgroundTasks,
    company: Company = Depends(get_required_company),
    session: AsyncSession = Depends(get_session),
):
    """Fetch reply history from Smartlead campaigns and update contact status."""
    from app.services.smartlead_service import fetch_all_campaign_replies
    import os
    
    api_key = os.getenv("SMARTLEAD_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Smartlead API key not configured")
    
    async def process_replies():
        from app.db.database import async_session_maker
        async with async_session_maker() as bg_session:
            try:
                # Get Smartlead campaigns
                from app.services.smartlead_service import SmartleadService
                smartlead = SmartleadService()
                campaigns = await smartlead.get_campaigns()
                
                total_replies = 0
                contacts_updated = 0
                
                for campaign in campaigns[:50]:  # Limit to first 50 campaigns
                    campaign_id = str(campaign.get("id"))
                    try:
                        replies = await fetch_all_campaign_replies(campaign_id, api_key)
                        
                        for reply in replies:
                            email = reply.get("lead_email", "").lower().strip()
                            if not email:
                                continue
                                
                            # Find and update contact
                            result = await bg_session.execute(
                                select(Contact).where(
                                    Contact.email == email,
                                    Contact.deleted_at.is_(None)
                                )
                            )
                            contact = result.scalars().first()
                            
                            # Create contact if not found (fixes missing contacts bug)
                            if not contact:
                                contact = Contact(
                                    company_id=1,
                                    email=email,
                                    first_name=reply.get("first_name"),
                                    last_name=reply.get("last_name"),
                                    company_name=reply.get("company_name"),
                                    source="smartlead",
                                    status="replied",
                                    last_reply_at=datetime.utcnow(),
                                )
                                contact.mark_synced("smartlead")
                                contact.set_platform("smartlead", {"campaigns": [{
                                    "name": campaign.get("name"),
                                    "id": campaign_id,
                                    "source": "smartlead",
                                    "added_at": datetime.utcnow().isoformat(),
                                }]})
                                # Parse reply_time
                                reply_time_str = reply.get("reply_time")
                                if reply_time_str:
                                    try:
                                        contact.last_reply_at = datetime.fromisoformat(reply_time_str.replace("Z", ""))
                                    except (ValueError, TypeError):
                                        contact.last_reply_at = datetime.utcnow()
                                bg_session.add(contact)
                                contacts_updated += 1
                                logger.info(f"Reply sync: created contact {email} from reply data")
                            elif contact.last_reply_at is None:
                                contact.mark_replied("email")
                                from app.services.status_machine import transition_status
                                new_st, ok, _msg = transition_status(contact.status, "interested")
                                if ok:
                                    contact.status = new_st
                                reply_time_str = reply.get("reply_time")
                                if reply_time_str:
                                    try:
                                        from datetime import datetime
                                        contact.last_reply_at = datetime.fromisoformat(reply_time_str.replace("Z", ""))
                                    except (ValueError, TypeError):
                                        contact.last_reply_at = None
                                contacts_updated += 1
                                
                            total_replies += 1
                            
                    except Exception as e:
                        logger.warning(f"Error fetching replies for campaign {campaign_id}: {e}")
                        continue
                
                await bg_session.commit()
                logger.info(f"Reply sync complete: {total_replies} replies found, {contacts_updated} contacts updated")
                
            except Exception as e:
                await bg_session.rollback()
                logger.error(f"Reply sync failed: {e}")
    
    background_tasks.add_task(process_replies)
    
    return {"success": True, "message": "Reply fetch started in background"}


@router.post("/backfill-reply-contacts")
async def backfill_reply_contacts(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Backfill contacts from processed_replies table.
    
    Fixes the critical bug where reply senders captured via webhooks
    were stored in processed_replies but never created as contacts.
    This creates Contact records for all processed_replies that have
    no matching contact, and fixes has_replied flags on existing contacts.
    """
    from app.models.reply import ProcessedReply
    from sqlalchemy import func, text
    
    async def do_backfill():
        from app.db.database import async_session_maker
        async with async_session_maker() as bg_session:
            try:
                # Step 1: Find all unique reply senders NOT in contacts table
                result = await bg_session.execute(text("""
                    SELECT DISTINCT ON (pr.lead_email)
                        pr.lead_email, pr.lead_first_name, pr.lead_last_name,
                        pr.lead_company, pr.campaign_name, pr.campaign_id,
                        pr.category, pr.received_at
                    FROM processed_replies pr
                    LEFT JOIN contacts c ON LOWER(c.email) = LOWER(pr.lead_email) 
                        AND c.deleted_at IS NULL
                    WHERE c.id IS NULL
                      AND pr.lead_email IS NOT NULL
                      AND pr.lead_email != ''
                    ORDER BY pr.lead_email, pr.received_at DESC
                """))
                missing = result.fetchall()
                
                created = 0
                for row in missing:
                    email, first_name, last_name, company, campaign_name, campaign_id, category, received_at = row
                    contact = Contact(
                        company_id=1,
                        email=email.lower().strip(),
                        first_name=first_name,
                        last_name=last_name,
                        company_name=company,
                        source="smartlead",
                        status="replied",
                        last_reply_at=received_at,
                    )
                    contact.mark_synced("smartlead")
                    if campaign_name or campaign_id:
                        contact.set_platform("smartlead", {"campaigns": [{
                            "name": campaign_name,
                            "id": str(campaign_id) if campaign_id else None,
                            "source": "smartlead",
                            "added_at": datetime.utcnow().isoformat(),
                        }]})
                    
                    bg_session.add(contact)
                    created += 1
                
                await bg_session.flush()
                
                fix_result = await bg_session.execute(text("""
                    UPDATE contacts c
                    SET status = CASE WHEN c.status IN ('new', 'lead', 'contacted') THEN 'replied' ELSE c.status END,
                        last_reply_at = COALESCE(c.last_reply_at, (
                            SELECT MAX(pr.received_at) FROM processed_replies pr 
                            WHERE LOWER(pr.lead_email) = LOWER(c.email)
                        ))
                    FROM processed_replies pr
                    WHERE LOWER(c.email) = LOWER(pr.lead_email)
                      AND c.deleted_at IS NULL
                      AND c.last_reply_at IS NULL
                """))
                fixed = fix_result.rowcount
                
                # Step 3: Merge all campaign entries for each contact
                # (contacts may have replies from multiple campaigns but only 1 recorded)
                multi_result = await bg_session.execute(text("""
                    SELECT LOWER(pr.lead_email) AS email,
                           json_agg(DISTINCT jsonb_build_object(
                               'name', pr.campaign_name,
                               'id', CAST(pr.campaign_id AS text),
                               'source', COALESCE(pr.source, 'smartlead'),
                               'added_at', COALESCE(pr.received_at::text, NOW()::text)
                           )) AS all_campaigns
                    FROM processed_replies pr
                    WHERE pr.lead_email IS NOT NULL AND pr.lead_email != ''
                    GROUP BY LOWER(pr.lead_email)
                    HAVING COUNT(DISTINCT pr.campaign_name) > 1
                """))
                for row in multi_result.fetchall():
                    email, all_campaigns = row
                    cq = await bg_session.execute(
                        select(Contact).where(
                            func.lower(Contact.email) == email,
                            Contact.deleted_at.is_(None),
                        )
                    )
                    c = cq.scalar_one_or_none()
                    if c:
                        sl = [x for x in (all_campaigns or []) if x.get("source") == "smartlead"]
                        gs = [x for x in (all_campaigns or []) if x.get("source") == "getsales"]
                        if sl:
                            c.set_platform("smartlead", {"campaigns": sl})
                        if gs:
                            c.set_platform("getsales", {"campaigns": gs})
                merged = multi_result.rowcount if hasattr(multi_result, 'rowcount') else 0

                await bg_session.commit()
                logger.info(f"Backfill complete: {created} contacts created, {fixed} contacts fixed, {merged} campaigns merged")

            except Exception as e:
                await bg_session.rollback()
                logger.error(f"Backfill failed: {e}")
    
    background_tasks.add_task(do_backfill)
    
    return {"success": True, "message": "Backfill started in background. Check logs for progress."}


@router.get("/webhooks")
async def list_configured_webhooks(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    List all configured webhooks in external systems.
    """
    sync_service = get_crm_sync_service()
    results = {"getsales": [], "smartlead": []}
    
    if sync_service.getsales:
        try:
            results["getsales"] = await sync_service.getsales.get_webhooks()
        except Exception as e:
            logger.error(f"Failed to get GetSales webhooks: {e}")
    
    return results


@router.get("/status")
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get current sync status and statistics.
    """
    # Count contacts by source
    from sqlalchemy import func
    
    source_counts = await session.execute(
        select(Contact.source, func.count(Contact.id))
        .where(and_(Contact.company_id == company.id, Contact.deleted_at.is_(None)))
        .group_by(Contact.source)
    )
    by_source = {row[0]: row[1] for row in source_counts.all()}
    
    # Count replied contacts
    replied_count = await session.execute(
        select(func.count(Contact.id))
        .where(and_(
            Contact.company_id == company.id,
            Contact.deleted_at.is_(None),
            Contact.last_reply_at.isnot(None)
        ))
    )
    
    # Count activities
    activity_count = await session.execute(
        select(func.count(ContactActivity.id))
        .where(ContactActivity.company_id == company.id)
    )
    
    return {
        "total_contacts": sum(by_source.values()),
        "by_source": by_source,
        "replied_contacts": replied_count.scalar() or 0,
        "total_activities": activity_count.scalar() or 0,
    }


@router.get("/project/{project_id}/monitoring")
async def get_project_monitoring(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Project-level monitoring dashboard data.
    Returns webhook health, polling intervals, per-campaign status, reply stats.
    No X-Company-ID header required (frontend skips it for /crm-sync routes).
    """
    from app.models.contact import Project
    from app.models.campaign import Campaign
    from app.models.reply import ProcessedReply, WebhookEventModel
    from app.services.crm_scheduler import get_crm_scheduler
    from sqlalchemy import func

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    company_id = project.company_id

    scheduler = get_crm_scheduler()
    scheduler_status = scheduler.get_status()

    campaign_names = project.campaign_filters or []
    campaign_names_lower = {n.lower() for n in campaign_names}

    ACTIVE_STATUSES = {'active', 'STARTED', 'in_progress', 'INPROGRESS', 'ready', 'linked'}
    STATUS_NORMALIZE = {
        'INPROGRESS': 'active', 'STARTED': 'active', 'in_progress': 'active',
        'ready': 'active', 'linked': 'active',
        'COMPLETED': 'completed', 'BLOCKED': 'blocked',
    }

    # Per-campaign stats — only show active campaigns
    campaign_stats = []
    active_campaign_names = []
    if campaign_names:
        db_campaigns_q = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.company_id == company_id,
                    Campaign.name.in_(campaign_names),
                )
            )
        )
        db_campaigns_map = {c.name: c for c in db_campaigns_q.scalars().all()}

        for name in sorted(campaign_names):
            db_camp = db_campaigns_map.get(name)
            raw_status = db_camp.status if db_camp else "linked"
            is_active = raw_status in ACTIVE_STATUSES
            display_status = STATUS_NORMALIZE.get(raw_status, raw_status)
            platform = db_camp.platform if db_camp else "unknown"

            # Try to infer platform from campaign name for unregistered GetSales flows
            if platform == "unknown":
                name_lower = name.lower()
                if "dm" in name_lower or "connect" in name_lower or "linkedin" in name_lower:
                    platform = "getsales"

            if not is_active:
                continue

            active_campaign_names.append(name)

            contact_count_q = await session.execute(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.company_id == company_id,
                        Contact.deleted_at.is_(None),
                        Contact.platform_state.cast(String).ilike(f'%{name}%'),
                    )
                )
            )
            replied_q = await session.execute(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.company_id == company_id,
                        Contact.deleted_at.is_(None),
                        Contact.last_reply_at.isnot(None),
                        Contact.platform_state.cast(String).ilike(f'%{name}%'),
                    )
                )
            )

            campaign_stats.append({
                "name": name,
                "platform": platform,
                "status": display_status,
                "active": True,
                "contacts": contact_count_q.scalar() or 0,
                "replied": replied_q.scalar() or 0,
                "external_id": db_camp.external_id if db_camp else None,
            })

    # Project-level reply stats (last 24h and 7d)
    since_24h = datetime.utcnow() - __import__('datetime').timedelta(hours=24)
    since_7d = datetime.utcnow() - __import__('datetime').timedelta(days=7)

    # Recent processed replies — count from all project campaigns (active and inactive can still receive late replies)
    replies_24h_q = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            and_(
                ProcessedReply.received_at >= since_24h,
                ProcessedReply.campaign_name.in_(campaign_names) if campaign_names else ProcessedReply.id < 0,
            )
        )
    )
    replies_7d_q = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            and_(
                ProcessedReply.received_at >= since_7d,
                ProcessedReply.campaign_name.in_(campaign_names) if campaign_names else ProcessedReply.id < 0,
            )
        )
    )

    # Failed webhook events in last 24h
    failed_events_q = await session.execute(
        select(func.count(WebhookEventModel.id)).where(
            and_(
                WebhookEventModel.processed == False,
                WebhookEventModel.created_at >= since_24h,
            )
        )
    )

    # Total project contacts
    total_contacts_q = await session.execute(
        select(func.count(Contact.id)).where(
            and_(
                Contact.company_id == company_id,
                Contact.project_id == project_id,
                Contact.deleted_at.is_(None),
            )
        )
    )
    total_replied_q = await session.execute(
        select(func.count(Contact.id)).where(
            and_(
                Contact.company_id == company_id,
                Contact.project_id == project_id,
                Contact.deleted_at.is_(None),
                Contact.last_reply_at.isnot(None),
            )
        )
    )

    # Task timing from scheduler
    task_timing = scheduler_status.get("task_timing", {})
    reply_count = scheduler_status.get("reply_check_count", 0)
    webhook_healthy = scheduler_status.get("webhook_healthy", True)

    # Build intervals from live task_timing (accurate last_run + next_run)
    polling_tasks = []
    display_order = ["reply_check", "sync", "webhook_setup", "conversation_sync", "sheet_sync", "event_recovery"]
    for key in display_order:
        t = task_timing.get(key, {})
        polling_tasks.append({
            "task": t.get("label", key),
            "interval_seconds": t.get("interval_seconds"),
            "last_run": t.get("last_run"),
            "next_run": t.get("next_run"),
        })

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "webhooks_enabled": project.webhooks_enabled,
        },
        "scheduler": {
            "running": scheduler_status.get("running", False),
            "task_health": scheduler_status.get("task_health", {}),
        },
        "webhooks": {
            "healthy": webhook_healthy,
            "last_received": scheduler_status.get("last_webhook_received"),
            "last_check": scheduler_status.get("last_webhook_check"),
        },
        "polling": {
            "intervals": polling_tasks,
            "reply_checks_count": reply_count,
            "sync_count": scheduler_status.get("sync_count", 0),
        },
        "reply_stats": {
            "total_contacts": total_contacts_q.scalar() or 0,
            "total_replied": total_replied_q.scalar() or 0,
            "replies_24h": replies_24h_q.scalar() or 0,
            "replies_7d": replies_7d_q.scalar() or 0,
            "failed_events_24h": failed_events_q.scalar() or 0,
        },
        "campaigns": sorted(campaign_stats, key=lambda c: c["name"]),
        "active_campaigns_count": len(active_campaign_names),
        "latest_events": await _get_latest_events(session, campaign_names),
    }


async def _get_latest_events(session: AsyncSession, campaign_names: list) -> dict:
    """Fetch latest events for THIS project only. Merges replies + sent into one timeline."""
    from app.models.reply import WebhookEventModel, ProcessedReply
    from sqlalchemy import desc

    result: dict = {"events": []}

    if not campaign_names:
        return result

    # Latest processed replies for this project's campaigns
    replies_q = await session.execute(
        select(ProcessedReply)
        .where(ProcessedReply.campaign_name.in_(campaign_names))
        .order_by(desc(ProcessedReply.received_at))
        .limit(10)
    )
    for r in replies_q.scalars().all():
        result["events"].append({
            "id": f"reply_{r.id}",
            "type": "reply",
            "source": r.source,
            "channel": r.channel,
            "campaign_name": r.campaign_name,
            "lead_email": r.lead_email,
            "lead_name": f"{r.lead_first_name or ''} {r.lead_last_name or ''}".strip(),
            "category": r.category,
            "approval_status": r.approval_status,
            "at": r.received_at.isoformat() + "Z" if r.received_at else None,
        })

    # Latest webhook events — scope via campaign_ids from campaigns table
    from app.models.campaign import Campaign as CampaignModel
    camp_ids_q = await session.execute(
        select(CampaignModel.external_id).where(
            CampaignModel.name.in_(campaign_names),
            CampaignModel.external_id.isnot(None),
        )
    )
    project_campaign_ids = [r[0] for r in camp_ids_q.all()]

    if project_campaign_ids:
        events_q = await session.execute(
            select(WebhookEventModel)
            .where(WebhookEventModel.campaign_id.in_(project_campaign_ids))
            .order_by(desc(WebhookEventModel.created_at))
            .limit(10)
        )
        for ev in events_q.scalars().all():
            if ev.event_type in ("EMAIL_REPLY", "EMAIL_SENT"):
                continue
            result["events"].append({
                "id": f"wh_{ev.id}",
                "type": ev.event_type.lower() if ev.event_type else "unknown",
                "source": "smartlead",
                "channel": "email",
                "campaign_name": None,
                "lead_email": ev.lead_email,
                "lead_name": None,
                "category": None,
                "approval_status": None,
                "at": ev.created_at.isoformat() + "Z" if ev.created_at else None,
                "error": ev.error[:150] if ev.error else None,
            })

    # Sort merged list by time descending, replies first at same time
    def sort_key(e):
        priority = 0 if e["type"] == "reply" else 1
        return (e.get("at") or "", priority)

    result["events"].sort(key=sort_key, reverse=True)
    result["events"] = result["events"][:10]

    return result


# ============= Webhook Endpoints =============
# SmartLead webhooks are handled EXCLUSIVELY by /api/smartlead/webhook
# (in smartlead.py). Never duplicate webhook handlers — that's how we
# ended up with 360+ duplicate registrations and lost events.

@router.post("/webhook/getsales/bulk-import")
async def getsales_bulk_import_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Webhook endpoint for GetSales bulk contact export.
    """
    from app.core.config import settings as _cfg
    if _cfg.WEBHOOK_SECRET:
        token = request.query_params.get("token")
        if token != _cfg.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook token")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Log full payload for debugging
    debug_file = "/tmp/getsales_webhook_sample.json"
    try:
        with open(debug_file, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info(f"Saved webhook payload to {debug_file}")
    except Exception as e:
        logger.warning(f"Could not save payload: {e}")
    
    # GetSales sends contact data in the body
    body = payload.get("body", payload)
    contact_data = body.get("contact", body)
    
    # Extract contact fields
    email = (
        contact_data.get("work_email") or 
        contact_data.get("personal_email") or 
        contact_data.get("email")
    )
    
    if not email:
        logger.warning(f"Bulk import: No email in payload")
        return {"status": "ignored", "reason": "no email"}
    
    email = email.lower().strip()
    
    # Check if contact already exists
    result = await session.execute(
        select(Contact).where(
            and_(Contact.email == email, Contact.deleted_at.is_(None))
        )
    )
    contact = result.scalar_one_or_none()
    
    getsales_uuid = contact_data.get("uuid") or contact_data.get("id")
    
    if contact:
        # Update existing contact with GetSales data
        contact.getsales_id = str(getsales_uuid) if getsales_uuid else contact.getsales_id
        contact.mark_synced("getsales")
        if contact_data.get("pipeline_stage"):
            contact.update_platform_status("getsales", contact_data.get("pipeline_stage"))
        action = "updated"
    else:
        # Create new contact
        linkedin_url_raw = (
            contact_data.get("linkedin_url") or 
            contact_data.get("linkedin_profile_url") or
            contact_data.get("linkedin")
        )
        linkedin_url = _normalize_linkedin(linkedin_url_raw)
        
        contact = Contact(
            company_id=1,  # Default company
            email=email,
            first_name=_truncate(contact_data.get("first_name", ""), 255),
            last_name=_truncate(contact_data.get("last_name", ""), 255),
            company_name=_truncate(contact_data.get("account", {}).get("name") if isinstance(contact_data.get("account"), dict) else contact_data.get("company_name", ""), 500),
            job_title=_truncate(contact_data.get("job_title") or contact_data.get("title"), 500),
            linkedin_url=_truncate(linkedin_url, 500),
            location=_truncate(_extract_location(contact_data.get("location")) or contact_data.get("city"), 500),
            phone=_truncate(contact_data.get("phone") or contact_data.get("phone_number"), 100),
            source="getsales",
            getsales_id=str(getsales_uuid) if getsales_uuid else None,
            status="lead",
        )
        contact.update_platform_status("getsales", contact_data.get("pipeline_stage") or "")
        session.add(contact)
        action = "created"
    
    await session.commit()
    
    logger.info(f"Bulk import: {action} contact {email}")
    return {"status": "processed", "action": action, "email": email}


@router.post("/webhook/getsales")
async def getsales_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Webhook endpoint for GetSales events.
    """
    from app.core.config import settings as _cfg
    if _cfg.WEBHOOK_SECRET:
        token = request.query_params.get("token")
        if token != _cfg.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook token")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # GetSales wraps everything in "body"
    body = payload.get("body", payload)
    
    contact_data = body.get("contact", {})
    account_data = body.get("account", {})
    automation_data = body.get("automation", {})
    linkedin_message = body.get("linkedin_message", {})
    contact_markers = body.get("contact_markers", {})
    
    lead_uuid = contact_data.get("uuid")
    lead_email = contact_data.get("work_email") or contact_data.get("personal_email")
    linkedin_url = contact_data.get("linkedin_url") or contact_data.get("linkedin")
    
    # Determine if this is an inbound reply
    message_type = linkedin_message.get("type", "").lower()
    is_reply = message_type == "inbox"
    
    automation_name = automation_data.get("name", "")
    automation_uuid = automation_data.get("uuid", "")
    logger.info(f"GetSales webhook: contact={contact_data.get('name')}, message_type={message_type}, automation={automation_name}")

    # Log raw event to webhook_events table for debugging/replay
    from app.models.reply import WebhookEventModel
    event_type = f"linkedin_{message_type}" if message_type else "getsales_unknown"
    webhook_event = WebhookEventModel(
        event_type=event_type,
        campaign_id=automation_uuid or automation_name,
        lead_email=lead_email or contact_data.get("name", ""),
        payload=json.dumps(payload, default=str),
        processed=False
    )
    session.add(webhook_event)
    await session.flush()
    gs_event_id = webhook_event.id

    # Skip events from automations belonging to disabled projects (startswith matching)
    disabled = await _get_disabled_project_info(session)
    if automation_name and disabled["projects"]:
        auto_lower = automation_name.lower()
        if any(auto_lower.startswith(pname) for pname in disabled["projects"]):
            webhook_event.processed = True
            webhook_event.processed_at = datetime.utcnow()
            logger.info(f"GetSales webhook skipped: automation '{automation_name}' (webhooks disabled)")
            return {"status": "skipped", "reason": "webhooks disabled for project"}

    # Signal webhook health to the scheduler
    from app.services.crm_scheduler import mark_webhook_received
    mark_webhook_received()
    
    # Find contact by UUID, email, or LinkedIn
    contact = None
    
    if lead_uuid:
        result = await session.execute(
            select(Contact).where(
                and_(Contact.getsales_id == lead_uuid, Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    if not contact and lead_email:
        result = await session.execute(
            select(Contact).where(
                and_(Contact.email == lead_email.lower(), Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    # Also try to match by LinkedIn URL (for contacts from Smartlead with LinkedIn)
    if not contact and linkedin_url:
        # Normalize LinkedIn URL for matching
        normalized_linkedin = linkedin_url.lower().rstrip("/")
        if "linkedin.com/in/" in normalized_linkedin:
            linkedin_handle = _extract_linkedin_handle(linkedin_url)
            result = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.linkedin_url.ilike(f"%/in/{linkedin_handle}%"),
                        Contact.deleted_at.is_(None)
                    )
                )
            )
            contact = result.scalar_one_or_none()
    
    # If we found an existing contact (from Smartlead), update GetSales fields
    is_existing_contact = contact is not None
    if is_existing_contact and not contact.getsales_id:
        logger.info(f"Merging GetSales data into existing contact: {contact.email}")
        contact.getsales_id = lead_uuid
        contact.update_platform_status("getsales", contact_data.get("pipeline_stage_name") or "")
        if linkedin_url and not contact.linkedin_url:
            contact.linkedin_url = linkedin_url
    
    # If contact has a placeholder/NULL email and webhook provides a real one, update it
    if is_existing_contact and lead_email and (
        not contact.email
        or any(p in contact.email for p in ("@linkedin.placeholder", "@getsales.local", "@placeholder.local"))
    ):
        logger.info(f"Updating email {contact.email} -> {lead_email}")
        contact.email = lead_email.lower().strip()
        if '@' in lead_email:
            contact.domain = lead_email.split('@')[1].lower()
    
    if not contact:
        # Contact not in our system yet - create it
        logger.info(f"Creating new contact from GetSales webhook: {lead_email or linkedin_url}")
        
        location = contact_data.get("location")
        if isinstance(location, dict):
            location_str = ", ".join(filter(None, [
                location.get("city"),
                location.get("region"),
                location.get("country")
            ]))
        elif isinstance(location, str):
            location_str = location
        else:
            location_str = contact_data.get("raw_address", "")
        
        # Resolve project from automation data
        from app.services.crm_sync_service import match_campaign_to_project, _getsales_flow_cache
        webhook_project_id = None
        if automation_name:
            webhook_project_id = match_campaign_to_project(automation_name)
        if not webhook_project_id and automation_uuid:
            flow_name = _getsales_flow_cache.get(automation_uuid, "")
            if flow_name:
                webhook_project_id = match_campaign_to_project(flow_name)

        contact = Contact(
            company_id=1,  # Default company
            project_id=webhook_project_id,
            email=lead_email or None,
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            company_name=contact_data.get("company_name") or account_data.get("name"),
            job_title=contact_data.get("position"),
            linkedin_url=linkedin_url,
            location=location_str,
            source="getsales",
            getsales_id=lead_uuid,
            status="replied" if is_reply else "contacted",
            last_reply_at=datetime.utcnow() if is_reply else None,
        )
        contact.update_platform_status("getsales", contact_data.get("pipeline_stage_name") or "")
        if automation_data.get("name") or automation_data.get("uuid"):
            contact.set_platform("getsales", {"campaigns": [{
                "name": automation_data.get("name"),
                "id": automation_data.get("uuid"),
                "source": "getsales",
                "status": "active"
            }]})
        session.add(contact)
        await session.flush()

        # Register unknown automation as campaign if not already in DB
        if automation_uuid and automation_name:
            from app.models.campaign import Campaign
            existing_camp = await session.execute(
                select(Campaign).where(
                    and_(Campaign.platform == "getsales", Campaign.external_id == automation_uuid)
                )
            )
            if not existing_camp.scalar():
                camp = Campaign(
                    company_id=1, project_id=webhook_project_id,
                    platform="getsales", channel="linkedin",
                    external_id=automation_uuid, name=automation_name,
                    status="active",
                    resolution_method="webhook" if webhook_project_id else None,
                    resolution_detail="Auto-registered from GetSales webhook",
                )
                session.add(camp)
                logger.info(f"Registered new campaign from webhook: {automation_name} (project_id={webhook_project_id})")

        if webhook_project_id:
            logger.info(f"New contact from webhook assigned to project_id={webhook_project_id}")
    
    # Determine activity type
    if is_reply:
        activity_type = "linkedin_replied"
        direction = "inbound"
    else:
        activity_type = "linkedin_sent"
        direction = "outbound"
    
    # Parse sent_at timestamp
    sent_at_str = linkedin_message.get("sent_at")
    if sent_at_str:
        try:
            activity_at = datetime.fromisoformat(sent_at_str.replace(" ", "T").replace("Z", "+00:00"))
        except (ValueError, TypeError):
            activity_at = datetime.utcnow()
    else:
        activity_at = datetime.utcnow()
    
    # Create activity
    message_text = linkedin_message.get("text", "")
    # Dedup check for reply activities
    snippet = message_text[:200] if message_text else None
    is_duplicate = False
    if "replied" in activity_type:
        from sqlalchemy import func
        minute_start = activity_at.replace(second=0, microsecond=0)
        minute_end = activity_at.replace(second=59, microsecond=999999)
        existing = await session.execute(
            select(ContactActivity).where(
                ContactActivity.contact_id == contact.id,
                ContactActivity.source == "getsales",
                ContactActivity.activity_type == activity_type,
                ContactActivity.activity_at >= minute_start,
                ContactActivity.activity_at <= minute_end,
                ContactActivity.snippet == snippet
            )
        )
        if existing.scalar():
            is_duplicate = True
            logger.info(f"[GETSALES] Skipping duplicate activity for contact {contact.id}")
    
    if not is_duplicate:
        activity = ContactActivity(
            contact_id=contact.id,
            company_id=contact.company_id,
            activity_type=activity_type,
            channel="linkedin",
            direction=direction,
            source="getsales",
            source_id=lead_uuid,
            subject=linkedin_message.get("subject"),
            body=message_text,
            snippet=snippet,
            extra_data={
                "automation_uuid": automation_data.get("uuid"),
                "automation_name": automation_data.get("name"),
                "pipeline_stage": contact_data.get("pipeline_stage_name"),
                "account_name": account_data.get("name"),
                "account_website": account_data.get("website"),
                "linkedin_type": linkedin_message.get("linkedin_type"),
                "messages_sent_count": contact_markers.get("linkedin_messages_sent_count"),
                "messages_inbox_count": contact_markers.get("linkedin_messages_inbox_count"),
                "conversation_thread": (body.get("latest_linkedin_conversation_thread") or {}).get("messaging_thread") if isinstance(body.get("latest_linkedin_conversation_thread"), dict) else None,
            },
            activity_at=activity_at
        )
        session.add(activity)
    
    # Update contact if this is a reply
    if is_reply:
        contact.mark_replied("linkedin", at=activity_at)
        contact.last_reply_at = activity_at
        contact.update_platform_status("getsales", contact_data.get("pipeline_stage_name") or "")

        # M9 FIX: Use process_getsales_reply as the single source of classification.
        # Previously we did a lightweight classify_reply here (redundant) and then called
        # process_getsales_reply which does proper GPT classification again.
        # Now: call process_getsales_reply once, use its result for contact status.
        category = "other"  # default fallback
        pr = None
        try:
            from app.services.reply_processor import process_getsales_reply

            # Wrap in savepoint so failures don't poison the outer session
            # (allows webhook_event + contact activity to still commit)
            async with session.begin_nested():
                pr = await process_getsales_reply(
                    message_text=message_text,
                    contact=contact,
                    flow_name=automation_data.get("name", ""),
                    flow_uuid=automation_data.get("uuid", ""),
                    message_id=linkedin_message.get("uuid", ""),
                    activity_at=activity_at,
                    raw_data=body,
                    session=session,
                )
            if pr and pr.category:
                category = pr.category
        except Exception as pr_err:
            logger.warning(f"[GETSALES] ProcessedReply creation failed (non-fatal): {pr_err}")

        # Update activity with category from the proper classification
        if not is_duplicate:
            activity.extra_data["category"] = category

        # Update contact status via state machine (forward-only)
        from app.services.status_machine import transition_status, status_from_ai_category
        from app.services.crm_sync_service import get_sentiment_from_category
        target_status = status_from_ai_category(category)
        new_st, ok, msg = transition_status(contact.status, target_status)
        if ok:
            contact.status = new_st
            logger.info(f"[GETSALES] {contact.email} → {new_st} (category={category})")
        else:
            logger.warning(f"[GETSALES] Blocked transition for {contact.email}: {msg}")
        contact.set_platform("getsales", {"reply_category": category})

        # Append to getsales_raw for debugging
        from datetime import datetime as dt
        webhook_entry = {
            "received_at": dt.utcnow().isoformat(),
            "type": "reply",
            "category": category,
            "payload": body
        }
        if contact.getsales_raw:
            try:
                raw = json.loads(contact.getsales_raw) if isinstance(contact.getsales_raw, str) else contact.getsales_raw
                if "webhooks" not in raw:
                    raw["webhooks"] = []
                raw["webhooks"].append(webhook_entry)
                contact.getsales_raw = raw
            except (json.JSONDecodeError, TypeError, AttributeError):
                contact.getsales_raw = {"webhooks": [webhook_entry]}
        else:
            contact.getsales_raw = {"webhooks": [webhook_entry]}
        contact.update_platform_raw("getsales", contact.getsales_raw)
        
        # Telegram notification sent AFTER commit (see below)

    # Mark webhook event as processed — but ONLY if reply was created (or not a reply event)
    if not is_reply or pr:
        webhook_event.processed = True
        webhook_event.processed_at = datetime.utcnow()
    else:
        webhook_event.error = f"process_getsales_reply returned None for contact {contact.id if contact else 'unknown'}"
        logger.warning(f"[GETSALES] Webhook event {gs_event_id} NOT marked processed — reply creation failed")

    await session.commit()

    # Send Telegram notification AFTER commit — prevents ghost notifications on rollback
    if is_reply and pr:
        try:
            from app.services.reply_processor import send_getsales_notification
            await send_getsales_notification(
                processed_reply=pr,
                contact=contact,
                flow_name=automation_data.get("name", ""),
                flow_uuid=automation_data.get("uuid", ""),
                message_text=message_text,
                raw_data=body,
                session=session,
            )
        except Exception as tg_err:
            logger.warning(f"[GETSALES] Post-commit notification failed (non-fatal): {tg_err}")

    return {
        "status": "processed",
        "event_id": gs_event_id,
        "contact_id": contact.id,
        "is_reply": is_reply,
        "is_duplicate": is_duplicate,
    }


# ============= Activity Endpoints =============

@router.get("/contacts/{contact_id}/activities", response_model=List[ActivityResponse])
async def get_contact_activities(
    contact_id: int,
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get all activities for a contact.
    """
    # Verify contact belongs to company
    contact = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company.id,
                Contact.deleted_at.is_(None)
            )
        )
    )
    if not contact.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Get activities
    result = await session.execute(
        select(ContactActivity)
        .where(ContactActivity.contact_id == contact_id)
        .order_by(desc(ContactActivity.activity_at))
        .limit(limit)
    )
    activities = result.scalars().all()
    
    return [ActivityResponse.model_validate(a) for a in activities]


@router.get("/contacts/{contact_id}/full", response_model=ContactWithActivitiesResponse)
async def get_contact_with_activities(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get contact with all activities (full history).
    """
    # Get contact
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company.id,
                Contact.deleted_at.is_(None)
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Get activities
    activities_result = await session.execute(
        select(ContactActivity)
        .where(ContactActivity.contact_id == contact_id)
        .order_by(desc(ContactActivity.activity_at))
        .limit(100)
    )
    activities = activities_result.scalars().all()
    
    return ContactWithActivitiesResponse(
        id=contact.id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company_name=contact.company_name,
        job_title=contact.job_title,
        linkedin_url=contact.linkedin_url,
        source=contact.source,
        status=contact.status,
        last_reply_at=contact.last_reply_at,
        provenance=contact.provenance,
        platform_state=contact.platform_state,
        activities=[ActivityResponse.model_validate(a) for a in activities]
    )


@router.get("/replies/recent", response_model=List[ContactWithActivitiesResponse])
async def get_recent_replies(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get contacts with recent replies, sorted by last reply time.
    """
    result = await session.execute(
        select(Contact)
        .where(and_(
            Contact.company_id == company.id,
            Contact.deleted_at.is_(None),
            Contact.last_reply_at.isnot(None)
        ))
        .order_by(desc(Contact.last_reply_at))
        .limit(limit)
    )
    contacts = result.scalars().all()
    
    responses = []
    for contact in contacts:
        # Get last few activities
        activities_result = await session.execute(
            select(ContactActivity)
            .where(ContactActivity.contact_id == contact.id)
            .order_by(desc(ContactActivity.activity_at))
            .limit(5)
        )
        activities = activities_result.scalars().all()
        
        responses.append(ContactWithActivitiesResponse(
            id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company_name=contact.company_name,
            job_title=contact.job_title,
            linkedin_url=contact.linkedin_url,
            source=contact.source,
            status=contact.status,
            last_reply_at=contact.last_reply_at,
            provenance=contact.provenance,
            platform_state=contact.platform_state,
            activities=[ActivityResponse.model_validate(a) for a in activities]
        ))
    
    return responses


# ── Contact Sync: Full Load / Incremental ──

@router.post("/contact-sync/start")
async def start_contact_sync(
    background_tasks: BackgroundTasks,
    phase: str = Query("full_load", regex="^(full_load|incremental)$"),
    project_id: Optional[int] = Query(None, description="Sync only this project's campaigns (fast)"),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Launch contact sync as a background task.

    - phase=full_load: resets offsets to 0, syncs all leads (no limit)
    - phase=incremental: syncs from saved offset with 3K limit
    - project_id: if set, only sync campaigns for this project (much faster)
    """
    import redis.asyncio as aioredis
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = aioredis.from_url(redis_url)
    try:
        status = await redis.get("contact_sync:status")
        if status and status.decode() == "running":
            raise HTTPException(409, "Contact sync already running")

        if phase == "full_load":
            await redis.set("contact_sync:smartlead_offset", "0")
            await redis.set("contact_sync:getsales_offset", "0")

        await redis.set("contact_sync:status", "running")
        await redis.delete("contact_sync:cancel")
        await redis.delete("contact_sync:progress")
        await redis.hset("contact_sync:progress", mapping={
            "status": "running",
            "phase": phase,
            "started_at": datetime.utcnow().isoformat(),
            "sl_processed": "0", "sl_created": "0", "sl_updated": "0",
            "sl_skipped": "0", "sl_offset": "0", "sl_has_more": "1",
            "gs_processed": "0", "gs_offset": "0", "gs_total": "0",
            "elapsed": "0",
        })
    finally:
        await redis.aclose()

    max_leads = 999999 if phase == "full_load" else 3000

    async def _run_sync():
        redis_inner = aioredis.from_url(redis_url)
        try:
            sync_service = get_crm_sync_service()

            async def _run_platform(plat: str):
                async with async_session_maker() as s:
                    await sync_service.sync_contacts_global(
                        s, company.id,
                        max_leads=max_leads,
                        report_progress=True,
                        platform=plat,
                        project_id=project_id,
                    )

            if phase == "full_load" and not project_id:
                # Global full load: SmartLead only (GetSales has ES 10K offset limit)
                await _run_platform("smartlead")
            elif project_id:
                # Project-scoped: run both in parallel (small dataset, fast)
                await asyncio.gather(
                    _run_platform("smartlead"),
                    _run_platform("getsales"),
                )
            else:
                await asyncio.gather(
                    _run_platform("smartlead"),
                    _run_platform("getsales"),
                )
            await redis_inner.set("contact_sync:status", "completed")
        except Exception as e:
            logger.error(f"[CONTACT-SYNC] Background sync failed: {e}")
            await redis_inner.set("contact_sync:status", "failed")
        finally:
            await redis_inner.aclose()

    background_tasks.add_task(_run_sync)
    return {"status": "started", "phase": phase, "max_leads": max_leads}


@router.get("/contact-sync/progress")
async def get_sync_progress(
    company: Company = Depends(get_required_company),
):
    """Get real-time contact sync progress from Redis."""
    import redis.asyncio as aioredis
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = aioredis.from_url(redis_url)
    try:
        progress = await redis.hgetall("contact_sync:progress")
        if not progress:
            return {"status": "idle", "message": "No sync has been run yet"}

        # Decode bytes to str
        decoded = {k.decode(): v.decode() for k, v in progress.items()}
        # Derive overall status from per-platform statuses
        sl_status = decoded.get("status_smartlead", "pending")
        gs_status = decoded.get("status_getsales", "pending")
        overall = decoded.get("status", "running")
        if sl_status == "completed" and gs_status == "completed":
            overall = "completed"
        elif "failed" in (sl_status, gs_status):
            overall = "failed"
        elif "running" in (sl_status, gs_status):
            overall = "running"

        return {
            "status": overall,
            "phase": decoded.get("phase", "unknown"),
            "started_at": decoded.get("started_at"),
            "smartlead": {
                "status": sl_status,
                "processed": int(decoded.get("sl_processed", "0")),
                "created": int(decoded.get("sl_created", "0")),
                "updated": int(decoded.get("sl_updated", "0")),
                "skipped": int(decoded.get("sl_skipped", "0")),
                "offset": int(decoded.get("sl_offset", "0")),
                "has_more": decoded.get("sl_has_more", "0") == "1",
                "elapsed_seconds": int(decoded.get("elapsed_smartlead", decoded.get("elapsed", "0"))),
            },
            "getsales": {
                "status": gs_status,
                "processed": int(decoded.get("gs_processed", "0")),
                "offset": int(decoded.get("gs_offset", "0")),
                "total": int(decoded.get("gs_total", "0")),
                "elapsed_seconds": int(decoded.get("elapsed_getsales", decoded.get("elapsed", "0"))),
            },
            "error": decoded.get("error"),
        }
    finally:
        await redis.aclose()


@router.post("/contact-sync/cancel")
async def cancel_contact_sync(
    company: Company = Depends(get_required_company),
):
    """Cancel a running contact sync."""
    import redis.asyncio as aioredis
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = aioredis.from_url(redis_url)
    try:
        status = await redis.get("contact_sync:status")
        if not status or status.decode() != "running":
            raise HTTPException(400, "No sync is currently running")

        await redis.set("contact_sync:cancel", "1")
        return {"status": "cancel_requested"}
    finally:
        await redis.aclose()


_backfill_status = {"running": False, "stats": {}, "started_at": None}


@router.post("/fast-backfill")
async def fast_backfill(
    platform: str = Query("all", description="smartlead, getsales, or all"),
    concurrency: int = Query(10, description="Max concurrent API calls"),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Fire-and-forget fast backfill. Returns immediately, work runs in background.

    Monitor progress via GET /crm-sync/fast-backfill/status or docker logs.
    """
    if _backfill_status["running"]:
        return {"status": "already_running", **_backfill_status["stats"]}

    import json as json_mod
    from app.models.campaign import Campaign as CampaignModel

    # Pre-fetch campaign data while we have the session
    camp_data = []
    if platform in ("all", "smartlead"):
        camp_result = await session.execute(
            select(
                CampaignModel.id, CampaignModel.external_id,
                CampaignModel.name, CampaignModel.leads_count,
                CampaignModel.project_id,
            ).where(
                and_(
                    CampaignModel.platform == "smartlead",
                    CampaignModel.external_id.isnot(None),
                    func.coalesce(CampaignModel.leads_count, 0) > 0,
                )
            ).order_by(CampaignModel.leads_count.desc())
        )
        camp_data = camp_result.all()

    company_id = company.id

    async def _run_backfill():
        _backfill_status["running"] = True
        _backfill_status["started_at"] = datetime.utcnow().isoformat()
        sync_service = get_crm_sync_service()
        sem = asyncio.Semaphore(concurrency)
        stats = {"sl_campaigns": 0, "sl_leads": 0, "sl_created": 0, "sl_updated": 0,
                 "sl_skipped": 0, "sl_errors": 0,
                 "gs_contacts": 0, "gs_created": 0, "gs_updated": 0, "gs_skipped": 0,
                 "gs_errors": 0, "elapsed_seconds": 0}
        _backfill_status["stats"] = stats
        start_time = datetime.utcnow()

        try:
            # --- SmartLead ---
            if platform in ("all", "smartlead"):
                total_camps = len(camp_data)
                stats["sl_campaigns"] = total_camps
                completed_count = {"n": 0}
                logger.info(f"[FAST-BACKFILL] SmartLead: {total_camps} campaigns, concurrency={concurrency}")

                async def _export_and_process(camp_row):
                    camp_id, ext_id, camp_name, leads_count, project_id = camp_row
                    async with sem:
                        try:
                            csv_rows = await sync_service.smartlead.export_campaign_leads(ext_id)
                            if not csv_rows:
                                completed_count["n"] += 1
                                return {"created": 0, "updated": 0, "skipped": 0, "leads": 0}

                            local_stats = {"created": 0, "updated": 0, "skipped": 0, "leads": len(csv_rows)}

                            # Update campaign leads_count
                            actual_count = len(csv_rows)
                            async with async_session_maker() as camp_session:
                                from app.models.campaign import Campaign as CM
                                camp_obj = await camp_session.get(CM, camp_id)
                                if camp_obj:
                                    camp_obj.leads_count = actual_count
                                    camp_obj.synced_leads_count = actual_count
                                    camp_obj.last_contact_sync_at = datetime.utcnow()
                                    await camp_session.commit()

                            # Process in batches of 100
                            BATCH = 100
                            for i in range(0, len(csv_rows), BATCH):
                                batch = csv_rows[i:i + BATCH]
                                async with async_session_maker() as local_session:
                                    for row in batch:
                                        try:
                                            custom_fields_raw = row.get("custom_fields", "{}")
                                            try:
                                                custom_fields = json_mod.loads(custom_fields_raw) if custom_fields_raw else {}
                                            except (json_mod.JSONDecodeError, TypeError):
                                                custom_fields = {}
                                            reply_count = int(row.get("reply_count", 0) or 0)
                                            lead = {
                                                "id": row.get("id", ""),
                                                "email": row.get("email", ""),
                                                "first_name": row.get("first_name", ""),
                                                "last_name": row.get("last_name", ""),
                                                "company_name": row.get("company_name", ""),
                                                "phone_number": row.get("phone_number", ""),
                                                "linkedin_profile": row.get("linkedin_profile", ""),
                                                "location": row.get("location", ""),
                                                "custom_fields": custom_fields,
                                                "created_at": row.get("created_at", ""),
                                                "_raw_csv_row": dict(row),
                                                "campaigns": [{
                                                    "campaign_name": camp_name,
                                                    "campaign_id": ext_id,
                                                    "lead_status": row.get("status", "ACTIVE"),
                                                    "created_at": row.get("created_at", ""),
                                                    "reply_time": True if reply_count > 0 else None,
                                                }],
                                            }
                                            result = await sync_service._process_smartlead_lead(
                                                local_session, company_id, lead, campaign_project_id=project_id
                                            )
                                            local_stats[result] += 1
                                        except Exception:
                                            local_stats["skipped"] += 1
                                            try:
                                                await local_session.rollback()
                                            except Exception:
                                                pass
                                    try:
                                        await local_session.commit()
                                    except Exception:
                                        try:
                                            await local_session.rollback()
                                        except Exception:
                                            pass

                            completed_count["n"] += 1
                            n = completed_count["n"]
                            elapsed = (datetime.utcnow() - start_time).total_seconds()
                            # Update running stats
                            stats["sl_leads"] += local_stats["leads"]
                            stats["sl_created"] += local_stats["created"]
                            stats["sl_updated"] += local_stats["updated"]
                            stats["sl_skipped"] += local_stats["skipped"]
                            stats["elapsed_seconds"] = elapsed
                            if n % 10 == 0 or n == total_camps:
                                pct = n * 100 / total_camps
                                eta = elapsed / n * (total_camps - n) if n > 0 else 0
                                logger.info(f"[FAST-BACKFILL] Progress: {n}/{total_camps} ({pct:.0f}%) "
                                            f"elapsed={elapsed:.0f}s eta={eta:.0f}s "
                                            f"total_leads={stats['sl_leads']} created={stats['sl_created']} updated={stats['sl_updated']}")
                            return local_stats
                        except Exception as e:
                            completed_count["n"] += 1
                            stats["sl_errors"] += 1
                            logger.warning(f"[FAST-BACKFILL] Campaign {camp_name} failed: {e}")
                            return {"created": 0, "updated": 0, "skipped": 0, "leads": 0, "error": str(e)}

                await asyncio.gather(
                    *[_export_and_process(c) for c in camp_data],
                    return_exceptions=True,
                )
                logger.info(f"[FAST-BACKFILL] SmartLead done: {stats['sl_leads']} leads, "
                             f"created={stats['sl_created']}, updated={stats['sl_updated']}")

            # --- GetSales (flow-based, iterates registered campaigns) ---
            if platform in ("all", "getsales"):
                try:
                    from app.models.campaign import Campaign as CampaignModel
                    async with async_session_maker() as gs_session:
                        gs_result = await gs_session.execute(
                            select(CampaignModel).where(
                                and_(
                                    CampaignModel.platform == "getsales",
                                    CampaignModel.external_id.isnot(None),
                                )
                            )
                        )
                        gs_campaigns = gs_result.scalars().all()

                    logger.info(f"[FAST-BACKFILL] GetSales: {len(gs_campaigns)} campaigns (flow-based), concurrency={concurrency}")

                    async def _sync_gs_campaign(camp_data):
                        async with sem:
                            local_stats = {"created": 0, "updated": 0, "skipped": 0, "contacts": 0}
                            try:
                                async with async_session_maker() as local_session:
                                    camp_result = await local_session.execute(
                                        select(CampaignModel).where(CampaignModel.id == camp_data["id"])
                                    )
                                    campaign = camp_result.scalar()
                                    if not campaign:
                                        return local_stats

                                    synced = await sync_service._sync_getsales_campaign_contacts(
                                        local_session, company_id, campaign, max_leads=50000,
                                        start_offset=0,
                                    )
                                    campaign.last_contact_sync_at = datetime.utcnow()
                                    await local_session.commit()

                                    local_stats["created"] = synced.get("created", 0)
                                    local_stats["updated"] = synced.get("updated", 0)
                                    local_stats["skipped"] = synced.get("skipped", 0)
                                    local_stats["contacts"] = sum(synced.get(k, 0) for k in ("created", "updated", "skipped"))
                            except Exception as e:
                                logger.warning(f"[FAST-BACKFILL] GetSales campaign {camp_data['name']} failed: {e}")
                            stats["gs_contacts"] += local_stats["contacts"]
                            stats["gs_created"] += local_stats["created"]
                            stats["gs_updated"] += local_stats["updated"]
                            stats["gs_skipped"] += local_stats["skipped"]
                            stats["elapsed_seconds"] = (datetime.utcnow() - start_time).total_seconds()
                            return local_stats

                    gs_camp_data = [{"id": c.id, "name": c.name} for c in gs_campaigns]
                    await asyncio.gather(
                        *[_sync_gs_campaign(c) for c in gs_camp_data],
                        return_exceptions=True,
                    )
                    logger.info(f"[FAST-BACKFILL] GetSales done: {stats['gs_contacts']} contacts, "
                                 f"created={stats['gs_created']}, updated={stats['gs_updated']}")
                except Exception as e:
                    logger.warning(f"[FAST-BACKFILL] GetSales failed: {e}")
                    stats["gs_errors"] += 1

            stats["elapsed_seconds"] = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[FAST-BACKFILL] COMPLETE in {stats['elapsed_seconds']:.0f}s: {stats}")
        except Exception as e:
            logger.error(f"[FAST-BACKFILL] Fatal error: {e}")
        finally:
            _backfill_status["running"] = False

    asyncio.create_task(_run_backfill())
    return {"status": "started", "sl_campaigns": len(camp_data), "platform": platform, "concurrency": concurrency}


@router.get("/fast-backfill/status")
async def fast_backfill_status():
    """Check progress of running fast-backfill."""
    return {**_backfill_status}
