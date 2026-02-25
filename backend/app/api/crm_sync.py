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
from sqlalchemy import select, and_, desc, String
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
    webhook_base_url: str = Body(None, embed=True),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Set up webhooks in Smartlead and GetSales to send events to our CRM.
    
    If webhook_base_url is not provided, uses the default based on settings.
    
    This will:
    - For Smartlead: Configure webhooks on all active campaigns for EMAIL_REPLY, LEAD_CATEGORY_UPDATED
    - For GetSales: Configure webhooks for contact_replied_linkedin_message, connection_accepted
    """
    sync_service = get_crm_sync_service()
    
    # Default webhook base URL
    if not webhook_base_url:
        from app.core.config import settings as _s
        webhook_base_url = f"{_s.WEBHOOK_BASE_URL}/api/crm-sync/webhook"
    
    results = {"getsales": None, "smartlead": None}
    
    # Set up GetSales webhooks
    if sync_service.getsales:
        try:
            getsales_url = f"{webhook_base_url}/getsales"
            results["getsales"] = await sync_service.getsales.setup_crm_webhooks(getsales_url)
        except Exception as e:
            logger.error(f"Failed to set up GetSales webhooks: {e}")
            results["getsales"] = {"error": str(e)}
    
    # Set up Smartlead webhooks
    if sync_service.smartlead:
        try:
            smartlead_url = f"{webhook_base_url}/smartlead"
            results["smartlead"] = await sync_service.smartlead.setup_crm_webhooks(smartlead_url)
        except Exception as e:
            logger.error(f"Failed to set up Smartlead webhooks: {e}")
            results["smartlead"] = {"error": str(e)}
    
    return {
        "success": True,
        "message": "Webhook setup complete",
        "results": results
    }




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
                                    "source": "smartlead"
                                }]})
                                # Parse reply_time
                                reply_time_str = reply.get("reply_time")
                                if reply_time_str:
                                    try:
                                        contact.last_reply_at = datetime.fromisoformat(reply_time_str.replace("Z", ""))
                                    except:
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
                                    except:
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
                            "source": "smartlead"
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
                               'source', COALESCE(pr.source, 'smartlead')
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

    # Per-campaign stats from contacts
    campaign_stats = []
    if campaign_names:
        for name in sorted(campaign_names):
            # Determine source from allCampaigns or from contacts data
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

            db_campaign = await session.execute(
                select(Campaign).where(
                    and_(
                        Campaign.company_id == company_id,
                        Campaign.name == name,
                    )
                )
            )
            db_camp = db_campaign.scalar_one_or_none()

            campaign_stats.append({
                "name": name,
                "platform": db_camp.platform if db_camp else ("smartlead" if any(c.lower().startswith("easystaff") or c.lower().startswith("inxy") or c.lower().startswith("squarefi") or c.lower().startswith("deliryo") or c.lower().startswith("abeta") or c.lower().startswith("palark") for c in [name]) else "unknown"),
                "status": db_camp.status if db_camp else "linked",
                "contacts": contact_count_q.scalar() or 0,
                "replied": replied_q.scalar() or 0,
                "external_id": db_camp.external_id if db_camp else None,
            })

    # Project-level reply stats (last 24h and 7d)
    since_24h = datetime.utcnow() - __import__('datetime').timedelta(hours=24)
    since_7d = datetime.utcnow() - __import__('datetime').timedelta(days=7)

    # Recent processed replies for this project's campaigns
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

    # Determine current polling interval
    reply_count = scheduler_status.get("reply_check_count", 0)
    webhook_healthy = scheduler_status.get("webhook_healthy", True)
    if reply_count <= 3:
        current_reply_interval = "3 min (startup catch-up)"
    elif not webhook_healthy:
        current_reply_interval = "3 min (webhooks unhealthy)"
    else:
        current_reply_interval = "10 min (steady state)"

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
            "intervals": [
                {"task": "Reply polling", "interval": current_reply_interval, "last_run": scheduler_status.get("last_reply_check")},
                {"task": "Full CRM sync", "interval": "30 min", "last_run": scheduler_status.get("last_sync")},
                {"task": "Webhook registration", "interval": "5 min", "last_run": scheduler_status.get("last_webhook_check")},
                {"task": "Conversation sync", "interval": "3 min", "last_run": None},
                {"task": "Sheet sync", "interval": "5 min", "last_run": None},
                {"task": "Event recovery", "interval": "5 min", "last_run": None},
            ],
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
        "campaigns": campaign_stats,
        "latest_events": await _get_latest_events(session, campaign_names),
    }


async def _get_latest_events(session: AsyncSession, campaign_names: list) -> dict:
    """Fetch latest webhook events and processed replies for debugging."""
    from app.models.reply import WebhookEventModel, ProcessedReply
    from app.models.contact import ContactActivity
    from sqlalchemy import func, desc

    result: dict = {"webhook_events": [], "processed_replies": [], "activities": []}

    # Latest 5 webhook events (any type)
    events_q = await session.execute(
        select(WebhookEventModel)
        .order_by(desc(WebhookEventModel.created_at))
        .limit(5)
    )
    for ev in events_q.scalars().all():
        payload_preview = (ev.payload or "")[:200]
        result["webhook_events"].append({
            "id": ev.id,
            "event_type": ev.event_type,
            "campaign_id": ev.campaign_id,
            "lead_email": ev.lead_email,
            "processed": ev.processed,
            "error": ev.error[:150] if ev.error else None,
            "retry_count": ev.retry_count or 0,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "processed_at": ev.processed_at.isoformat() if ev.processed_at else None,
            "payload_preview": payload_preview,
        })

    # Latest 5 processed replies for this project's campaigns
    if campaign_names:
        replies_q = await session.execute(
            select(ProcessedReply)
            .where(ProcessedReply.campaign_name.in_(campaign_names))
            .order_by(desc(ProcessedReply.received_at))
            .limit(5)
        )
    else:
        replies_q = await session.execute(
            select(ProcessedReply)
            .order_by(desc(ProcessedReply.received_at))
            .limit(5)
        )
    for r in replies_q.scalars().all():
        result["processed_replies"].append({
            "id": r.id,
            "source": r.source,
            "channel": r.channel,
            "campaign_name": r.campaign_name,
            "lead_email": r.lead_email,
            "lead_name": f"{r.lead_first_name or ''} {r.lead_last_name or ''}".strip(),
            "category": r.category,
            "approval_status": r.approval_status,
            "received_at": r.received_at.isoformat() if r.received_at else None,
        })

    # Latest 5 contact activities for this project
    activities_q = await session.execute(
        select(ContactActivity)
        .order_by(desc(ContactActivity.activity_at))
        .limit(5)
    )
    for a in activities_q.scalars().all():
        result["activities"].append({
            "id": a.id,
            "activity_type": a.activity_type,
            "channel": a.channel,
            "contact_id": a.contact_id,
            "activity_at": a.activity_at.isoformat() if a.activity_at else None,
        })

    return result


# ============= Webhook Endpoints =============

@router.post("/webhook/smartlead")
async def smartlead_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Webhook endpoint for Smartlead events.
    
    Smartlead webhook payload structure (from n8n reference):
    {
      "body": {
        "event_type": "EMAIL_REPLY" | "LEAD_CATEGORY_UPDATED" | "EMAIL_SENT",
        "lead_email": "...",
        "lead_id": 123,
        "campaign_id": 456,
        "campaign_name": "...",
        "from_email": "...",
        "to_email": "...",
        "event_timestamp": "2025-...",
        "lead_data": {
          "first_name": "...",
          "last_name": "...",
          "company_name": "...",
          "linkedin_profile": "...",
          "category": { "name": "Positive Reply", "sentiment_type": "positive" }
        },
        "reply_message": { "text": "..." },
        "last_reply": { "email_body": "...", "time": "..." },
        "history": [ { "type": "SENT"|"REPLY", "email_body": "...", "time": "..." } ]
      }
    }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Handle both direct payload and nested body (n8n style)
    body = payload.get("body", payload)
    
    event_type = body.get("event_type") or body.get("event")
    lead_email = (
        body.get("lead_email") or 
        body.get("to_email") or 
        body.get("sl_lead_email") or
        body.get("email")
    )
    campaign_id = body.get("campaign_id")
    campaign_name = body.get("campaign_name")
    lead_id = body.get("lead_id")
    lead_data = body.get("lead_data", {})
    
    logger.info(f"Smartlead webhook received: {event_type} for {lead_email}")

    # Skip events from campaigns belonging to disabled projects
    if campaign_name:
        disabled = await _get_disabled_project_info(session)
        if campaign_name in disabled["campaigns"]:
            logger.info(f"Smartlead webhook skipped: campaign '{campaign_name}' (webhooks disabled)")
            return {"status": "skipped", "reason": "webhooks disabled for project"}

    if not lead_email:
        return {"status": "ignored", "reason": "no email"}
    
    # Find contact by email or smartlead_id
    contact = None
    if lead_id:
        result = await session.execute(
            select(Contact).where(
                and_(Contact.smartlead_id == str(lead_id), Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    if not contact:
        result = await session.execute(
            select(Contact).where(
                and_(Contact.email == lead_email.lower(), Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    # Also try to match by LinkedIn URL (for contacts from GetSales)
    linkedin_profile = lead_data.get("linkedin_profile") or lead_data.get("linkedin_url")
    if not contact and linkedin_profile:
        normalized_linkedin = linkedin_profile.lower().rstrip("/")
        if "linkedin.com/in/" in normalized_linkedin:
            linkedin_handle = _extract_linkedin_handle(linkedin_profile)
            result = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.linkedin_url.ilike(f"%/in/{linkedin_handle}%"),
                        Contact.deleted_at.is_(None)
                    )
                )
            )
            contact = result.scalar_one_or_none()
    
    # If we found an existing contact (from GetSales), merge Smartlead data
    if contact and not contact.smartlead_id:
        logger.info(f"Merging Smartlead data into existing contact: {contact.email}")
        contact.smartlead_id = str(lead_id) if lead_id else None
        if linkedin_profile and not contact.linkedin_url:
            contact.linkedin_url = _normalize_linkedin(linkedin_profile)
        # Upgrade placeholder email with real email from Smartlead
        if lead_email and contact.email and any(
            p in contact.email for p in ("@linkedin.placeholder", "@getsales.local", "@placeholder.local")
        ):
            logger.info(f"Upgrading placeholder email {contact.email} -> {lead_email}")
            contact.email = lead_email.lower().strip()
            if '@' in lead_email:
                contact.domain = lead_email.split('@')[1].lower()
        # Add campaign to existing campaigns if not already there
        if campaign_name or campaign_id:
            campaign_entry = {
                "name": campaign_name,
                "id": str(campaign_id) if campaign_id else None,
                "source": "smartlead"
            }
            existing_campaigns = parse_campaigns(contact.campaigns)
            existing_ids = {c.get("id") for c in existing_campaigns if isinstance(c, dict)}
            if str(campaign_id) not in existing_ids:
                existing_campaigns.append(campaign_entry)
                contact.campaigns = existing_campaigns
    
    if not contact:
        # Create new contact from webhook data
        logger.info(f"Creating new contact from Smartlead webhook: {lead_email}")
        contact = Contact(
            company_id=1,  # Default company
            email=lead_email.lower().strip(),
            first_name=lead_data.get("first_name"),
            last_name=lead_data.get("last_name"),
            company_name=lead_data.get("company_name"),
            linkedin_url=_normalize_linkedin(lead_data.get("linkedin_profile")),
            source="smartlead",
            smartlead_id=str(lead_id) if lead_id else None,
            status="new",
        )
        contact.mark_synced("smartlead")
        if campaign_name or campaign_id:
            contact.set_platform("smartlead", {"campaigns": [{
                "name": campaign_name,
                "id": str(campaign_id) if campaign_id else None,
                "source": "smartlead"
            }]})
        session.add(contact)
        await session.flush()  # Get contact.id
    
    
    # Map event type to activity type (Smartlead uses uppercase)
    activity_map = {
        "EMAIL_REPLY": "email_replied",
        "lead.replied": "email_replied",
        "email.replied": "email_replied",
        "reply": "email_replied",
        "EMAIL_SENT": "email_sent",
        "email.sent": "email_sent",
        "sent": "email_sent",
        "EMAIL_OPENED": "email_opened",
        "email.opened": "email_opened",
        "open": "email_opened",
        "EMAIL_CLICKED": "email_clicked",
        "email.clicked": "email_clicked",
        "click": "email_clicked",
        "EMAIL_BOUNCED": "email_bounced",
        "email.bounced": "email_bounced",
        "bounce": "email_bounced",
        "LEAD_CATEGORY_UPDATED": "category_updated",
    }
    
    activity_type = activity_map.get(event_type, event_type or "unknown")
    
    # Extract reply content
    reply_text = None
    reply_body = None
    if body.get("reply_message"):
        reply_text = body["reply_message"].get("text")
    if body.get("last_reply"):
        reply_body = body["last_reply"].get("email_body")
    
    # Get subject from history if available
    subject = None
    history = body.get("history", [])
    for entry in history:
        if entry.get("subject"):
            subject = entry.get("subject")
            break
    
    # Parse event timestamp
    event_time = datetime.utcnow()
    if body.get("event_timestamp"):
        try:
            parsed = datetime.fromisoformat(body["event_timestamp"].replace("Z", "+00:00"))
            event_time = parsed.replace(tzinfo=None)  # Store as naive UTC
        except:
            pass
    
    # Create activity
    activity = ContactActivity(
        contact_id=contact.id,
        company_id=contact.company_id,
        activity_type=activity_type,
        channel="email",
        direction="inbound" if "replied" in activity_type else "outbound",
        source="smartlead",
        source_id=str(lead_id) if lead_id else None,
        subject=subject,
        body=reply_body or reply_text,
        snippet=(reply_text or reply_body or "")[:200] if (reply_text or reply_body) else None,
        extra_data={
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "raw_event": event_type,
            "category": lead_data.get("category"),
            "history_count": len(history),
            "from_email": body.get("from_email"),
            "to_email": body.get("to_email"),
        },
        activity_at=event_time
    )
    session.add(activity)
    
    # Update contact if replied — use status machine for forward-only transitions
    from app.services.status_machine import transition_status, status_from_ai_category
    if "replied" in activity_type:
        contact.mark_replied("email", at=event_time)
        contact.last_reply_at = event_time

    # Map Smartlead category → 13-status via state machine
    if lead_data.get("category"):
        category = lead_data["category"]
        cat_name = category.get("name", "").lower()
        contact.update_platform_status("smartlead", category.get("name"))
        # Map Smartlead category names to AI categories for status machine
        sl_to_ai = {
            "interested": "interested",
            "meeting booked": "meeting_request",
            "out of office": "out_of_office",
            "not interested": "not_interested",
            "wrong person": "wrong_person",
            "do not contact": "not_interested",
            "auto reply": "out_of_office",
        }
        ai_cat = sl_to_ai.get(cat_name)
        if ai_cat:
            target = status_from_ai_category(ai_cat)
            new_st, ok, msg = transition_status(contact.status, target)
            if ok:
                contact.status = new_st
                logger.info(f"SmartLead webhook: {contact.email} → {new_st} (from {cat_name})")
    elif "replied" in activity_type:
        # No category yet — default to "interested" if allowed
        new_st, ok, _msg = transition_status(contact.status, "interested")
        if ok:
            contact.status = new_st
    
    # Update smartlead_id if not set
    if lead_id and not contact.smartlead_id:
        contact.smartlead_id = str(lead_id)
    
    await session.commit()

    # H1 FIX: Route EMAIL_REPLY events through the reply processor so replies
    # arriving at this endpoint also get classified, drafted, and notified —
    # prevents silent data loss when SmartLead is configured to the wrong URL.
    if "replied" in activity_type and lead_email:
        full_payload = {
            "event_type": event_type or "EMAIL_REPLY",
            "campaign_id": str(campaign_id) if campaign_id else None,
            "campaign_name": campaign_name,
            "lead_email": lead_email,
            "to_email": lead_email,
            "to_name": f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip(),
            "first_name": lead_data.get("first_name", ""),
            "last_name": lead_data.get("last_name", ""),
            "company_name": lead_data.get("company_name", ""),
            "email_subject": subject,
            "email_body": reply_body or reply_text or "",
            "preview_text": reply_text or reply_body or "",
            "sl_email_lead_id": str(lead_id) if lead_id else "",
            "linkedin_profile": lead_data.get("linkedin_profile", ""),
            "time_replied": body.get("event_timestamp"),
            "_source": "crm_sync_webhook",
        }
        asyncio.create_task(_process_smartlead_reply_safe(full_payload))
        logger.info(f"[CRM-SYNC] Queued reply processing for {lead_email}")

    return {"status": "processed", "activity_id": activity.id}


async def _process_smartlead_reply_safe(payload: dict):
    """Process a SmartLead reply via the shared reply processor. Fire-and-forget."""
    from app.services.reply_processor import process_reply_webhook

    try:
        async with async_session_maker() as session:
            await process_reply_webhook(payload, session)
            await session.commit()
    except Exception as e:
        logger.error(f"[CRM-SYNC] Reply processing failed (non-fatal): {e}")


@router.post("/webhook/getsales/bulk-import")
async def getsales_bulk_import_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Webhook endpoint for GetSales bulk contact export.
    
    This is triggered when you use GetSales UI:
    1. Select all contacts
    2. Export > Webhook
    3. Select this webhook
    
    GetSales will send each contact one by one to this endpoint.
    """
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
    
    GetSales sends webhooks with this structure:
    {
      "body": {
        "contact": { uuid, first_name, last_name, linkedin_url, work_email, ... },
        "account": { name, website, ... },
        "automation": { uuid, name, ... },
        "linkedin_message": { text, type, sent_at, ... },
        "contact_markers": { ... },
        "latest_linkedin_conversation_thread": { messaging_thread, ... }
      }
    }
    
    The linkedin_message.type can be:
    - "inbox" = received reply from contact
    - "outbox" = message we sent
    """
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
    logger.info(f"GetSales webhook: contact={contact_data.get('name')}, message_type={message_type}, automation={automation_name}")

    # Skip events from automations belonging to disabled projects (startswith matching)
    disabled = await _get_disabled_project_info(session)
    if automation_name and disabled["projects"]:
        auto_lower = automation_name.lower()
        if any(auto_lower.startswith(pname) for pname in disabled["projects"]):
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
    
    # If contact has a placeholder email and webhook provides a real one, update it
    if is_existing_contact and lead_email and contact.email and any(
        p in contact.email for p in ("@linkedin.placeholder", "@getsales.local", "@placeholder.local")
    ):
        logger.info(f"Updating placeholder email {contact.email} -> {lead_email}")
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
        
        contact = Contact(
            company_id=1,  # Default company
            email=lead_email or f"gs_{lead_uuid}@linkedin.placeholder",
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
        except:
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
        try:
            from app.services.reply_processor import process_getsales_reply

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

        # Append to touches JSON
        from datetime import datetime as dt
        touch = {
            "at": activity_at.isoformat() if activity_at else dt.utcnow().isoformat(),
            "campaign": automation_data.get("name"),
            "source": "getsales",
            "channel": "linkedin",
            "type": "reply",
            "category": category,
            "message": message_text[:100] if message_text else None
        }
        if contact.touches:
            try:
                touches = json.loads(contact.touches) if isinstance(contact.touches, str) else contact.touches
                touches.append(touch)
                contact.touches = touches
            except:
                contact.touches = [touch]
        else:
            contact.touches = [touch]
        
        # Append to getsales_raw for debugging
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
            except:
                contact.getsales_raw = {"webhooks": [webhook_entry]}
        else:
            contact.getsales_raw = {"webhooks": [webhook_entry]}
        contact.update_platform_raw("getsales", contact.getsales_raw)
        
        # Send Telegram notification for LinkedIn reply (with per-project routing)
        try:
            from app.services.notification_service import notify_linkedin_reply
            flow_name = automation_data.get("name") or get_getsales_flow_name(None, contact.campaigns)
            contact_name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip() or "Unknown"
            
            await notify_linkedin_reply(
                contact_name=contact_name,
                contact_email=contact.email or "N/A",
                flow_name=flow_name,
                message_text=message_text or "",
                campaign_name=flow_name  # Use flow name for project routing
            )
        except Exception as e:
            logger.warning(f"Telegram notification failed (non-fatal): {e}")
    
    # Enrich contact with flow/automation info if not already present
    if automation_data.get("name") or automation_data.get("uuid"):
        flow_entry = {
            "name": automation_data.get("name"),
            "id": automation_data.get("uuid"),
            "source": "getsales",
            "status": "active"
        }
        # Parse existing campaigns
        existing_campaigns = parse_campaigns(contact.campaigns)
        
        # Check if this flow is already in campaigns
        existing_flow_ids = {c.get("id") for c in existing_campaigns if isinstance(c, dict)}
        if automation_data.get("uuid") not in existing_flow_ids:
            existing_campaigns.append(flow_entry)
            contact.campaigns = existing_campaigns
    
    await session.commit()
    
    return {
        "status": "processed",
        "activity_id": activity.id if not is_duplicate else None,
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
