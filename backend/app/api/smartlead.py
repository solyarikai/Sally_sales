"""Smartlead API endpoints for campaign and lead management."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
import logging

from app.db import get_session, async_session_maker
from app.core.config import settings
from app.services.smartlead_service import smartlead_service

logger = logging.getLogger(__name__)

# Event types that represent actual inbound replies
REPLY_EVENT_TYPES = {"EMAIL_REPLY", "lead.replied", "email.replied", "reply"}

# Map Smartlead event types to ContactActivity types
ACTIVITY_TYPE_MAP = {
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

router = APIRouter(prefix="/smartlead", tags=["smartlead"])


# Request/Response models
class CampaignResponse(BaseModel):
    id: str
    name: str
    status: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    campaigns: List[dict]
    total: int


class LeadResponse(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[str] = None
    
    class Config:
        from_attributes = True


class LeadsListResponse(BaseModel):
    leads: List[dict]
    total: int
    offset: int
    limit: int


class WebhookBody(BaseModel):
    """Inner body of Smartlead webhook."""
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    preview_text: Optional[str] = None
    email_text: Optional[str] = None
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    lead_id: Optional[str] = None
    ui_master_inbox_link: Optional[str] = None
    
    class Config:
        extra = "allow"


class WebhookPayload(BaseModel):
    """Smartlead webhook payload for email replies."""
    # Smartlead wraps data in body
    body: Optional[WebhookBody] = None
    # Also support flat format for testing
    event_type: Optional[str] = None
    campaign_id: Optional[str] = None
    lead_email: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    reply_text: Optional[str] = None
    received_at: Optional[str] = None
    
    class Config:
        extra = "allow"


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns():
    """Get all Smartlead campaigns.
    
    Returns list of campaigns from Smartlead API.
    Requires Smartlead API key to be configured in settings.
    """
    if not smartlead_service.is_connected():
        raise HTTPException(
            status_code=400, 
            detail="Smartlead API key not configured. Please set it in Settings."
        )
    
    try:
        campaigns = await smartlead_service.get_campaigns()
        return CampaignListResponse(
            campaigns=campaigns,
            total=len(campaigns)
        )
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get a specific campaign by ID."""
    if not smartlead_service.is_connected():
        raise HTTPException(
            status_code=400, 
            detail="Smartlead API key not configured"
        )
    
    try:
        campaign = await smartlead_service.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/leads", response_model=LeadsListResponse)
