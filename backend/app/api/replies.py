"""API endpoints for Reply Automation feature."""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.db import get_session
from app.models.reply import ReplyAutomation, ProcessedReply
from app.schemas.reply import (
    ReplyAutomationCreate,
    ReplyAutomationUpdate,
    ReplyAutomationResponse,
    ReplyAutomationListResponse,
    ProcessedReplyResponse,
    ProcessedReplyListResponse,
    ProcessedReplyStats,
)
from app.services.notification_service import send_test_notification, send_slack_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replies", tags=["replies"])


# ============= Test Endpoints =============

@router.post("/test-notification")
async def test_notification():
    """Test the Slack notification with sample data to #c-replies-test channel."""
    from app.services.notification_service import send_test_notification
    
    result = await send_test_notification(channel_id="C09REGUQWTG")
    return {"slack_response": result}


@router.post("/test-full-notification")
async def test_full_notification():
    """Test a full reply notification with sample data."""
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
    automation = ReplyAutomation(
        name=data.name,
        company_id=data.company_id,
        environment_id=data.environment_id,
        campaign_ids=data.campaign_ids,
        slack_webhook_url=data.slack_webhook_url,
        slack_channel=data.slack_channel,
        auto_classify=data.auto_classify,
        auto_generate_reply=data.auto_generate_reply,
        active=data.active
    )
    
    session.add(automation)
    await session.flush()
    await session.refresh(automation)
    
    logger.info(f"Created reply automation: {automation.id} - {automation.name}")
    return ReplyAutomationResponse.model_validate(automation)


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
    
    return ProcessedReplyStats(
        total=total,
        by_category=by_category,
        by_status=by_status,
        today=today,
        this_week=this_week,
        sent_to_slack=sent_to_slack,
        pending=pending_count,
        approved=approved_count,
        dismissed=dismissed_count
    )


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
