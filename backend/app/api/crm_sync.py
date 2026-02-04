"""
CRM Sync API endpoints.

Provides:
- Manual sync triggers
- Webhook endpoints for Smartlead and GetSales
- Activity history endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import hashlib
import hmac

from app.db import get_session
from app.models import Company, Contact, ContactActivity
from app.api.companies import get_required_company
from app.services.crm_sync_service import get_crm_sync_service, CRMSyncService, get_getsales_flow_name
from app.services.notification_service import send_telegram_notification

logger = logging.getLogger(__name__)


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
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: str
    status: str
    has_replied: bool
    last_reply_at: Optional[datetime] = None
    reply_channel: Optional[str] = None
    smartlead_status: Optional[str] = None
    getsales_status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    activities: List[ActivityResponse] = []
    
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
        webhook_base_url = "http://46.62.210.24:8000/api/crm-sync/webhook"
    
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
                            
                            if contact and not contact.has_replied:
                                contact.has_replied = True
                                contact.status = "replied"
                                # Parse reply_time string to datetime
                                reply_time_str = reply.get("reply_time")
                                if reply_time_str:
                                    try:
                                        from datetime import datetime
                                        contact.last_reply_at = datetime.fromisoformat(reply_time_str.replace("Z", ""))
                                    except:
                                        contact.last_reply_at = None
                                contact.reply_channel = "email"
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
            Contact.has_replied == True
        ))
    )
    
    # Get last synced time
    last_sync = await session.execute(
        select(func.max(Contact.last_synced_at))
        .where(Contact.company_id == company.id)
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
        "last_synced_at": last_sync.scalar()
    }


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
        # Add campaign to existing campaigns if not already there
        if campaign_name or campaign_id:
            campaign_entry = {
                "name": campaign_name,
                "id": str(campaign_id) if campaign_id else None,
                "source": "smartlead"
            }
            existing_campaigns = []
            if contact.campaigns:
                try:
                    if isinstance(contact.campaigns, str):
                        existing_campaigns = json.loads(contact.campaigns)
                    elif isinstance(contact.campaigns, list):
                        existing_campaigns = contact.campaigns
                except:
                    existing_campaigns = []
            existing_ids = {c.get("id") for c in existing_campaigns if isinstance(c, dict)}
            if str(campaign_id) not in existing_ids:
                existing_campaigns.append(campaign_entry)
                contact.campaigns = json.dumps(existing_campaigns)
    
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
            last_synced_at=datetime.utcnow(),
            campaigns=json.dumps([{
                "name": campaign_name,
                "id": str(campaign_id) if campaign_id else None,
                "source": "smartlead"
            }]) if campaign_name or campaign_id else None
        )
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
            event_time = datetime.fromisoformat(body["event_timestamp"].replace("Z", "+00:00"))
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
    
    # Update contact if replied
    if "replied" in activity_type:
        contact.has_replied = True
        contact.reply_channel = "email"
        contact.last_reply_at = event_time
        contact.status = "replied"
    
    # Update contact's Smartlead status from category
    if lead_data.get("category"):
        category = lead_data["category"]
        contact.smartlead_status = category.get("name")
    
    # Update smartlead_id if not set
    if lead_id and not contact.smartlead_id:
        contact.smartlead_id = str(lead_id)
    
    await session.commit()
    
    return {"status": "processed", "activity_id": activity.id}


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
        contact.last_synced_at = datetime.utcnow()
        if contact_data.get("pipeline_stage"):
            contact.getsales_status = contact_data.get("pipeline_stage")
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
            getsales_status=contact_data.get("pipeline_stage"),
            last_synced_at=datetime.utcnow(),
            status="lead",
        )
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
    
    logger.info(f"GetSales webhook: contact={contact_data.get('name')}, message_type={message_type}, automation={automation_data.get('name')}")
    
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
        contact.getsales_status = contact_data.get("pipeline_stage_name")
        if linkedin_url and not contact.linkedin_url:
            contact.linkedin_url = linkedin_url
    
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
            email=lead_email or f"linkedin_{lead_uuid}@getsales.local",
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            company_name=contact_data.get("company_name") or account_data.get("name"),
            job_title=contact_data.get("position"),
            linkedin_url=linkedin_url,
            location=location_str,
            source="getsales",
            getsales_id=lead_uuid,
            getsales_status=contact_data.get("pipeline_stage_name"),
            status="replied" if is_reply else "contacted",
            has_replied=is_reply,
            last_synced_at=datetime.utcnow(),
            # Add flow/automation info from webhook
            campaigns=json.dumps([{
                "name": automation_data.get("name"),
                "id": automation_data.get("uuid"),
                "source": "getsales",
                "status": "active"
            }]) if automation_data.get("name") or automation_data.get("uuid") else None
        )
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
        from sqlalchemy import select, func
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
        contact.has_replied = True
        contact.reply_channel = "linkedin"
        contact.last_reply_at = activity_at
        contact.getsales_status = contact_data.get("pipeline_stage_name")
        
        # Classify the reply
        from app.services.crm_sync_service import classify_reply, get_status_from_category, get_sentiment_from_category
        category = await classify_reply(message_text)
        
        # Update activity with category
        activity.extra_data["category"] = category
        
        # Update contact status and sentiment
        contact.status = get_status_from_category(category)
        contact.reply_category = category
        contact.reply_sentiment = get_sentiment_from_category(category)
        
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
                import json
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
        
        # Send Telegram notification for LinkedIn reply
        try:
            flow_name = automation_data.get("name") or get_getsales_flow_name(None, contact.campaigns)
            contact_name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip() or "Unknown"
            message_preview = (message_text or "")[:300]
            
            telegram_msg = f"""💬 <b>New LinkedIn Reply!</b>

<b>From:</b> {contact_name}
<b>Email:</b> {contact.email or 'N/A'}
<b>Flow:</b> {flow_name}

<b>Message:</b>
<code>{message_preview}</code>
"""
            await send_telegram_notification(telegram_msg.strip())
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
        existing_campaigns = []
        if contact.campaigns:
            try:
                if isinstance(contact.campaigns, str):
                    existing_campaigns = json.loads(contact.campaigns)
                elif isinstance(contact.campaigns, list):
                    existing_campaigns = contact.campaigns
            except:
                existing_campaigns = []
        
        # Check if this flow is already in campaigns
        existing_flow_ids = {c.get("id") for c in existing_campaigns if isinstance(c, dict)}
        if automation_data.get("uuid") not in existing_flow_ids:
            existing_campaigns.append(flow_entry)
            contact.campaigns = json.dumps(existing_campaigns)
    
    await session.commit()
    
    return {
        "status": "processed",
        "activity_id": activity.id,
        "contact_id": contact.id,
        "is_reply": is_reply
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
        has_replied=contact.has_replied or False,
        last_reply_at=contact.last_reply_at,
        reply_channel=contact.reply_channel,
        smartlead_status=contact.smartlead_status,
        getsales_status=contact.getsales_status,
        last_synced_at=contact.last_synced_at,
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
            Contact.has_replied == True
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
            has_replied=contact.has_replied or False,
            last_reply_at=contact.last_reply_at,
            reply_channel=contact.reply_channel,
            smartlead_status=contact.smartlead_status,
            getsales_status=contact.getsales_status,
            last_synced_at=contact.last_synced_at,
            activities=[ActivityResponse.model_validate(a) for a in activities]
        ))
    
    return responses
