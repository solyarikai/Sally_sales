"""API endpoints for Reply Automation feature."""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.db import get_session
from app.models.reply import ReplyAutomation, ProcessedReply, ReplyPromptTemplateModel, WebhookEventModel
from app.schemas.reply import (
    ReplyAutomationCreate,
    ReplyAutomationUpdate,
    ReplyAutomationResponse,
    ReplyAutomationListResponse,
    ProcessedReplyResponse,
    ProcessedReplyListResponse,
    ProcessedReplyStats,
    AutomationMonitoringStats,
    AutomationMonitoringListResponse,
)
from app.services.notification_service import (
    send_test_notification, 
    send_slack_notification,
    get_slack_token_status,
    list_slack_channels,
    create_slack_channel
)
from app.services.google_sheets_service import google_sheets_service
from app.services.smartlead_service import smartlead_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replies", tags=["replies"])


# ============= Test Endpoints =============


class PromptDebugRequest(BaseModel):
    prompt: str
    conversation_history: str
    prompt_type: str = "classification"  # classification or reply


class ReplyPromptTemplate(BaseModel):
    id: Optional[int] = None
    name: str
    prompt_type: Optional[str] = None  # Optional tag
    prompt_text: str
    is_default: bool = False


@router.post("/test-notification")
async def test_notification():
    """Test the Slack notification with sample data to #c-replies-test channel."""
    from app.services.notification_service import send_test_notification
    
    result = await send_test_notification(channel_id="C09REGUQWTG")
    return {"slack_response": result}


@router.post("/test-full-notification")
async def test_full_notification():
    """Test a full reply notification with sample data including inbox link."""
    # Create a mock reply object for testing
    class MockReply:
        id = 999
        category = "interested"
        lead_email = "test@example.com"
        lead_first_name = "John"
        lead_last_name = "Doe"
        lead_company = "Example Corp"
        email_subject = "Re: Partnership Opportunity"
        email_body = "Hi, I am very interested in learning more about your services. When can we schedule a call?"
        reply_text = None
        draft_reply = "Thank you for your interest! I'd be happy to schedule a call. What times work best for you this week?"
        campaign_id = "test-campaign"
        campaign_name = "Test Campaign"
        category_confidence = "high"
        classification_reasoning = "User explicitly expresses interest and asks for a call"
        # Smartlead inbox link for direct access
        inbox_link = "https://app.smartlead.ai/app/master-inbox/123456"
    
    mock_reply = MockReply()
    
    success = await send_slack_notification(
        channel_id="C09REGUQWTG",
        reply=mock_reply
    )
    
    return {
        "success": success,
        "message": "Full notification sent" if success else "Failed to send notification"
    }


# ============= Reply Automations =============

@router.get("/automations", response_model=ReplyAutomationListResponse)
async def list_automations(
    company_id: Optional[int] = None,
    active_only: bool = True,
    session: AsyncSession = Depends(get_session)
):
    """List all reply automations."""
    query = select(ReplyAutomation).where(ReplyAutomation.is_active == True)
    
    if active_only:
        query = query.where(ReplyAutomation.active == True)
    
    if company_id:
        query = query.where(ReplyAutomation.company_id == company_id)
    
    query = query.order_by(desc(ReplyAutomation.created_at))
    
    result = await session.execute(query)
    automations = result.scalars().all()
    
    return ReplyAutomationListResponse(
        automations=[ReplyAutomationResponse.model_validate(a) for a in automations],
        total=len(automations)
    )


