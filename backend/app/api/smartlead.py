"""Smartlead API endpoints for campaign and lead management."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.db import get_session
from app.services.smartlead_service import smartlead_service

logger = logging.getLogger(__name__)

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



@router.post("/webhook-raw")
async def receive_webhook_raw(request: Request):
    """Debug endpoint to log raw webhook payload."""
    import json
    from datetime import datetime
    
    # Log request details
    logger.info("="*60)
    logger.info(f"[WEBHOOK-RAW] Received at {datetime.now().isoformat()}")
    logger.info(f"[WEBHOOK-RAW] Headers: {dict(request.headers)}")
    logger.info(f"[WEBHOOK-RAW] Client: {request.client}")
    
    # Get raw body
    body = await request.body()
    body_str = body.decode() if body else "<empty>"
    logger.info(f"[WEBHOOK-RAW] Body length: {len(body_str)} chars")
    logger.info(f"[WEBHOOK-RAW] Raw body: {body_str[:2000]}")  # First 2000 chars
    
    # Try to parse as JSON
    try:
        data = await request.json()
        logger.info(f"[WEBHOOK-RAW] Parsed JSON keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        logger.info(f"[WEBHOOK-RAW] Full JSON: " + json.dumps(data, indent=2, default=str)[:3000])
    except Exception as e:
        logger.error(f"[WEBHOOK-RAW] JSON parse error: {e}")
    
    logger.info("="*60)
    return {"status": "logged", "received_at": datetime.now().isoformat()}


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Receive webhook events from Smartlead.
    
    This endpoint receives email reply notifications from Smartlead.
    Configure this URL in Smartlead webhook settings:
    https://your-domain.com/api/smartlead/webhook
    
    The webhook will:
    1. Log the incoming reply
    2. Queue it for AI classification
    3. Generate draft response
    4. Send Slack notification
    """
    import json
    from datetime import datetime
    
    logger.info("="*60)
    logger.info(f"[WEBHOOK] Received at {datetime.now().isoformat()}")
    
    # First get raw body for debugging
    raw_body = await request.body()
    logger.info(f"[WEBHOOK] Raw body: {raw_body.decode()[:2000]}")
    
    # Log event to history for replay capability
    try:
        from app.models.reply import WebhookEventModel
        webhook_event = WebhookEventModel(
            event_type="EMAIL_REPLY",
            campaign_id=str(data.get("campaign_id", "") if isinstance(data, dict) else ""),
            lead_email=data.get("sl_lead_email") or data.get("to_email") if isinstance(data, dict) else None,
            payload=raw_body.decode(),
            processed=False
        )
        session.add(webhook_event)
        await session.flush()
        logger.info(f"[WEBHOOK] Event logged with ID: {webhook_event.id}")
    except Exception as log_err:
        logger.warning(f"[WEBHOOK] Failed to log event: {log_err}")
    
    # Parse JSON manually
    try:
        data = await request.json()
        logger.info(f"[WEBHOOK] Parsed keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    except Exception as e:
        logger.error(f"[WEBHOOK] JSON parse error: {e}")
        return {"status": "error", "message": str(e)}
    
    # Convert to payload model
    try:
        payload = WebhookPayload(**data)
    except Exception as e:
        logger.warning(f"[WEBHOOK] Pydantic validation error: {e}")
        logger.info(f"[WEBHOOK] Proceeding with raw data")
        # Create minimal payload from raw data
        # Smartlead sends different fields depending on webhook version
        payload = WebhookPayload()
        payload.campaign_id = str(data.get("campaign_id") or data.get("body", {}).get("campaign_id") or "")
        
        # Lead email: sl_lead_email or to_email (in flat format, to_email is the lead who receives)
        payload.lead_email = data.get("sl_lead_email") or data.get("to_email") or data.get("body", {}).get("from_email")
        
        # Subject
        payload.email_subject = data.get("subject")
        
        # Reply body: try multiple locations (including description field)
        reply_body = (
            data.get("reply_body") or 
            data.get("preview_text") or
            data.get("description") or  # Smartlead sends reply text in description field
            (data.get("reply_message", {}) or {}).get("text") or
            (data.get("reply_message", {}) or {}).get("html") or
            data.get("body", {}).get("preview_text") or
            data.get("body", {}).get("email_text")
        )
        
        # Log what we found for debugging
        logger.info(f"[WEBHOOK] description={data.get('description', 'N/A')[:200] if data.get('description') else 'None'}")
        payload.email_body = reply_body
        payload.reply_text = reply_body
        
        # Store full conversation history if available
        payload.received_at = data.get("time_replied") or data.get("event_timestamp")
        payload.event_type = "EMAIL_REPLY"
        
        # Log extracted fields
        logger.info(f"[WEBHOOK] Extracted fields: subject={payload.email_subject}, body_len={len(payload.email_body) if payload.email_body else 0}")
    
    logger.info(f"[WEBHOOK] Payload: campaign_id={payload.campaign_id}, lead_email={payload.lead_email}")
    
    # Handle both wrapped (body) and flat formats
    if payload.body:
        # Smartlead sends data wrapped in body
        body = payload.body
        logger.info(f"[WEBHOOK] Format: WRAPPED (body object detected)")
        logger.info(f"[WEBHOOK] body.campaign_id={body.campaign_id}")
        logger.info(f"[WEBHOOK] body.from_email={body.from_email}")
        logger.info(f"[WEBHOOK] body.to_email={body.to_email}")
        logger.info(f"[WEBHOOK] body.preview_text={body.preview_text[:200] if body.preview_text else None}")
        logger.info(f"[WEBHOOK] body.campaign_name={body.campaign_name}")
        
        # Convert to flat format for processor
        payload.campaign_id = str(body.campaign_id) if body.campaign_id else None
        payload.lead_email = body.from_email  # to_email is our lead
        payload.email_body = body.preview_text or body.email_text
        payload.event_type = "EMAIL_REPLY"
        logger.info(f"[WEBHOOK] Converted: campaign_id={payload.campaign_id}, lead_email={payload.lead_email}")
    else:
        logger.info(f"[WEBHOOK] Format: FLAT")
        logger.info(f"[WEBHOOK] event_type={payload.event_type}")
        logger.info(f"[WEBHOOK] campaign_id={payload.campaign_id}")
        logger.info(f"[WEBHOOK] lead_email={payload.lead_email}")
        logger.info(f"[WEBHOOK] email_body={payload.email_body[:200] if payload.email_body else None}")
    
    logger.info("="*60)
    
    # Import here to avoid circular imports
    from app.services.reply_processor import process_reply_webhook
    
    # Process in background to return quickly to Smartlead
    # Merge raw data with payload so processor has access to all Smartlead fields
    # (like sl_email_lead_map_id, to_name, preview_text, etc.)
    full_payload = {**data, **payload.model_dump()}
    
    background_tasks.add_task(
        process_reply_webhook,
        payload=full_payload,
        session=session
    )
    
    return {"status": "received", "message": "Webhook processed"}


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
        
        # 5. Add leads
        for email in emails:
            first_name = email.split("@")[0].replace(".", " ").title().split()[0]
            await client.post(
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads?api_key={api_key}",
                json=[{"email": email, "first_name": first_name, "company": "Test Company"}]
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
