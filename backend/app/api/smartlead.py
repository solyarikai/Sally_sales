"""Smartlead API endpoints for campaign and lead management."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
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


class WebhookPayload(BaseModel):
    """Smartlead webhook payload for email replies."""
    event_type: Optional[str] = None
    campaign_id: Optional[str] = None
    lead_email: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    reply_text: Optional[str] = None
    received_at: Optional[str] = None
    # Allow extra fields from webhook
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
    payload: WebhookPayload,
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
    logger.info(f"Received Smartlead webhook: {payload.event_type}")
    logger.info(f"Payload: campaign={payload.campaign_id}, email={payload.lead_email}")
    
    # Import here to avoid circular imports
    from app.services.reply_processor import process_reply_webhook
    
    # Process in background to return quickly to Smartlead
    background_tasks.add_task(
        process_reply_webhook,
        payload=payload.model_dump(),
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