@router.post("/automations", response_model=ReplyAutomationResponse)
async def create_automation(
    data: ReplyAutomationCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new reply automation."""
    
    # Handle Google Sheet creation if requested
    google_sheet_id = data.google_sheet_id
    google_sheet_name = data.google_sheet_name
    
    if data.create_google_sheet and not google_sheet_id:
        if google_sheets_service.is_configured():
            sheet_result = google_sheets_service.create_reply_sheet(
                name=data.name,
                share_with_email=data.share_sheet_with_email
            )
            if sheet_result:
                google_sheet_id = sheet_result['sheet_id']
                google_sheet_name = f"Reply Log - {data.name}"
                logger.info(f"Created Google Sheet {google_sheet_id} for automation {data.name}")
            else:
                logger.warning(f"Failed to create Google Sheet for automation {data.name}")
        else:
            logger.warning("Google Sheets not configured, skipping sheet creation")
    
    automation = ReplyAutomation(
        name=data.name,
        company_id=data.company_id,
        environment_id=data.environment_id,
        campaign_ids=data.campaign_ids,
        slack_webhook_url=data.slack_webhook_url,
        slack_channel=data.slack_channel,
        google_sheet_id=google_sheet_id,
        google_sheet_name=google_sheet_name,
        auto_classify=data.auto_classify,
        auto_generate_reply=data.auto_generate_reply,
        classification_prompt=data.classification_prompt,
        reply_prompt=data.reply_prompt,
        active=data.active
    )
    
    session.add(automation)
    await session.flush()
    await session.refresh(automation)
    
    # Auto-configure Smartlead webhooks for all campaigns
    webhook_url = "http://46.62.210.24:8000/api/smartlead/webhook"
    for campaign_id in data.campaign_ids:
        try:
            await smartlead_service.configure_campaign_webhook(
                campaign_id=campaign_id,
                webhook_url=webhook_url
            )
        except Exception as e:
            logger.warning(f"Failed to configure webhook for campaign {campaign_id}: {e}")
    
    logger.info(f"Created reply automation: {automation.id} - {automation.name}")
    
    # Auto-sync historical replies to Google Sheet (data only, no AI/Slack)
    if automation.google_sheet_id and automation.campaign_ids:
        import httpx
        import os
        import re as regex
        
        api_key = os.environ.get("SMARTLEAD_API_KEY")
        synced = 0
        existing_emails = set()
        
        try:
            # First try local DB
            for campaign_id in automation.campaign_ids:
                local_query = select(ProcessedReply).where(
                    ProcessedReply.campaign_id == campaign_id
                ).order_by(ProcessedReply.received_at.desc()).limit(100)
                local_result = await session.execute(local_query)
                local_replies = local_result.scalars().all()
                
                for reply in local_replies:
                    # Skip test emails
                    if reply.lead_email and ("@example.com" in reply.lead_email.lower() or "@test.com" in reply.lead_email.lower()):
                        continue
                    if reply.lead_email and reply.lead_email.lower() in existing_emails:
                        continue
                    row_data = {
                        "lead_email": reply.lead_email or "",
                        "lead_name": f"{reply.lead_first_name or '' } {reply.lead_last_name or '' }".strip(),
                        "subject": reply.email_subject or "",
                        "reply_text": (reply.email_body or reply.reply_text or "")[:500],
                        "received_at": reply.received_at.isoformat() if reply.received_at else "",
                        "campaign_name": reply.campaign_name or automation.name,
                        "category": reply.category or "",
                        "status": "historical"
                    }
                    google_sheets_service.append_reply(automation.google_sheet_id, row_data)
                    synced += 1
                    if reply.lead_email:
                        existing_emails.add(reply.lead_email.lower())
            
            # If no local data, fetch from Smartlead API with full message history
            if api_key:  # Fetch from Smartlead API with pagination
                async with httpx.AsyncClient(timeout=60.0) as client:
                    for campaign_id in automation.campaign_ids:
                        offset = 0
                        page_size = 500
                        empty_pages = 0
                        
                        while offset < 5000 and empty_pages < 3:
                            try:
                                resp = await client.get(
                                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                                    params={"api_key": api_key, "limit": page_size, "offset": offset}
                                )
                                stats = resp.json()
                                page_entries = stats.get("data", [])
                                
                                if not page_entries:
                                    break
                                
                                page_replies = [e for e in page_entries if e.get("reply_time")]
                                if not page_replies:
                                    empty_pages += 1
                                    offset += page_size
                                    continue
                                empty_pages = 0
                                
                                for entry in page_replies:
                                    lead_email = entry.get("lead_email", "").lower()
                                    if lead_email in existing_emails:
                                        continue
                                    
                                    # Get actual reply content from message history
                                    reply_text = ""
                                    try:
                                        lead_resp = await client.get(
                                            "https://server.smartlead.ai/api/v1/leads",
                                            params={"api_key": api_key, "email": entry.get("lead_email")}
                                        )
                                        lead_data = lead_resp.json()
                                        lead_id = lead_data.get("id")
                                        if lead_id:
                                            hist_resp = await client.get(
                                                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                                                params={"api_key": api_key}
                                            )
                                            hist = hist_resp.json()
                                            for msg in hist.get("history", []):
                                                if msg.get("type") == "REPLY":
                                                    reply_text = msg.get("email_body", "")
                                                    if "<" in reply_text:
                                                        reply_text = regex.sub(r"<[^>]+>", " ", reply_text)
                                                        reply_text = regex.sub(r"\\s+", " ", reply_text).strip()
                                                    break
                                    except Exception:
                                        pass
                                    
                                    row_data = {
                                        "lead_email": entry.get("lead_email", ""),
                                        "lead_name": entry.get("lead_name", ""),
                                        "subject": entry.get("email_subject", ""),
                                        "reply_text": reply_text[:1000] if reply_text else f"[Reply at {entry.get('reply_time', '')}]",
                                        "received_at": entry.get("reply_time", ""),
                                        "campaign_name": automation.name,
                                        "category": "",
                                        "status": "historical_api"
                                    }
                                    google_sheets_service.append_reply(automation.google_sheet_id, row_data)
                                    synced += 1
                                    existing_emails.add(lead_email)
                                
                                offset += page_size
                                
                            except Exception as api_err:
                                logger.warning(f"Failed to fetch stats for campaign {campaign_id}: {api_err}")
                                break

            if synced > 0:
                logger.info(f"Auto-synced {synced} historical replies to Google Sheet")
        except Exception as e:
            logger.warning(f"Failed to auto-sync historical replies: {e}")
    
    return ReplyAutomationResponse.model_validate(automation)


# IMPORTANT: This route must be before /automations/{automation_id} to avoid route conflicts
@router.get("/automations/monitoring", response_model=AutomationMonitoringListResponse)
async def get_automation_monitoring_list(
    session: AsyncSession = Depends(get_session)
):
    """Get detailed monitoring stats for all automations."""
    # Get all active (not soft-deleted) automations
    result = await session.execute(
        select(ReplyAutomation).where(ReplyAutomation.is_active == True).order_by(desc(ReplyAutomation.created_at))
    )
    automations = result.scalars().all()
    
    monitoring_stats = []
    total_active = 0
    total_paused = 0
    total_processed_all = 0
    total_errors_all = 0
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    
    for auto in automations:
        # Today count
        today_result = await session.execute(
            select(func.count(ProcessedReply.id)).where(
                ProcessedReply.automation_id == auto.id,
                ProcessedReply.processed_at >= today_start
            )
        )
        replies_today = today_result.scalar() or 0
        
        # Week count
        week_result = await session.execute(
            select(func.count(ProcessedReply.id)).where(
                ProcessedReply.automation_id == auto.id,
                ProcessedReply.processed_at >= week_start
            )
        )
        replies_this_week = week_result.scalar() or 0
        
        # Status breakdown
        status_result = await session.execute(
            select(ProcessedReply.approval_status, func.count(ProcessedReply.id)).where(
                ProcessedReply.automation_id == auto.id
            ).group_by(ProcessedReply.approval_status)
        )
        pending = 0
        approved = 0
        dismissed = 0
        for row in status_result.all():
            status = row[0] or "pending"
            count = row[1]
            if status in ("pending", None):
                pending += count
            elif status == "approved":
                approved = count
            elif status == "dismissed":
                dismissed = count
        
        # Category breakdown
        cat_result = await session.execute(
            select(ProcessedReply.category, func.count(ProcessedReply.id)).where(
                ProcessedReply.automation_id == auto.id
            ).group_by(ProcessedReply.category)
        )
        by_category = {row[0] or "unknown": row[1] for row in cat_result.all()}
        
        # Determine health status
        health_status = "healthy"
        if auto.total_errors and auto.total_errors > 0:
            error_rate = auto.total_errors / max(auto.total_processed or 1, 1)
            if error_rate > 0.5:
                health_status = "error"
            elif error_rate > 0.1:
                health_status = "warning"
        
        if not auto.active:
            health_status = "paused"
        
        monitoring_stats.append(AutomationMonitoringStats(
            automation_id=auto.id,
            automation_name=auto.name,
            active=auto.active,
            total_processed=auto.total_processed or 0,
            total_errors=auto.total_errors or 0,
            replies_today=replies_today,
            replies_this_week=replies_this_week,
            pending=pending,
            approved=approved,
            dismissed=dismissed,
            by_category=by_category,
            last_run_at=auto.last_run_at,
            last_error_at=auto.last_error_at,
            last_error=auto.last_error,
            created_at=auto.created_at,
            health_status=health_status
        ))
        
        # Aggregate totals
        if auto.active:
            total_active += 1
        else:
            total_paused += 1
        total_processed_all += auto.total_processed or 0
        total_errors_all += auto.total_errors or 0
    
    return AutomationMonitoringListResponse(
        automations=monitoring_stats,
        total=len(monitoring_stats),
        total_active=total_active,
        total_paused=total_paused,
        total_processed_all=total_processed_all,
        total_errors_all=total_errors_all
    )


@router.get("/automations/{automation_id}", response_model=ReplyAutomationResponse)
async def get_automation(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific reply automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    return ReplyAutomationResponse.model_validate(automation)


@router.patch("/automations/{automation_id}", response_model=ReplyAutomationResponse)
async def update_automation(
    automation_id: int,
    data: ReplyAutomationUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a reply automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(automation, field, value)
    
    automation.updated_at = datetime.utcnow()
    await session.flush()
    await session.refresh(automation)
    
    logger.info(f"Updated reply automation: {automation.id}")
    return ReplyAutomationResponse.model_validate(automation)


@router.delete("/automations/{automation_id}")
async def delete_automation(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete (soft) a reply automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    automation.soft_delete()
    await session.flush()
    
    logger.info(f"Deleted reply automation: {automation.id}")
    return {"message": "Automation deleted", "id": automation_id}




@router.post("/automations/{automation_id}/campaigns")
async def add_campaigns_to_automation(
    automation_id: int,
    campaign_ids: List[str],
    session: AsyncSession = Depends(get_session)
):
    """Add campaigns to an existing automation.
    
    This appends to the existing campaign list without replacing.
    """
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    # Get existing campaigns and add new ones (dedup)
    existing = automation.campaign_ids or []
    updated = list(set(existing + campaign_ids))
    automation.campaign_ids = updated
    automation.updated_at = datetime.utcnow()
    
    await session.flush()
    await session.refresh(automation)
    
    # Configure webhooks for new campaigns
    from app.services.smartlead_service import smartlead_service
    webhook_url = "http://46.62.210.24:8000/api/smartlead/webhook"
    
    for cid in campaign_ids:
        if cid not in existing:  # Only configure new ones
            try:
                await smartlead_service.configure_campaign_webhook(
                    campaign_id=cid,
                    webhook_url=webhook_url,
                    event_types=["EMAIL_REPLY"]
                )
                logger.info(f"Configured webhook for campaign {cid}")
            except Exception as e:
                logger.warning(f"Failed to configure webhook for campaign {cid}: {e}")
    
    logger.info(f"Added {len(campaign_ids)} campaigns to automation {automation_id}")
    return {"automation_id": automation_id, "campaign_ids": updated, "added": campaign_ids}


@router.delete("/automations/{automation_id}/campaigns/{campaign_id}")
async def remove_campaign_from_automation(
    automation_id: int,
    campaign_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Remove a campaign from an automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    existing = automation.campaign_ids or []
    if campaign_id in existing:
        existing.remove(campaign_id)
        automation.campaign_ids = existing
        automation.updated_at = datetime.utcnow()
        await session.flush()
    
    return {"automation_id": automation_id, "campaign_ids": existing, "removed": campaign_id}

@router.post("/automations/{automation_id}/test-webhook")
async def test_automation_webhook(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Test the Slack webhook for an automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    if not automation.slack_webhook_url:
        raise HTTPException(status_code=400, detail="No Slack webhook URL configured")
    
    result = await send_test_notification(automation.slack_webhook_url)
    return result


# ============= Processed Replies =============

@router.get("/", response_model=ProcessedReplyListResponse)
async def list_replies(
    automation_id: Optional[int] = None,
    campaign_id: Optional[str] = None,
    category: Optional[str] = None,
    approval_status: Optional[str] = Query(None, description="Filter by status: pending, approved, dismissed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    """List processed replies with filters.
    
    Dashboard can filter by approval_status to show pending/approved/dismissed replies.
    """
    query = select(ProcessedReply)
    count_query = select(func.count(ProcessedReply.id))
    
    # Apply filters
    if automation_id:
        query = query.where(ProcessedReply.automation_id == automation_id)
        count_query = count_query.where(ProcessedReply.automation_id == automation_id)
    
    if campaign_id:
        query = query.where(ProcessedReply.campaign_id == campaign_id)
        count_query = count_query.where(ProcessedReply.campaign_id == campaign_id)
    
    if category:
        query = query.where(ProcessedReply.category == category)
        count_query = count_query.where(ProcessedReply.category == category)
    
    # Filter by approval status (pending, approved, dismissed)
    if approval_status:
        if approval_status == "pending":
            # Pending = null or explicitly set to pending
            query = query.where(
                (ProcessedReply.approval_status == None) | 
                (ProcessedReply.approval_status == "pending")
            )
            count_query = count_query.where(
                (ProcessedReply.approval_status == None) | 
                (ProcessedReply.approval_status == "pending")
            )
        else:
            query = query.where(ProcessedReply.approval_status == approval_status)
            count_query = count_query.where(ProcessedReply.approval_status == approval_status)
    
    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(desc(ProcessedReply.processed_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(query)
    replies = result.scalars().all()
    
    return ProcessedReplyListResponse(
        replies=[ProcessedReplyResponse.model_validate(r) for r in replies],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/stats", response_model=ProcessedReplyStats)
async def get_reply_stats(
    automation_id: Optional[int] = None,
    campaign_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Get statistics for processed replies."""
    base_query = select(ProcessedReply)
    
    if automation_id:
        base_query = base_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        base_query = base_query.where(ProcessedReply.campaign_id == campaign_id)
    
    # Total count
    total_result = await session.execute(
        select(func.count(ProcessedReply.id)).select_from(base_query.subquery())
    )
    total = total_result.scalar() or 0
    
    # Count by category
    category_query = select(
        ProcessedReply.category,
        func.count(ProcessedReply.id)
    ).group_by(ProcessedReply.category)
    
    if automation_id:
        category_query = category_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        category_query = category_query.where(ProcessedReply.campaign_id == campaign_id)
    
    category_result = await session.execute(category_query)
    by_category = {row[0] or "unknown": row[1] for row in category_result.all()}
    
    # Today count
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_query = select(func.count(ProcessedReply.id)).where(
        ProcessedReply.processed_at >= today_start
    )
    if automation_id:
        today_query = today_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        today_query = today_query.where(ProcessedReply.campaign_id == campaign_id)
    
    today_result = await session.execute(today_query)
    today = today_result.scalar() or 0
    
    # This week count
    week_start = today_start - timedelta(days=today_start.weekday())
    week_query = select(func.count(ProcessedReply.id)).where(
        ProcessedReply.processed_at >= week_start
    )
    if automation_id:
        week_query = week_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        week_query = week_query.where(ProcessedReply.campaign_id == campaign_id)
    
    week_result = await session.execute(week_query)
    this_week = week_result.scalar() or 0
    
    # Sent to Slack count
    slack_query = select(func.count(ProcessedReply.id)).where(
        ProcessedReply.sent_to_slack == True
    )
    if automation_id:
        slack_query = slack_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        slack_query = slack_query.where(ProcessedReply.campaign_id == campaign_id)
    
    slack_result = await session.execute(slack_query)
    sent_to_slack = slack_result.scalar() or 0
    
    # Count by approval status (for dashboard)
    status_query = select(
        ProcessedReply.approval_status,
        func.count(ProcessedReply.id)
    ).group_by(ProcessedReply.approval_status)
    
    if automation_id:
        status_query = status_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        status_query = status_query.where(ProcessedReply.campaign_id == campaign_id)
    
    status_result = await session.execute(status_query)
    by_status = {}
    pending_count = 0
    approved_count = 0
    dismissed_count = 0
    
    for row in status_result.all():
        status_key = row[0] or "pending"  # null = pending
        count = row[1]
        by_status[status_key] = count
        
        if status_key in ("pending", None):
            pending_count += count
        elif status_key == "approved":
            approved_count = count
        elif status_key == "dismissed":
            dismissed_count = count
    
    # Count by automation (with names)
    automation_query = select(
        ProcessedReply.automation_id,
        ReplyAutomation.name,
        func.count(ProcessedReply.id)
    ).outerjoin(
        ReplyAutomation, ProcessedReply.automation_id == ReplyAutomation.id
    ).group_by(ProcessedReply.automation_id, ReplyAutomation.name)
    
    if campaign_id:
        automation_query = automation_query.where(ProcessedReply.campaign_id == campaign_id)
    
    automation_result = await session.execute(automation_query)
    by_automation = {}
    for row in automation_result.all():
        auto_id = row[0]
        auto_name = row[1] or "Unknown"
        count = row[2]
        if auto_id is not None:
            by_automation[str(auto_id)] = {"id": auto_id, "name": auto_name, "count": count}
    
    return ProcessedReplyStats(
        total=total,
        by_category=by_category,
        by_automation=by_automation,
        by_status=by_status,
        today=today,
        this_week=this_week,
        sent_to_slack=sent_to_slack,
        pending=pending_count,
        approved=approved_count,
        dismissed=dismissed_count
    )


# ===== PROMPT TESTING ROUTES =====
# These MUST be before /{reply_id} to avoid route conflicts

@router.post("/test-prompt")
async def test_prompt_endpoint(
    subject: str = "",
    body: str = "",
    classification_prompt: Optional[str] = None,
    reply_prompt: Optional[str] = None,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    show_prompts: bool = True
):
    """Test classification and reply prompts with sample data.
    
    Args:
        subject: Email subject to test
        body: Email body to test
        classification_prompt: Custom classification prompt (optional)
        reply_prompt: Custom reply prompt (optional)
        first_name: Lead first name for reply generation
        last_name: Lead last name for reply generation
        company: Lead company for reply generation
        show_prompts: Include the actual rendered prompts in response (for debugging)
    
    Returns:
        Classification result, generated reply, and optionally the actual prompts used
    """
    from app.services.reply_processor import (
        classify_reply, generate_draft_reply,
        CLASSIFICATION_PROMPT, DRAFT_REPLY_PROMPT,
        render_classification_prompt, render_draft_prompt
    )
    
    # Get the actual rendered prompts for debugging
    rendered_classification_prompt = render_classification_prompt(
        subject=subject,
        body=body,
        custom_prompt=classification_prompt
    )
    
    # Run classification
    classification = await classify_reply(
        subject=subject,
        body=body,
        custom_prompt=classification_prompt
    )
    
    # Get the actual rendered draft prompt
    rendered_draft_prompt = render_draft_prompt(
        subject=subject,
        body=body,
        category=classification["category"],
        first_name=first_name,
        last_name=last_name,
        company=company,
        custom_prompt=reply_prompt
    )
    
    # Generate reply
    draft = await generate_draft_reply(
        subject=subject,
        body=body,
        category=classification["category"],
        first_name=first_name,
        last_name=last_name,
        company=company,
        custom_prompt=reply_prompt
    )
    
    result = {
        "classification": classification,
        "draft_reply": draft,
        "input": {
            "subject": subject,
            "body": body,
            "first_name": first_name,
            "last_name": last_name,
            "company": company
        }
    }
    
    # Include prompts for debugging if requested
    if show_prompts:
        result["debug"] = {
            "classification_prompt": {
                "template_used": "custom" if classification_prompt else "default",
                "rendered": rendered_classification_prompt
            },
            "draft_prompt": {
                "template_used": "custom" if reply_prompt else "default",
                "rendered": rendered_draft_prompt
            },
            "default_templates": {
                "classification": CLASSIFICATION_PROMPT,
                "draft_reply": DRAFT_REPLY_PROMPT
            }
        }
    
    return result


@router.get("/test/sample-replies")
async def get_replies_for_testing_endpoint(
    search: str = "",
    limit: int = 20,
    session: AsyncSession = Depends(get_session)
):
    """Get recent replies for prompt testing.
    
    Args:
        search: Search term for filtering
        limit: Max number of results
    
    Returns:
        List of replies with subject, body, and lead info
    """
    from sqlalchemy import or_
    
    stmt = select(ProcessedReply).order_by(ProcessedReply.created_at.desc())
    
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                ProcessedReply.email_subject.ilike(search_term),
                ProcessedReply.email_body.ilike(search_term),
                ProcessedReply.lead_email.ilike(search_term),
                ProcessedReply.lead_first_name.ilike(search_term)
            )
        )
    
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    replies = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "subject": r.email_subject,
            "body": r.email_body,
            "first_name": r.lead_first_name,
            "last_name": r.lead_last_name,
            "company": r.lead_company,
            "email": r.lead_email,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in replies
    ]