async def get_campaign_leads(
    campaign_id: str,
    offset: int = 0,
    limit: int = 100
):
    """Get leads for a specific campaign."""
    if not smartlead_service.is_connected():
        raise HTTPException(
            status_code=400, 
            detail="Smartlead API key not configured"
        )
    
    try:
        result = await smartlead_service.get_campaign_leads(
            campaign_id, 
            offset=offset, 
            limit=limit
        )
        return LeadsListResponse(
            leads=result.get("leads", []),
            total=result.get("total", 0),
            offset=offset,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error fetching campaign leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/statistics")
async def get_campaign_statistics(campaign_id: str):
    """Get statistics for a campaign."""
    if not smartlead_service.is_connected():
        raise HTTPException(
            status_code=400, 
            detail="Smartlead API key not configured"
        )
    
    try:
        stats = await smartlead_service.get_campaign_statistics(campaign_id)
        return stats
    except Exception as e:
        logger.error(f"Error fetching campaign statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/leads/{email}/thread")
async def get_lead_email_thread(campaign_id: str, email: str):
    """Get email thread for a specific lead."""
    if not smartlead_service.is_connected():
        raise HTTPException(
            status_code=400, 
            detail="Smartlead API key not configured"
        )
    
    try:
        thread = await smartlead_service.get_email_thread(campaign_id, email)
        return {"messages": thread, "total": len(thread)}
    except Exception as e:
        logger.error(f"Error fetching email thread: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/webhook")
async def receive_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Receive webhook events from Smartlead.
    
    ALL events are logged to webhook_events table (raw payload) for debugging.
    Only EMAIL_REPLY events create ContactActivity and trigger the reply pipeline.
    Conversation history for non-reply events is loaded on demand.
    """
    from app.core.config import settings as _cfg
    if _cfg.WEBHOOK_SECRET:
        token = request.query_params.get("token")
        if token != _cfg.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook token")

    from app.models.reply import WebhookEventModel
    from app.models.contact import Contact, ContactActivity
    
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"[WEBHOOK] JSON parse error: {e}")
        return {"status": "error", "message": str(e)}
    
    # Determine the REAL event type — never override
    actual_event_type = _extract_event_type(data)
    
    # Extract lead email and campaign info
    lead_email = _extract_lead_email(data)
    campaign_id = _extract_campaign_id(data)
    campaign_name = _extract_campaign_name(data)
    lead_data = data.get("lead_data", {})
    
    logger.info(f"[WEBHOOK] {actual_event_type} for {lead_email} (campaign: {campaign_name or campaign_id})")

    # Drop EMAIL_SENT — outbound sends are not tracked; conversation history loads on demand
    if actual_event_type == "EMAIL_SENT":
        return {"status": "skipped", "reason": "EMAIL_SENT events not tracked"}

    # ===== PHASE 1: Store everything in DB (within request session) =====
    
    # 1a. Store raw webhook event for replay/recovery
    webhook_event = WebhookEventModel(
        event_type=actual_event_type,
        campaign_id=str(campaign_id) if campaign_id else None,
        lead_email=lead_email,
        payload=json.dumps(data, default=str),
        processed=False
    )
    session.add(webhook_event)
    await session.flush()
    event_id = webhook_event.id
    
    # 1b. Find or create contact
    contact = None
    if lead_email:
        result = await session.execute(
            select(Contact).where(
                and_(func.lower(Contact.email) == lead_email.lower(), Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    # Try by smartlead_id
    lead_id = data.get("lead_id") or lead_data.get("id")
    if not contact and lead_id:
        result = await session.execute(
            select(Contact).where(
                and_(Contact.smartlead_id == str(lead_id), Contact.deleted_at.is_(None))
            )
        )
        contact = result.scalar_one_or_none()
    
    if not contact and lead_email:
        contact = Contact(
            company_id=1,
            email=lead_email.lower().strip(),
            first_name=lead_data.get("first_name") or data.get("first_name"),
            last_name=lead_data.get("last_name") or data.get("last_name"),
            company_name=lead_data.get("company_name") or data.get("company_name"),
            source="smartlead",
            smartlead_id=str(lead_id) if lead_id else None,
            status="new",
            platform_state={
                "smartlead": {
                    "last_synced": datetime.utcnow().isoformat(),
                    "campaigns": [{
                        "name": campaign_name,
                        "id": str(campaign_id) if campaign_id else None,
                    }] if campaign_name or campaign_id else [],
                }
            },
        )
        session.add(contact)
        await session.flush()
    
    # 1c. Only create ContactActivity for reply events (conversation history loaded on demand)
    is_reply = actual_event_type in REPLY_EVENT_TYPES
    
    # Parse event timestamp
    event_time = datetime.utcnow()
    for ts_field in ("event_timestamp", "time_replied", "timestamp"):
        ts_val = data.get(ts_field)
        if ts_val:
            try:
                event_time = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
            break
    
    if contact:
        if is_reply:
            reply_text = _extract_reply_text(data)
            subject = _extract_subject(data)
            activity = ContactActivity(
                contact_id=contact.id,
                company_id=contact.company_id,
                activity_type="email_replied",
                channel="email",
                direction="inbound",
                source="smartlead",
                source_id=str(lead_id) if lead_id else None,
                subject=subject,
                body=reply_text,
                snippet=(reply_text or "")[:200] if reply_text else None,
                extra_data={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "webhook_event_id": event_id,
                },
                activity_at=event_time
            )
            session.add(activity)
            contact.last_reply_at = event_time
            contact.mark_replied("email", at=event_time)
            if contact.status in (None, "", "new", "contacted", "lead"):
                contact.status = "replied"
        
        if actual_event_type == "EMAIL_BOUNCED":
            contact.status = "bounced"
        
        if lead_id and not contact.smartlead_id:
            contact.smartlead_id = str(lead_id)
    
    # Session commits on return via get_session() dependency
    # At this point, event is safely stored regardless of what happens next
    
    # Signal webhook health to the scheduler
    from app.services.crm_scheduler import mark_webhook_received
    mark_webhook_received()
    
    # ===== PHASE 2: Process reply pipeline async (own session) =====
    if is_reply and lead_email:
        # Build the payload for the reply processor
        full_payload = _build_reply_payload(data)
        asyncio.create_task(_process_reply_safe(event_id, full_payload))
        logger.info(f"[WEBHOOK] Reply processing queued for event {event_id}")
    else:
        # Non-reply events are fully handled — mark as processed
        webhook_event.processed = True
        webhook_event.processed_at = datetime.utcnow()
        logger.info(f"[WEBHOOK] Non-reply event {actual_event_type} stored (event {event_id})")
    
    return {"status": "received", "event_id": event_id, "event_type": actual_event_type}


async def _process_reply_safe(event_id: int, payload: dict):
    """Process a reply with its own DB session. Failures are recoverable via event recovery loop."""
    from app.services.reply_processor import process_reply_webhook
    from app.models.reply import WebhookEventModel
    
    try:
        async with async_session_maker() as session:
            result = await process_reply_webhook(payload, session)
            
            # Mark event as successfully processed
            event = await session.get(WebhookEventModel, event_id)
            if event:
                event.processed = True
                event.processed_at = datetime.utcnow()
                event.error = None
            await session.commit()
            
            if result:
                logger.info(f"[WEBHOOK] Reply processed for event {event_id}: category={result.category}")
            else:
                logger.warning(f"[WEBHOOK] process_reply_webhook returned None for event {event_id}")
    except Exception as e:
        # Duplicate replies (uq_processed_reply_content) are not errors — mark as processed
        if "uq_processed_reply_content" in str(e):
            logger.info(f"[WEBHOOK] Duplicate reply for event {event_id} — marking as processed")
            try:
                async with async_session_maker() as dup_session:
                    event = await dup_session.get(WebhookEventModel, event_id)
                    if event:
                        event.processed = True
                        event.processed_at = datetime.utcnow()
                    await dup_session.commit()
            except Exception as mark_err:
                logger.error(f"[WEBHOOK] Failed to mark duplicate event {event_id}: {mark_err}")
            return

        logger.error(f"[WEBHOOK] Reply processing failed for event {event_id}: {e}")
        # Mark event with error for recovery loop to pick up
        try:
            async with async_session_maker() as err_session:
                event = await err_session.get(WebhookEventModel, event_id)
                if event:
                    event.error = str(e)[:500]
                    event.retry_count = (event.retry_count or 0) + 1
                await err_session.commit()
        except Exception as mark_err:
            logger.error(f"[WEBHOOK] Failed to mark event {event_id} error: {mark_err}")


# ===== Helper functions for webhook data extraction =====

def _extract_event_type(data: dict) -> str:
    """Extract the real event type from webhook data. Never hardcode."""
    # Try flat format first
    event_type = data.get("event_type")
    if event_type:
        return event_type
    # Try nested body format
    body = data.get("body")
    if isinstance(body, dict):
        event_type = body.get("event_type")
        if event_type:
            return event_type
    # Default to EMAIL_REPLY for backwards compatibility with older webhook formats
    # that don't include event_type but are always reply webhooks
    return "EMAIL_REPLY"


def _extract_lead_email(data: dict) -> Optional[str]:
    """Extract lead email from various webhook formats."""
    email = (
        data.get("sl_lead_email") or
        data.get("to_email") or
        data.get("lead_email") or
        (data.get("body") or {}).get("from_email") or
        (data.get("lead_data") or {}).get("email")
    )
    return email.lower().strip() if email else None


def _extract_campaign_id(data: dict) -> Optional[str]:
    """Extract campaign ID from various webhook formats."""
    cid = data.get("campaign_id") or (data.get("body") or {}).get("campaign_id")
    return str(cid) if cid else None


def _extract_campaign_name(data: dict) -> Optional[str]:
    """Extract campaign name from various webhook formats."""
    return data.get("campaign_name") or (data.get("body") or {}).get("campaign_name")


def _extract_reply_text(data: dict) -> Optional[str]:
    """Extract reply/email text content from webhook data.

    Works for both inbound (EMAIL_REPLY) and outbound (EMAIL_SENT) events.
    """
    text = (
        data.get("reply_body") or
        data.get("email_body") or              # top-level — common in EMAIL_SENT
        data.get("email_text") or              # alternate field
        data.get("preview_text") or
        data.get("description") or
        (data.get("reply_message") or {}).get("text") or
        (data.get("reply_message") or {}).get("html") or
        (data.get("body") or {}).get("preview_text") or
        (data.get("body") or {}).get("email_text") or
        (data.get("body") or {}).get("email_body") or
        (data.get("last_reply") or {}).get("email_body")
    )
    if text:
        return text

    # Fallback: try history entries (Smartlead sometimes sends the body here)
    history = data.get("history") or []
    for entry in reversed(history):  # newest first
        body = entry.get("email_body") or entry.get("email_text")
        if body:
            return body

    return None


def _extract_subject(data: dict) -> Optional[str]:
    """Extract email subject from webhook data."""
    subject = data.get("subject") or data.get("email_subject")
    if not subject:
        for entry in data.get("history", []):
            if entry.get("subject"):
                subject = entry["subject"]
                break
    return subject


def _build_reply_payload(data: dict) -> dict:
    """Build a flat payload dict for process_reply_webhook from raw webhook data."""
    body = data.get("body") or {}
    lead_data = data.get("lead_data") or {}
    
    lead_email = _extract_lead_email(data)
    campaign_id = _extract_campaign_id(data)
    campaign_name = _extract_campaign_name(data)
    reply_text = _extract_reply_text(data)
    subject = _extract_subject(data)
    
    return {
        "event_type": "EMAIL_REPLY",
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "lead_email": lead_email,
        "to_email": lead_email,
        "to_name": data.get("to_name", ""),
        "first_name": lead_data.get("first_name") or data.get("first_name", ""),
        "last_name": lead_data.get("last_name") or data.get("last_name", ""),
        "company_name": lead_data.get("company_name") or data.get("company_name", ""),
        "email_subject": subject,
        "preview_text": reply_text,
        "email_body": reply_text,
        "sl_email_lead_id": str(data.get("lead_id", "")) if data.get("lead_id") else "",
        "sl_email_lead_map_id": str(data.get("sl_email_lead_map_id", "")),
        "custom_fields": lead_data.get("custom_fields") or data.get("custom_fields", {}),
        "website": lead_data.get("website") or data.get("website", ""),
        "linkedin_profile": lead_data.get("linkedin_profile") or data.get("linkedin_profile", ""),
        "location": lead_data.get("location") or data.get("location", ""),
        "time_replied": data.get("time_replied") or data.get("event_timestamp"),
        "history": data.get("history", []),
        "ui_master_inbox_link": body.get("ui_master_inbox_link") or data.get("ui_master_inbox_link"),
        # Preserve all original data for the processor
        **{k: v for k, v in data.items() if k not in ("body", "lead_data")},
    }


class SimulateReplyPayload(BaseModel):
    """Payload for simulating a reply (for testing)."""
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = "Test Campaign"
    lead_email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    email_subject: Optional[str] = "Re: Test Subject"
    email_body: str
    
    class Config:
        extra = "allow"


@router.post("/simulate-reply")
async def simulate_reply(
    payload: SimulateReplyPayload,
    session: AsyncSession = Depends(get_session)
):
    """Simulate an incoming reply for testing purposes.
    
    This endpoint processes a simulated reply synchronously
    and returns the classification and draft reply immediately.
    Use this to test the AI classification and draft generation
    without needing actual Smartlead webhooks.
    
    Example request:
    ```json
    {
        "lead_email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "company_name": "Acme Corp",
        "email_subject": "Re: Your offer",
        "email_body": "I'm interested in learning more about your services."
    }
    ```
    """
    logger.info(f"Simulating reply from: {payload.lead_email}")
    
    # Import here to avoid circular imports
    from app.services.reply_processor import process_reply_webhook
    
    # Build webhook-like payload
    webhook_payload = {
        "event_type": "simulated_reply",
        "campaign_id": payload.campaign_id,
        "campaign_name": payload.campaign_name,
        "lead_email": payload.lead_email,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "company_name": payload.company_name,
        "email_subject": payload.email_subject,
        "email_body": payload.email_body,
        "reply_text": payload.email_body,
    }
    
    try:
        # Process synchronously for immediate feedback
        processed_reply = await process_reply_webhook(
            payload=webhook_payload,
            session=session
        )
        
        if processed_reply:
            return {
                "success": True,
                "reply_id": processed_reply.id,
                "category": processed_reply.category,
                "confidence": processed_reply.category_confidence,
                "reasoning": processed_reply.classification_reasoning,
                "draft_subject": processed_reply.draft_subject,
                "draft_reply": processed_reply.draft_reply,
                "sent_to_slack": processed_reply.sent_to_slack
            }
        else:
            return {
                "success": False,
                "message": "Failed to process reply"
            }
    except Exception as e:
        logger.error(f"Error simulating reply: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/test-campaign")
async def create_test_campaign(
    emails: list[str],
    name: str = None,
    launch: bool = False
):
    """Create a test campaign for automation testing"""
    import httpx
    from datetime import datetime
    
    api_key = settings.SMARTLEAD_API_KEY
    timestamp = datetime.now().strftime("%H%M")
    campaign_name = name or f"Test Campaign {timestamp}"
    
    async with httpx.AsyncClient() as client:
        # 1. Create campaign
        resp = await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/create?api_key={api_key}",
            json={"name": campaign_name}
        )
        data = resp.json()
        campaign_id = data.get("id")
        if not campaign_id:
            raise HTTPException(status_code=400, detail=f"Failed to create campaign: {data}")
        
        # 2. Add sequence
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/sequences?api_key={api_key}",
            json={
                "sequences": [{
                    "seq_number": 1,
                    "seq_delay_details": {"delay_in_days": 0},
                    "subject": f"Test Email - {campaign_name}",
                    "email_body": "<p>Hi {{first_name}},</p><p>This is a test email for automation testing.</p><p>Please reply to test the auto-reply system.</p><p>Best,<br>Test Bot</p>"
                }]
            }
        )
        
        # 3. Set schedule (24/7)
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/schedule?api_key={api_key}",
            json={
                "timezone": "UTC",
                "days_of_the_week": [0,1,2,3,4,5,6],
                "start_hour": "00:01",
                "end_hour": "23:59",
                "min_time_btw_emails": 3,
                "max_new_leads_per_day": 100
            }
        )
        
        # 4. Settings
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/settings?api_key={api_key}",
            json={
                "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
                "stop_lead_settings": "REPLY_TO_AN_EMAIL",
                "send_as_plain_text": False,
                "follow_up_percentage": 100
            }
        )
        
        # 5. Add leads (SmartLead expects {"lead_list": [...]})
        leads_to_add = []
        for email in emails:
            first_name = email.split("@")[0].replace(".", " ").title().split()[0]
            leads_to_add.append({"email": email, "first_name": first_name, "company_name": "Test Company"})

        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads?api_key={api_key}",
            json={"lead_list": leads_to_add}
        )
        
        # 6. Launch if requested
        if launch:
            await client.post(
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status?api_key={api_key}",
                json={"status": "START"}
            )
        
        return {
            "campaign_id": str(campaign_id),
            "campaign_name": campaign_name,
            "emails": emails,
            "launched": launch,
            "smartlead_url": f"https://app.smartlead.ai/app/email-campaign/{campaign_id}/overview"
        }


@router.post("/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: str):
    """Launch a campaign"""
    import httpx

    api_key = settings.SMARTLEAD_API_KEY
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status?api_key={api_key}",
            json={"status": "START"}
        )
        return resp.json()


@router.post("/campaigns/{campaign_id}/add-leads")
async def add_leads_to_campaign(campaign_id: str, emails: list[str]):
    """Add leads to an existing campaign"""
    import httpx

    api_key = settings.SMARTLEAD_API_KEY
    leads_to_add = []
    for email in emails:
        first_name = email.split("@")[0].replace(".", " ").title().split()[0]
        leads_to_add.append({
            "email": email,
            "first_name": first_name,
            "company_name": "Test Company"
        })

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads?api_key={api_key}",
            json={"lead_list": leads_to_add}
        )
        return {
            "campaign_id": campaign_id,
            "leads_added": len(emails),
            "emails": emails,
            "response": resp.json()
        }
