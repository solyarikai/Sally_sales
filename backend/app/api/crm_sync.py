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
import hashlib
import hmac

from app.db import get_session
from app.models import Company, Contact, ContactActivity
from app.api.companies import get_required_company
from app.services.crm_sync_service import get_crm_sync_service, CRMSyncService

logger = logging.getLogger(__name__)


def _normalize_linkedin(url: str) -> str:
    """Normalize LinkedIn URL for matching."""
    if not url or url == '--':
        return None
    import re
    normalized = re.sub(r'^https?://(www\.)?', '', url.lower()).rstrip('/')
    return normalized if normalized else None


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
        async with get_session() as bg_session:
            try:
                results = await sync_service.full_sync(bg_session, company.id)
                logger.info(f"Sync completed for company {company.id}: {results}")
            except Exception as e:
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
    
    if not contact:
        logger.warning(f"Contact not found for webhook: {lead_email}")
        return {"status": "ignored", "reason": "contact not found"}
    
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
            first_name=contact_data.get("first_name", ""),
            last_name=contact_data.get("last_name", ""),
            company_name=contact_data.get("account", {}).get("name") if isinstance(contact_data.get("account"), dict) else contact_data.get("company_name", ""),
            job_title=contact_data.get("job_title") or contact_data.get("title"),
            linkedin_url=linkedin_url,
            location=_extract_location(contact_data.get("location")) or contact_data.get("city"),
            phone=contact_data.get("phone") or contact_data.get("phone_number"),
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
    
    if not contact:
        # Contact not in our system yet - create it
        logger.info(f"Creating new contact from GetSales webhook: {lead_email or linkedin_url}")
        
        location = contact_data.get("location", {})
        location_str = ", ".join(filter(None, [
            location.get("city"),
            location.get("region"),
            location.get("country")
        ])) if isinstance(location, dict) else contact_data.get("raw_address")
        
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
            last_synced_at=datetime.utcnow()
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
        snippet=message_text[:200] if message_text else None,
        extra_data={
            "automation_uuid": automation_data.get("uuid"),
            "automation_name": automation_data.get("name"),
            "pipeline_stage": contact_data.get("pipeline_stage_name"),
            "account_name": account_data.get("name"),
            "account_website": account_data.get("website"),
            "linkedin_type": linkedin_message.get("linkedin_type"),
            "messages_sent_count": contact_markers.get("linkedin_messages_sent_count"),
            "messages_inbox_count": contact_markers.get("linkedin_messages_inbox_count"),
            "conversation_thread": body.get("latest_linkedin_conversation_thread", {}).get("messaging_thread"),
        },
        activity_at=activity_at
    )
    session.add(activity)
    
    # Update contact if this is a reply
    if is_reply:
        contact.has_replied = True
        contact.reply_channel = "linkedin"
        contact.last_reply_at = activity_at
        contact.status = "replied"
        contact.getsales_status = contact_data.get("pipeline_stage_name")
    
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