# ===== END PROMPT TESTING ROUTES =====


@router.get("/prompt-templates")
async def get_reply_prompt_templates(
    prompt_type: str = Query(None, description="Filter by type: classification or reply"),
    db: AsyncSession = Depends(get_session)
):
    """Get all reply prompt templates."""
    from sqlalchemy import select
    
    query = select(ReplyPromptTemplateModel)
    if prompt_type:
        query = query.where(ReplyPromptTemplateModel.prompt_type == prompt_type)
    query = query.order_by(ReplyPromptTemplateModel.is_default.desc(), ReplyPromptTemplateModel.name)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "prompt_type": t.prompt_type,
                "prompt_text": t.prompt_text,
                "is_default": t.is_default
            }
            for t in templates
        ]
    }


@router.post("/prompt-templates")
async def create_reply_prompt_template(
    template: ReplyPromptTemplate,
    db: AsyncSession = Depends(get_session)
):
    """Create a new reply prompt template."""
    new_template = ReplyPromptTemplateModel(
        name=template.name,
        prompt_type=template.prompt_type,
        prompt_text=template.prompt_text,
        is_default=template.is_default
    )
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)
    
    return {
        "id": new_template.id,
        "name": new_template.name,
        "prompt_type": new_template.prompt_type,
        "prompt_text": new_template.prompt_text,
        "is_default": new_template.is_default
    }


@router.put("/prompt-templates/{template_id}")
async def update_reply_prompt_template(
    template_id: int,
    template: ReplyPromptTemplate,
    db: AsyncSession = Depends(get_session)
):
    """Update a reply prompt template."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(ReplyPromptTemplateModel).where(ReplyPromptTemplateModel.id == template_id)
    )
    existing = result.scalar_one_or_none()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    
    existing.name = template.name
    existing.prompt_type = template.prompt_type
    existing.prompt_text = template.prompt_text
    existing.is_default = template.is_default
    
    await db.commit()
    
    return {"success": True, "id": template_id}


@router.delete("/prompt-templates/{template_id}")
async def delete_reply_prompt_template(
    template_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Delete a reply prompt template."""
    from sqlalchemy import select, delete
    
    await db.execute(
        delete(ReplyPromptTemplateModel).where(ReplyPromptTemplateModel.id == template_id)
    )
    await db.commit()
    
    return {"success": True}




# ============ Webhook History & Replay ============

@router.get("/webhook-history")
async def get_webhook_history(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    processed: bool = Query(None),
    campaign_id: str = Query(None),
    db: AsyncSession = Depends(get_session)
):
    """Get webhook event history for debugging and replay."""
    from app.models.reply import WebhookEventModel
    
    query = select(WebhookEventModel).order_by(WebhookEventModel.created_at.desc())
    
    if processed is not None:
        query = query.where(WebhookEventModel.processed == processed)
    if campaign_id:
        query = query.where(WebhookEventModel.campaign_id == campaign_id)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "campaign_id": e.campaign_id,
                "lead_email": e.lead_email,
                "processed": e.processed,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "error": e.error,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "payload_preview": e.payload[:200] + "..." if len(e.payload) > 200 else e.payload
            }
            for e in events
        ],
        "total": len(events),
        "limit": limit,
        "offset": offset
    }


@router.post("/webhook-history/{event_id}/replay")
async def replay_webhook_event(
    event_id: int,
    db: AsyncSession = Depends(get_session)
):
    """Replay a webhook event to reprocess it."""
    import json
    from app.models.reply import WebhookEventModel
    from app.services.reply_processor import process_reply_webhook
    
    result = await db.execute(
        select(WebhookEventModel).where(WebhookEventModel.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    try:
        payload = json.loads(event.payload)
        
        # Process the webhook
        process_result = await process_reply_webhook(payload, db)
        
        # Mark as reprocessed
        event.processed = True
        event.processed_at = datetime.utcnow()
        event.error = None
        await db.commit()
        
        return {
            "success": True,
            "message": "Event replayed successfully",
            "result": process_result
        }
    except Exception as e:
        event.error = str(e)
        await db.commit()
        return {
            "success": False,
            "message": f"Replay failed: {str(e)}"
        }


@router.delete("/webhook-history/clear")
async def clear_webhook_history(
    older_than_days: int = Query(30, description="Clear events older than N days"),
    db: AsyncSession = Depends(get_session)
):
    """Clear old webhook history."""
    from app.models.reply import WebhookEventModel
    from sqlalchemy import delete
    
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    
    result = await db.execute(
        delete(WebhookEventModel).where(WebhookEventModel.created_at < cutoff)
    )
    await db.commit()
    
    return {"deleted": result.rowcount, "older_than_days": older_than_days}


@router.get("/{reply_id}", response_model=ProcessedReplyResponse)
async def get_reply(
    reply_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific processed reply."""
    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    return ProcessedReplyResponse.model_validate(reply)




@router.patch("/{reply_id}/status")
async def update_reply_status(
    reply_id: int,
    approval_status: str = Query(..., description="New status: pending, approved, dismissed"),
    db: AsyncSession = Depends(get_session)
):
    """Update the approval status of a reply and sync to Google Sheets."""
    from app.services.google_sheets_service import google_sheets_service
    
    # Get the reply
    result = await db.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    # Validate status
    valid_statuses = ["pending", "approved", "dismissed"]
    if approval_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Update the reply
    reply.approval_status = approval_status
    db.add(reply)
    await db.commit()
    await db.refresh(reply)
    
    # Sync to Google Sheets if configured
    sheet_updated = False
    if reply.automation_id and reply.google_sheet_row:
        # Get automation to find sheet ID
        auto_result = await db.execute(
            select(ReplyAutomation).where(ReplyAutomation.id == reply.automation_id)
        )
        automation = auto_result.scalar_one_or_none()
        
        if automation and automation.google_sheet_id:
            approved_at_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            sheet_updated = google_sheets_service.update_reply_status(
                automation.google_sheet_id,
                reply.google_sheet_row,
                approval_status,
                approved_by='',  # Can be set from auth later
                approved_at=approved_at_str
            )
    
    return {
        "success": True,
        "reply_id": reply_id,
        "approval_status": approval_status,
        "sheet_updated": sheet_updated
    }

@router.post("/{reply_id}/resend-notification")
async def resend_notification(
    reply_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Resend Slack notification for a reply."""
    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    # Get automation for channel/webhook config
    channel_id = "C09REGUQWTG"  # Default test channel
    webhook_url = None
    
    if reply.automation_id:
        auto_result = await session.execute(
            select(ReplyAutomation).where(ReplyAutomation.id == reply.automation_id)
        )
        automation = auto_result.scalar_one_or_none()
        
        if automation:
            channel_id = automation.slack_channel or channel_id
            webhook_url = automation.slack_webhook_url
    
    success = await send_slack_notification(
        channel_id=channel_id,
        reply=reply,
        webhook_url=webhook_url
    )
    
    if success:
        reply.sent_to_slack = True
        reply.slack_sent_at = datetime.utcnow()
        await session.flush()
        return {"success": True, "message": "Notification sent"}
    else:
        return {"success": False, "message": "Failed to send notification"}


# ============= Google Sheets =============

@router.get("/google-sheets/status")
async def get_google_sheets_status():
    """Check if Google Sheets integration is configured and available."""
    is_configured = google_sheets_service.is_configured()
    service_account_email = google_sheets_service.get_service_account_email() if is_configured else None
    
    return {
        "configured": is_configured,
        "service_account_email": service_account_email,
        "message": "Google Sheets is ready" if is_configured else "Google Sheets not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS."
    }


@router.post("/google-sheets/create")
async def create_google_sheet(
    name: str = Query(..., description="Name for the new spreadsheet"),
    share_with_email: Optional[str] = Query(None, description="Email to share the sheet with"),
    automation_id: Optional[int] = Query(None, description="Automation ID to link the sheet to"),
    session: AsyncSession = Depends(get_session)
):
    """Create a NEW Google Sheet for logging replies.
    
    SAFETY: Only creates new sheets, never modifies existing ones.
    """
    if not google_sheets_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google Sheets integration not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS."
        )
    
    result = google_sheets_service.create_reply_sheet(name, share_with_email)
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create Google Sheet")
    
    # If automation_id provided, update the automation with the sheet ID
    if automation_id:
        auto_result = await session.execute(
            select(ReplyAutomation).where(
                ReplyAutomation.id == automation_id,
                ReplyAutomation.is_active == True
            )
        )
        automation = auto_result.scalar_one_or_none()
        
        if automation:
            automation.google_sheet_id = result['sheet_id']
            automation.google_sheet_name = f"Reply Log - {name}"
            automation.updated_at = datetime.utcnow()
            await session.flush()
            logger.info(f"Linked Google Sheet {result['sheet_id']} to automation {automation_id}")
    
    return {
        "success": True,
        "sheet_id": result['sheet_id'],
        "sheet_url": result['sheet_url'],
        "message": f"Created new sheet: Reply Log - {name}"
    }


@router.get("/google-sheets/{sheet_id}/info")
async def get_sheet_info(sheet_id: str):
    """Get information about a Google Sheet."""
    if not google_sheets_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google Sheets integration not configured"
        )
    
    info = google_sheets_service.get_sheet_info(sheet_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="Sheet not found or not accessible")
    
    return {
        "sheet_id": sheet_id,
        "title": info['title'],
        "url": info['url']
    }


@router.post("/google-sheets/{sheet_id}/log-reply/{reply_id}")
async def log_reply_to_sheet(
    sheet_id: str,
    reply_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Log a specific reply to a Google Sheet.
    
    SAFETY: Append-only operation.
    """
    if not google_sheets_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google Sheets integration not configured"
        )
    
    # Get the reply
    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    # Convert reply to dict for logging
    reply_data = {
        'lead_email': reply.lead_email,
        'lead_first_name': reply.lead_first_name,
        'lead_last_name': reply.lead_last_name,
        'lead_company': reply.lead_company,
        'campaign_id': reply.campaign_id,
        'campaign_name': reply.campaign_name,
        'category': reply.category,
        'category_confidence': reply.category_confidence,
        'email_subject': reply.email_subject,
        'email_body': reply.email_body,
        'reply_text': reply.reply_text,
        'draft_subject': reply.draft_subject,
        'draft_reply': reply.draft_reply,
        'classification_reasoning': reply.classification_reasoning,
        'approval_status': reply.approval_status,
        'inbox_link': reply.inbox_link,
    }
    
    success = google_sheets_service.append_reply(sheet_id, reply_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to log reply to sheet")
    
    return {"success": True, "message": f"Reply {reply_id} logged to sheet"}


# ============= Slack Integration =============



# ============= Test Flow Endpoints =============

@router.post("/test-flow/create-campaign")
async def create_test_campaign(
    name: str = Query("Test Campaign", description="Name for test campaign"),
    db: AsyncSession = Depends(get_session)
):
    """Create a test campaign for testing the auto-reply flow."""
    import uuid
    
    # Generate a unique test campaign ID
    test_id = f"test-{uuid.uuid4().hex[:8]}"
    
    return {
        "success": True,
        "campaign": {
            "id": test_id,
            "name": f"{name} ({test_id})",
            "is_test": True
        },
        "message": "Test campaign created. Now create an automation for this campaign."
    }


@router.post("/test-flow/simulate-reply")
async def simulate_test_reply(
    campaign_id: str = Query(..., description="Campaign ID to simulate reply for"),
    message: str = Query("Hi, I'm interested in learning more about your product. Can we schedule a demo?", description="Test reply message"),
    lead_email: str = Query("test.lead@example.com", description="Test lead email"),
    lead_name: str = Query("Test Lead", description="Test lead name"),
    company: str = Query("Test Company Inc", description="Test company name"),
    db: AsyncSession = Depends(get_session)
):
    """Simulate a reply to test the full automation flow.
    
    This will:
    1. Create a webhook-like payload
    2. Process it through the reply processor
    3. Return the results (classification, draft, notifications sent)
    """
    from app.services.reply_processor import process_reply_webhook
    from datetime import datetime
    
    # Create test payload matching Smartlead format
    test_payload = {
        "event_type": "EMAIL_REPLY",
        "campaign_id": campaign_id,
        "sl_lead_email": lead_email,
        "first_name": lead_name.split()[0] if lead_name else "Test",
        "last_name": lead_name.split()[-1] if len(lead_name.split()) > 1 else "Lead",
        "company_name": company,
        "subject": "Re: Your recent outreach",
        "reply_body": message,
        "time_replied": datetime.utcnow().isoformat()
    }
    
    try:
        # Process through the reply processor
        result = await process_reply_webhook(test_payload, db)
        
        return {
            "success": True,
            "message": "Test reply processed successfully!",
            "result": {
                "reply_id": result.id if result else None,
                "category": result.category if result else None,
                "slack_sent": result.sent_to_slack if result else False,
                "sheet_row": result.google_sheet_row if hasattr(result, "google_sheet_row") else None
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "result": None
        }




@router.get("/test-flow/email-accounts")
async def get_available_email_accounts():
    """Get Smartlead email accounts with available sending capacity."""
    import httpx
    import os
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead API key not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"https://server.smartlead.ai/api/v1/email-accounts",
            params={"api_key": api_key, "limit": 50}
        )
        accounts = response.json()
    
    if not isinstance(accounts, list):
        return {"accounts": [], "error": str(accounts)}
    
    # Filter accounts with available capacity
    available = []
    for acc in accounts:
        daily_limit = acc.get("message_per_day") or 50
        sent_today = acc.get("daily_sent_count") or 0
        remaining = daily_limit - sent_today
        
        if remaining > 0:
            available.append({
                "id": acc.get("id"),
                "email": acc.get("from_email"),
                "name": acc.get("from_name"),
                "daily_limit": daily_limit,
                "sent_today": sent_today,
                "remaining": remaining
            })
    
    available.sort(key=lambda x: x["remaining"], reverse=True)
    return {"accounts": available[:15], "total": len(available)}


@router.post("/test-flow/create-real-campaign")
async def create_real_test_campaign(
    user_email: str = Query(..., description="Your email to receive the test"),
    user_name: str = Query("Test User", description="Your name"),
    email_account_id: int = Query(None, description="Email account ID to send from"),
    db: AsyncSession = Depends(get_session)
):
    """Create a real test campaign in Smartlead and send email to user."""
    import httpx
    import os
    import uuid
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")
    
    test_id = uuid.uuid4().hex[:8]
    campaign_name = f"Auto-Reply Test {test_id}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 0. Auto-select email account if not provided
        if not email_account_id:
            acct_resp = await client.get(
                "https://server.smartlead.ai/api/v1/email-accounts",
                params={"api_key": api_key}
            )
            accounts = acct_resp.json()
            if isinstance(accounts, list) and len(accounts) > 0:
                # Pick account with most remaining capacity
                for acc in accounts:
                    limit = acc.get("message_per_day") or 50
                    sent = acc.get("daily_sent_count") or 0
                    if limit - sent > 0:
                        email_account_id = acc.get("id")
                        break
        
        if not email_account_id:
            return {"success": False, "error": "No email accounts with available capacity"}
        
        # 1. Create campaign
        resp = await client.post(
            "https://server.smartlead.ai/api/v1/campaigns/create",
            params={"api_key": api_key},
            json={"name": campaign_name}
        )
        campaign_data = resp.json()
        
        if "id" not in campaign_data:
            return {"success": False, "error": f"Failed to create campaign: {campaign_data}"}
        
        campaign_id = campaign_data["id"]
        
        # 2. Add email sequence
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/sequences",
            params={"api_key": api_key},
            json={"sequences": [{
                "seq_number": 1,
                "seq_delay_details": {"delay_in_days": 0},
                "subject": "Quick test for auto-reply system",
                "email_body": """Hi {{first_name}},

This is a test email to verify the auto-reply system is working.

Please reply to this email with any message to test the automation!

Example replies to try:
- "Yes, I'm interested!" (should classify as interested)
- "Not interested, thanks" (should classify as not interested)  
- "Can we schedule a call?" (should classify as meeting request)

Best,
{{sender_name}}"""
            }]}
        )
        
        # 3. Add sender account (required for launch)
        await client.post(
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts",
                params={"api_key": api_key},
                json={"email_account_ids": [email_account_id]}
            )
        
        # 4. Configure schedule for sending (days 0=Sun to 6=Sat)
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/schedule",
            params={"api_key": api_key},
            json={
                "timezone": "UTC",
                "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
                "start_hour": "00:00",
                "end_hour": "23:59",
                "min_time_btw_emails": 3,
                "max_new_leads_per_day": 100
            }
        )
        
        # 5. Add user as lead
        parts = user_name.split() if user_name else ["Test", "User"]
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
            params={"api_key": api_key},
            json={"lead_list": [{
                "email": user_email,
                "first_name": parts[0],
                "last_name": parts[-1] if len(parts) > 1 else "User",
                "company_name": "Test Company"
            }]}
        )
        
    return {
        "success": True,
        "campaign_id": str(campaign_id),
        "campaign_name": campaign_name,
        "status": "DRAFT",
        "message": f"Test campaign created! Set up automation, then click Launch.",
        "next_steps": [
            f"Create automation for campaign ID: {campaign_id}",
            "Set up Google Sheet and Slack channel",
            "Wait for email and reply to test"
        ]
    }


@router.get("/test-flow/campaigns")  
async def list_test_campaigns():
    """List test campaigns."""
    import httpx
    import os
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        return {"campaigns": []}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            "https://server.smartlead.ai/api/v1/campaigns",
            params={"api_key": api_key, "limit": 100}
        )
        campaigns = resp.json()
    
    if not isinstance(campaigns, list):
        return {"campaigns": []}
    
    test_campaigns = [
        {"id": str(c["id"]), "name": c["name"], "status": c.get("status"), "created_at": c.get("created_at")}
        for c in campaigns
        if "Auto-Reply Test" in c.get("name", "") or "test" in c.get("name", "").lower()
    ]
    
    return {"campaigns": test_campaigns[:20]}



@router.get("/test-flow/check-setup/{campaign_id}")
async def check_test_setup(
    campaign_id: str,
    db: AsyncSession = Depends(get_session)
):
    """Check if an automation is set up for a test campaign."""
    from sqlalchemy import select
    
    # Check for automation with this campaign
    result = await db.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.campaign_ids.contains([campaign_id])
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        return {
            "ready": False,
            "message": "No automation found for this campaign. Please create one first.",
            "automation": None
        }
    
    return {
        "ready": True,
        "message": "Automation is set up!",
        "automation": {
            "id": automation.id,
            "name": automation.name,
            "has_slack": bool(automation.slack_channel or automation.slack_webhook_url),
            "has_sheet": bool(automation.google_sheet_id)
        }
    }





@router.get("/campaign/{campaign_id}/status")
async def get_campaign_status(campaign_id: str):
    """Get campaign status from Smartlead."""
    import httpx
    import os
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}",
            params={"api_key": api_key}
        )
        data = resp.json()
    
    return {
        "campaign_id": campaign_id,
        "name": data.get("name"),
        "status": data.get("status"),  # DRAFT, ACTIVE, PAUSED, COMPLETED
        "created_at": data.get("created_at")
    }


@router.post("/campaign/{campaign_id}/launch")
async def launch_campaign(campaign_id: str):
    """Start/launch a Smartlead campaign. Sets schedule if missing."""
    import httpx
    import os
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # First ensure schedule is set
        await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/schedule",
            params={"api_key": api_key},
            json={
                "timezone": "UTC",
                "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
                "start_hour": "00:00",
                "end_hour": "23:59",
                "min_time_btw_emails": 3,
                "max_new_leads_per_day": 100
            }
        )
        
        # Now launch
        resp = await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status",
            params={"api_key": api_key},
            json={"status": "START"}
        )
        data = resp.json()
    
    if data.get("error"):
        return {"success": False, "message": data.get("error"), "response": data}
    
    return {"success": True, "message": f"Campaign {campaign_id} launched!", "response": data}


@router.post("/campaign/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause a Smartlead campaign."""
    import httpx
    import os
    from app.services.smartlead_service import smartlead_service
    
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status",
            params={"api_key": api_key},
            json={"status": "PAUSE"}
        )
        data = resp.json()
    
    return {"success": True, "message": f"Campaign {campaign_id} paused", "response": data}





# ============= Prompt Debug Endpoints =============

class PromptDebugResponse(BaseModel):
    result: str
    tokens_used: int = 0
    model: str = ""

@router.post("/prompt-debug/run")
async def run_prompt_debug(
    request: PromptDebugRequest,
    db: AsyncSession = Depends(get_session)
):
    """Test a prompt against conversation history."""
    from app.services.openai_service import openai_service
    
    if not openai_service.is_connected():
        raise HTTPException(status_code=500, detail="OpenAI not configured")
    
    # Auto-append conversation if no placeholder
    if "{{conversation}}" in request.prompt:
        full_prompt = request.prompt.replace("{{conversation}}", request.conversation_history)
    else:
        full_prompt = request.prompt + "\n\nConversation:\n" + request.conversation_history
    
    try:
        result = await openai_service.complete(
            prompt=full_prompt,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=1000
        )
        
        return {
            "result": result,
            "model": "gpt-4o-mini"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get('/smartlead/search-leads')
async def search_leads(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_session)
):
    """Search for leads by email or name."""
    import httpx
    import os
    
    api_key = os.getenv('SMARTLEAD_API_KEY')
    results = []
    seen_emails = set()
    
    # 1. Search local database (ProcessedReply) - supports name and partial email
    local_query = select(ProcessedReply).where(
        (ProcessedReply.lead_email.ilike(f'%{q}%')) |
        (ProcessedReply.lead_first_name.ilike(f'%{q}%'))
    ).order_by(ProcessedReply.received_at.desc()).limit(10)
    
    local_result = await db.execute(local_query)
    local_leads = local_result.scalars().all()
    
    for lead in local_leads:
        if lead.lead_email and lead.lead_email not in seen_emails:
            seen_emails.add(lead.lead_email)
            results.append({
                'email': lead.lead_email,
                'campaign_name': f'Campaign {lead.campaign_id}' if lead.campaign_id else '',
                'campaign_id': str(lead.campaign_id) if lead.campaign_id else '',
                'first_name': lead.lead_first_name.split()[0] if lead.lead_first_name else '',
                'last_name': ' '.join(lead.lead_first_name.split()[1:]) if lead.lead_first_name and ' ' in lead.lead_first_name else ''
            })
    
    # 2. Try Smartlead exact email match (if looks like email)
    if api_key and '@' in q:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                lead_resp = await client.get(
                    'https://server.smartlead.ai/api/v1/leads',
                    params={'api_key': api_key, 'email': q}
                )
                
                if lead_resp.status_code == 200:
                    lead_data = lead_resp.json()
                    
                    if isinstance(lead_data, dict) and lead_data.get('email'):
                        email = lead_data['email']
                        if email not in seen_emails:
                            seen_emails.add(email)
                            campaign_info = lead_data.get('lead_campaign_data', [])
                            campaign_name = campaign_info[0].get('campaign_name', '') if campaign_info else ''
                            campaign_id = campaign_info[0].get('campaign_id', '') if campaign_info else ''
                            
                            results.insert(0, {
                                'email': email,
                                'campaign_name': campaign_name,
                                'campaign_id': str(campaign_id),
                                'first_name': lead_data.get('first_name', ''),
                                'last_name': lead_data.get('last_name', '')
                            })
            except Exception as e:
                logging.warning(f'Smartlead search failed: {e}')
    
    return {'results': results[:10]}


@router.get("/smartlead/lead-conversations/{lead_email}")
async def get_lead_conversations(
    lead_email: str,
    db: AsyncSession = Depends(get_session)
):
    """Get conversation history for a lead from local database or Smartlead API."""
    import httpx
    import os
    import re
    from app.services.smartlead_service import smartlead_service
    
    # First try local database
    query = select(ProcessedReply).where(
        ProcessedReply.lead_email.ilike(f"%{lead_email}%")
    ).order_by(ProcessedReply.received_at.desc()).limit(20)
    
    result = await db.execute(query)
    replies = result.scalars().all()
    
    if replies:
        messages = []
        for r in replies:
            messages.append({
                "type": "REPLY",
                "body": r.email_body or r.reply_text or "",
                "subject": r.email_subject,
                "timestamp": r.received_at.isoformat() if r.received_at else None,
                "category": r.category
            })
            if r.draft_reply:
                messages.append({
                    "type": "SENT",
                    "body": r.draft_reply,
                    "subject": f"Re: {r.email_subject}" if r.email_subject else "Draft Reply",
                    "timestamp": r.received_at.isoformat() if r.received_at else None,
                    "status": r.approval_status
                })
        
        first_reply = replies[0]
        return {
            "lead_email": lead_email,
            "lead_name": f"{first_reply.lead_first_name or ''} {first_reply.lead_last_name or ''}".strip(),
            "campaign": first_reply.campaign_name or f"Campaign {first_reply.campaign_id}",
            "messages": messages
        }
    
    # Fallback to Smartlead API
    api_key = os.environ.get("SMARTLEAD_API_KEY") or smartlead_service.api_key
    if not api_key:
        return {"conversations": [], "message": "Lead not found"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            lead_resp = await client.get(
                "https://server.smartlead.ai/api/v1/leads",
                params={"api_key": api_key, "email": lead_email}
            )
            lead_data = lead_resp.json()
            
            if not lead_data or not lead_data.get("id"):
                return {"conversations": [], "message": "Lead not found in Smartlead"}
            
            lead_id = lead_data["id"]
            lead_name = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
            lead_campaigns = lead_data.get("lead_campaign_data", [])
            
            messages = []
            campaign_name = ""
            
            for campaign_info in lead_campaigns[:3]:
                campaign_id = campaign_info.get("campaign_id")
                if not campaign_id:
                    continue
                    
                campaign_name = campaign_info.get("campaign_name", f"Campaign {campaign_id}")
                
                hist_resp = await client.get(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                    params={"api_key": api_key}
                )
                hist_data = hist_resp.json()
                
                for msg in hist_data.get("history", []):
                    body = msg.get("email_body", "")
                    if "<" in body:
                        body = re.sub(r"<[^>]+>", "", body)
                    
                    messages.append({
                        "type": msg.get("type", "SENT"),
                        "body": body[:500],
                        "subject": msg.get("subject", ""),
                        "timestamp": msg.get("time"),
                        "from": msg.get("from"),
                        "to": msg.get("to")
                    })
            
            if not messages:
                return {"conversations": [], "message": "No message history found"}
            
            return {
                "lead_email": lead_email,
                "lead_name": lead_name,
                "campaign": campaign_name,
                "messages": messages
            }
    except Exception as e:
        return {"conversations": [], "message": f"Error: {str(e)}"}


@router.get("/slack/status")
async def get_slack_status():
    """Check Slack Bot Token status and permissions.
    
    Returns information about whether Slack is configured correctly
    and what permissions are available/missing.
    """
    status = await get_slack_token_status()
    return status


@router.get("/slack/channels")
async def get_slack_channels(include_private: bool = False):
    """List available Slack channels for notifications.
    
    Requires channels:read scope on the Slack Bot Token.
    If permissions are missing, returns error with instructions.
    """
    result = await list_slack_channels(include_private)
    
    if not result["success"]:
        # Return 200 with error info so frontend can show actionable message
        return result
    
    return result


@router.post("/slack/channels/create")
async def create_new_slack_channel(
    name: str = Query(..., description="Name for the new channel"),
    is_private: bool = Query(False, description="Create as private channel")
):
    """Create a new Slack channel for notifications.
    
    Requires channels:write (or groups:write for private) scope.
    """
    result = await create_slack_channel(name, is_private)
    
    if not result["success"]:
        return result
    
    return result


@router.post("/slack/test-channel/{channel_id}")
async def test_slack_channel(channel_id: str):
    """Send a test message to a specific Slack channel.
    
    Args:
        channel_id: Slack channel ID (e.g., C09REGUQWTG)
    """
    result = await send_test_notification(channel_id=channel_id)
    return result

# ============= Automation Controls =============

@router.post("/automations/{automation_id}/pause")
async def pause_automation(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Pause an automation (sets active=False)."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    automation.active = False
    automation.updated_at = datetime.utcnow()
    await session.commit()
    
    logger.info(f"Paused automation {automation_id}")
    return {"success": True, "message": f"Automation '{automation.name}' paused", "active": False}


@router.post("/automations/{automation_id}/resume")
async def resume_automation(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Resume a paused automation (sets active=True)."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    automation = result.scalar_one_or_none()
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    automation.active = True
    automation.updated_at = datetime.utcnow()
    await session.commit()
    
    logger.info(f"Resumed automation {automation_id}")
    return {"success": True, "message": f"Automation '{automation.name}' resumed", "active": True}


@router.get("/automations/{automation_id}/monitoring", response_model=AutomationMonitoringStats)
async def get_single_automation_monitoring(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed monitoring stats for a single automation."""
    result = await session.execute(
        select(ReplyAutomation).where(
            ReplyAutomation.id == automation_id,
            ReplyAutomation.is_active == True
        )
    )
    auto = result.scalar_one_or_none()
    
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    
    # Today count
    today_result = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.automation_id == auto.id,
            ProcessedReply.processed_at >= today_start
        )
    )
    replies_today = today_result.scalar() or 0
    
    # Week count
    week_result = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.automation_id == auto.id,
            ProcessedReply.processed_at >= week_start
        )
    )
    replies_this_week = week_result.scalar() or 0
    
    # Status breakdown
    status_result = await session.execute(
        select(ProcessedReply.approval_status, func.count(ProcessedReply.id)).where(
            ProcessedReply.automation_id == auto.id
        ).group_by(ProcessedReply.approval_status)
    )
    pending = 0
    approved = 0
    dismissed = 0
    for row in status_result.all():
        status = row[0] or "pending"
        count = row[1]
        if status in ("pending", None):
            pending += count
        elif status == "approved":
            approved = count
        elif status == "dismissed":
            dismissed = count
    
    # Category breakdown
    cat_result = await session.execute(
        select(ProcessedReply.category, func.count(ProcessedReply.id)).where(
            ProcessedReply.automation_id == auto.id
        ).group_by(ProcessedReply.category)
    )
    by_category = {row[0] or "unknown": row[1] for row in cat_result.all()}
    
    # Determine health status
    health_status = "healthy"
    if auto.total_errors and auto.total_errors > 0:
        error_rate = auto.total_errors / max(auto.total_processed or 1, 1)
        if error_rate > 0.5:
            health_status = "error"
        elif error_rate > 0.1:
            health_status = "warning"
    
    if not auto.active:
        health_status = "paused"
    
    return AutomationMonitoringStats(
        automation_id=auto.id,
        automation_name=auto.name,
        active=auto.active,
        total_processed=auto.total_processed or 0,
        total_errors=auto.total_errors or 0,
        replies_today=replies_today,
        replies_this_week=replies_this_week,
        pending=pending,
        approved=approved,
        dismissed=dismissed,
        by_category=by_category,
        last_run_at=auto.last_run_at,
        last_error_at=auto.last_error_at,
        last_error=auto.last_error,
        created_at=auto.created_at,
        health_status=health_status
    )




@router.post("/automations/{automation_id}/sync-historical")
async def sync_historical_replies(
    automation_id: int,
    limit: int = Query(10, le=100, description="Max replies to sync"),
    db: AsyncSession = Depends(get_session)
):
    """Sync historical replies from local DB to Google Sheet."""
    import re
    
    result = await db.execute(
        select(ReplyAutomation).where(ReplyAutomation.id == automation_id)
    )
    automation = result.scalar_one_or_none()
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    if not automation.google_sheet_id:
        raise HTTPException(status_code=400, detail="No Google Sheet configured")
    
    synced = 0
    skipped = 0
    errors = []
    existing_emails = set()
    
    from app.services.google_sheets_service import google_sheets_service
    
    # Sync from local ProcessedReply database
    for campaign_id in (automation.campaign_ids or []):
        local_query = select(ProcessedReply).where(
            ProcessedReply.campaign_id == campaign_id
        ).order_by(ProcessedReply.received_at.desc()).limit(limit)
        
        local_result = await db.execute(local_query)
        local_replies = local_result.scalars().all()
        
        for reply in local_replies:
            # Skip test emails
            if reply.lead_email and ("@example.com" in reply.lead_email.lower() or "@test.com" in reply.lead_email.lower()):
                continue
            if reply.lead_email and reply.lead_email.lower() in existing_emails:
                skipped += 1
                continue
            
            row_data = {
                "lead_email": reply.lead_email or "",
                "lead_name": f"{reply.lead_first_name or ''} {reply.lead_last_name or ''}".strip(),
                "subject": reply.email_subject or "",
                "reply_text": (reply.email_body or reply.reply_text or "")[:500],
                "received_at": reply.received_at.isoformat() if reply.received_at else "",
                "campaign_name": reply.campaign_name or automation.name,
                "category": reply.category or "",
                "status": reply.approval_status or "historical"
            }
            
            try:
                google_sheets_service.append_reply(
                    automation.google_sheet_id,
                    row_data
                )
                synced += 1
                if reply.lead_email:
                    existing_emails.add(reply.lead_email.lower())
            except Exception as e:
                errors.append(f"{reply.lead_email}: {str(e)}")
    
    # If no local data, fetch from Smartlead statistics API
    if True:  # Always fetch from Smartlead API
        import httpx
        import os
        api_key = os.environ.get("SMARTLEAD_API_KEY")
        if api_key:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for campaign_id in (automation.campaign_ids or []):
                    try:
                        resp = await client.get(
                            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                            params={"api_key": api_key, "limit": limit * 10}
                        )
                        stats = resp.json()
                        for entry in stats.get("data", []):
                            if not entry.get("reply_time"):
                                continue
                            if synced >= limit:
                                break
                            lead_email = entry.get("lead_email", "").lower()
                            if lead_email in existing_emails:
                                skipped += 1
                                continue
                            
                            row_data = {
                                "lead_email": entry.get("lead_email", ""),
                                "lead_name": entry.get("lead_name", ""),
                                "subject": entry.get("email_subject", ""),
                                "reply_text": f"[Reply received at {entry.get('reply_time', '')}]",
                                "received_at": entry.get("reply_time", ""),
                                "campaign_name": automation.name,
                                "category": "",
                                "status": "historical_api"
                            }
                            try:
                                google_sheets_service.append_reply(automation.google_sheet_id, row_data)
                                synced += 1
                                existing_emails.add(lead_email)
                            except Exception as e:
                                errors.append(f"{lead_email}: {str(e)}")
                    except Exception as api_err:
                        errors.append(f"Campaign {campaign_id}: {str(api_err)}")
    
    return {
        "success": True,
        "synced": synced,
        "skipped": skipped,
        "errors": errors[:10],
        "message": f"Synced {synced} replies to Google Sheet"
    }
