"""API endpoints for Reply Automation feature."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import asyncio

from app.db import get_session


def _utc_iso(dt) -> str:
    """Serialize datetime as ISO with Z suffix so JS interprets as UTC."""
    if dt is None:
        return ""
    iso = dt.isoformat()
    if not iso.endswith("Z") and "+" not in iso:
        return iso + "Z"
    return iso
from app.models.reply import ReplyAutomation, ProcessedReply, ReplyPromptTemplateModel, WebhookEventModel
from app.services.crm_sync_service import GETSALES_SENDER_PROFILES
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
    ContactCampaignEntry,
    ContactCampaignsResponse,
)
from app.services.notification_service import (
    send_test_notification, 
    send_slack_notification,
    get_slack_token_status,
    list_slack_channels,
    create_slack_channel
)
from app.services.google_sheets_service import google_sheets_service
from app.services.smartlead_service import smartlead_service, smartlead_request
from app.services.crm_sync_service import parse_campaigns

logger = logging.getLogger(__name__)


def _build_project_campaign_filter(project) -> list:
    """Build SQLAlchemy OR conditions for matching replies to a project.

    Returns list of conditions: exact match on campaign_filters + prefix match on project name.
    """
    parts = []
    project_campaigns = [c.lower() for c in (project.campaign_filters or []) if isinstance(c, str)]
    if project_campaigns:
        parts.append(func.lower(ProcessedReply.campaign_name).in_(project_campaigns))
    project_name_lower = (project.name or "").lower()
    if project_name_lower and len(project_name_lower) > 2:
        parts.append(func.lower(ProcessedReply.campaign_name).like(f"{project_name_lower}%"))
    return parts


router = APIRouter(prefix="/replies", tags=["replies"])


def _text_to_html(text: str) -> str:
    """Convert plain text with newlines to HTML paragraphs."""
    import html as html_mod
    text = html_mod.escape(text)
    paragraphs = text.split('\n\n')
    parts = []
    for p in paragraphs:
        p = p.strip()
        if p:
            p = p.replace('\n', '<br>')
            parts.append(f'<p>{p}</p>')
    return ''.join(parts) or '<p></p>'


def _parse_raw_webhook_data(reply) -> dict:
    """Parse raw_webhook_data from a ProcessedReply, handling str or dict."""
    raw = reply.raw_webhook_data or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return raw


def _extract_sender_name(reply) -> Optional[str]:
    """Extract human sender name (the person, not the campaign).

    LinkedIn: person name from GETSALES_SENDER_PROFILES (sender_profile_uuid)
    Email: from_email (the inbox/mailbox email address)
    """
    raw = _parse_raw_webhook_data(reply)

    if reply.channel == "linkedin" or reply.source == "getsales":
        sp_uuid = raw.get("sender_profile_uuid") or (
            (raw.get("automation", {}) or {}).get("sender_profile_uuid")
            if isinstance(raw.get("automation"), dict) else None
        )
        if sp_uuid and sp_uuid in GETSALES_SENDER_PROFILES:
            return GETSALES_SENDER_PROFILES[sp_uuid]
        if reply.campaign_name and " - " in reply.campaign_name:
            return reply.campaign_name.split(" - ", 1)[1]
        return None

    if reply.channel == "email" or reply.source == "smartlead":
        return raw.get("from_email") or None

    return None


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


# ============= Reply Automations (DISABLED) =============
# Automations are redundant: the app now tracks all replies automatically
# across all campaigns. Per-project campaign_filters + auto-gathered prompts
# handle classification and draft generation. No per-automation setup needed.
#
# To re-enable, create a separate router_automations and include it.

_AUTOMATIONS_DISABLED = True  # flip to False to re-enable automation routes


def _check_automations_disabled():
    """Raise 410 Gone if automations are disabled."""
    if _AUTOMATIONS_DISABLED:
        raise HTTPException(
            status_code=410,
            detail="Automation management is disabled. Replies are now tracked automatically per-project via campaign_filters."
        )


@router.get("/automations", response_model=ReplyAutomationListResponse)
async def list_automations(
    company_id: Optional[int] = None,
    active_only: bool = True,
    session: AsyncSession = Depends(get_session)
):
    """List all reply automations."""
    _check_automations_disabled()
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



async def _sync_historical_replies_background(automation_id: int, google_sheet_id: str, campaign_ids: list, automation_name: str):
    """Background task to sync historical replies without blocking API response."""
    import os
    import re as regex

    api_key = os.environ.get("SMARTLEAD_API_KEY")
    synced = 0
    existing_emails = set()

    try:
        if api_key:
            for campaign_id in campaign_ids:
                offset = 0
                page_size = 500
                empty_pages = 0

                while offset < 5000 and empty_pages < 3:
                    try:
                        resp = await smartlead_request(
                            "GET",
                            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                            params={"api_key": api_key, "limit": page_size, "offset": offset},
                            timeout=60.0,
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
                            if "@example.com" in lead_email or "@test.com" in lead_email:
                                continue
                            if lead_email in existing_emails:
                                continue

                            reply_text = ""
                            try:
                                lead_resp = await smartlead_request(
                                    "GET",
                                    "https://server.smartlead.ai/api/v1/leads",
                                    params={"api_key": api_key, "email": entry.get("lead_email")},
                                    timeout=60.0,
                                )
                                lead_data = lead_resp.json()
                                lead_id = lead_data.get("id")
                                if lead_id:
                                    hist_resp = await smartlead_request(
                                        "GET",
                                        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                                        params={"api_key": api_key},
                                        timeout=60.0,
                                    )
                                    from app.services.smartlead_service import parse_history_response
                                    for msg in parse_history_response(hist_resp.json()):
                                        if msg.get("type") == "REPLY":
                                            reply_text = msg.get("email_body", "")
                                            if "<" in reply_text:
                                                reply_text = regex.sub(r"<[^>]+>", " ", reply_text)
                                                reply_text = regex.sub(r"\s+", " ", reply_text).strip()
                                            break
                            except Exception:
                                pass

                            row_data = {
                                "lead_email": entry.get("lead_email", ""),
                                "lead_name": entry.get("lead_name", ""),
                                "subject": entry.get("email_subject", ""),
                                "reply_text": reply_text[:1000] if reply_text else f"[Reply at {entry.get('reply_time', '')}]",
                                "received_at": entry.get("reply_time", ""),
                                "campaign_name": automation_name,
                                "smartlead_status": entry.get("lead_category", "") or "",
                                "source": "historical"
                            }
                            google_sheets_service.append_reply(google_sheet_id, row_data)
                            synced += 1
                            existing_emails.add(lead_email)

                        offset += page_size
                    except Exception as api_err:
                        logger.warning(f"Failed to fetch stats for campaign {campaign_id}: {api_err}")
                        break

        if synced > 0:
            logger.info(f"Background sync: {synced} historical replies to Google Sheet")
    except Exception as e:
        logger.warning(f"Background sync failed: {e}")


@router.post("/automations", response_model=ReplyAutomationResponse)
async def create_automation(
    background_tasks: BackgroundTasks,
    data: ReplyAutomationCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new reply automation."""
    _check_automations_disabled()
    
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
    
    # Webhooks are managed exclusively by the CRM scheduler (setup_crm_webhooks_on_startup).
    # Never register webhooks inline — that caused 360+ duplicates across 102 campaigns.
    logger.info(f"Created reply automation: {automation.id} - {automation.name}")
    
    # Auto-sync historical replies in background (non-blocking)
    if automation.google_sheet_id and automation.campaign_ids:
        background_tasks.add_task(
            _sync_historical_replies_background,
            automation.id,
            automation.google_sheet_id,
            automation.campaign_ids,
            automation.name
        )
    
    return ReplyAutomationResponse.model_validate(automation)


# IMPORTANT: This route must be before /automations/{automation_id} to avoid route conflicts
@router.get("/automations/monitoring", response_model=AutomationMonitoringListResponse)
async def get_automation_monitoring_list(
    session: AsyncSession = Depends(get_session)
):
    """Get detailed monitoring stats for all automations."""
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    
    # Webhooks are managed exclusively by the CRM scheduler — never inline.
    logger.info(f"Added {len(campaign_ids)} campaigns to automation {automation_id}")
    return {"automation_id": automation_id, "campaign_ids": updated, "added": campaign_ids}


@router.delete("/automations/{automation_id}/campaigns/{campaign_id}")
async def remove_campaign_from_automation(
    automation_id: int,
    campaign_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Remove a campaign from an automation."""
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    campaign_names: Optional[str] = Query(None, description="Comma-separated campaign names to filter by"),
    project_id: Optional[int] = Query(None, description="Filter by project (uses project's campaign_filters)"),
    category: Optional[str] = None,
    approval_status: Optional[str] = Query(None, description="Filter by status: pending, approved, dismissed"),
    needs_reply: Optional[bool] = Query(None, description="Filter to replies with no outbound activity after received_at"),
    channel: Optional[str] = Query(None, description="Filter by channel: email, linkedin"),
    source: Optional[str] = Query(None, description="Filter by source: smartlead, getsales"),
    lead_email: Optional[str] = Query(None, description="Filter by lead email (exact match)"),
    group_by_contact: bool = Query(False, description="Dedup by lead_email, one card per unique contact"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    """List processed replies with filters.

    Dashboard can filter by approval_status to show pending/approved/dismissed replies.
    Use project_id to filter by a project's campaign_filters (e.g., Rizzult campaigns).
    Use group_by_contact=true to dedup by lead_email (one card per unique contact).
    """
    from sqlalchemy import case, or_, and_

    # --- Build reusable filter conditions ---
    conditions = []

    if lead_email:
        conditions.append(ProcessedReply.lead_email == lead_email)

    if automation_id:
        conditions.append(ProcessedReply.automation_id == automation_id)

    if campaign_id:
        conditions.append(ProcessedReply.campaign_id == campaign_id)

    # Filter by project's campaign_filters (case-insensitive) + prefix match
    if project_id:
        from app.models.contact import Project
        project_result = await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            filter_parts = _build_project_campaign_filter(project)
            if filter_parts:
                conditions.append(or_(*filter_parts))

    if campaign_names:
        names = [n.strip().lower() for n in campaign_names.split(",") if n.strip()]
        if names:
            conditions.append(func.lower(ProcessedReply.campaign_name).in_(names))

    if channel:
        conditions.append(ProcessedReply.channel == channel)

    if source:
        conditions.append(ProcessedReply.source == source)

    # Filter by approval status
    if approval_status:
        if approval_status == "pending":
            conditions.append(or_(
                ProcessedReply.approval_status == None,
                ProcessedReply.approval_status == "pending",
            ))
        else:
            conditions.append(ProcessedReply.approval_status == approval_status)

    # needs_reply filter
    if needs_reply:
        conditions.append(or_(
            ProcessedReply.approval_status == None,
            ProcessedReply.approval_status == "pending",
        ))
        no_reply_categories = ("out_of_office", "unsubscribe", "wrong_person", "not_interested")
        conditions.append(or_(
            ProcessedReply.category == None,
            ~ProcessedReply.category.in_(no_reply_categories),
        ))
        # Exclude replies with empty/meaningless bodies
        empty_bodies = ("(empty)", "(no content)", "no content", "empty", "")
        conditions.append(
            ~func.coalesce(func.trim(func.lower(
                func.coalesce(ProcessedReply.email_body, ProcessedReply.reply_text)
            )), '').in_(empty_bodies)
        )

    # Snapshot conditions BEFORE adding category filter — used for global tab counts
    base_conditions = list(conditions)

    if category:
        conditions.append(ProcessedReply.category == category)

    # Category priority expression
    category_priority = case(
        (ProcessedReply.category == "meeting_request", 0),
        (ProcessedReply.category == "interested", 1),
        (ProcessedReply.category == "question", 2),
        (ProcessedReply.category == "other", 3),
        else_=4,
    )

    if group_by_contact:
        # --- DEDUP MODE: one row per unique lead_email ---
        # PostgreSQL DISTINCT ON (lead_email): picks one row per email based on ORDER BY.
        # SQLAlchemy: select(...).distinct(col) => SELECT DISTINCT ON (col) ...

        # Subquery: pick one reply ID per lead_email (best category, then newest)
        dedup_sub = (
            select(ProcessedReply.lead_email.label("_dedup_email"), ProcessedReply.id.label("id"))
            .distinct(ProcessedReply.lead_email)
            .where(*conditions)
            .order_by(ProcessedReply.lead_email, category_priority, desc(ProcessedReply.received_at))
        ).subquery()

        # Total unique contacts
        total_result = await session.execute(
            select(func.count()).select_from(dedup_sub)
        )
        total = total_result.scalar() or 0

        # Hydrate full rows, paginate
        query = (
            select(ProcessedReply)
            .where(ProcessedReply.id.in_(select(dedup_sub.c.id)))
            .order_by(category_priority, desc(ProcessedReply.received_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(query)
        replies = result.scalars().all()

        # Compute contact_campaign_count: distinct campaigns per email
        # Uses base_conditions (project + needs_reply filters) to match what the campaign dropdown shows
        page_emails = list({r.lead_email for r in replies})
        campaign_count_map: dict = {}
        if page_emails:
            count_q = (
                select(
                    ProcessedReply.lead_email,
                    func.count(func.distinct(ProcessedReply.campaign_name)),
                )
                .where(
                    ProcessedReply.lead_email.in_(page_emails),
                    *base_conditions,
                )
                .group_by(ProcessedReply.lead_email)
            )
            count_result = await session.execute(count_q)
            campaign_count_map = {row[0]: row[1] for row in count_result.all()}

        reply_responses = []
        for r in replies:
            resp = ProcessedReplyResponse.model_validate(r)
            resp.contact_campaign_count = campaign_count_map.get(r.lead_email, 1)
            resp.sender_name = _extract_sender_name(r)
            reply_responses.append(resp)

        # Category counts — deduped, using base_conditions (without category filter) for global tab counts
        category_counts: dict = {}
        try:
            cat_sub = (
                select(ProcessedReply.lead_email.label("_dedup_email"), ProcessedReply.category.label("category"))
                .distinct(ProcessedReply.lead_email)
                .where(*base_conditions)
                .order_by(ProcessedReply.lead_email, category_priority, desc(ProcessedReply.received_at))
            ).subquery()
            cat_q = (
                select(cat_sub.c.category, func.count())
                .group_by(cat_sub.c.category)
            )
            cat_result = await session.execute(cat_q)
            category_counts = {row[0] or "other": row[1] for row in cat_result.all()}
        except Exception as e:
            logger.warning(f"Failed to compute grouped category counts: {e}")

        meeting_count = category_counts.get("meeting_request", 0)

        return ProcessedReplyListResponse(
            replies=reply_responses,
            total=total,
            meeting_count=meeting_count,
            category_counts=category_counts,
            page=page,
            page_size=page_size,
        )

    # --- NORMAL MODE (no dedup) ---
    query = select(ProcessedReply).where(*conditions) if conditions else select(ProcessedReply)
    count_query = select(func.count(ProcessedReply.id))
    if conditions:
        count_query = count_query.where(*conditions)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Category counts
    category_counts: dict = {}
    try:
        # Build conditions for category counts (needs_reply filters always apply)
        cat_conditions = []
        cat_conditions.append(or_(ProcessedReply.approval_status == None, ProcessedReply.approval_status == "pending"))
        no_reply_cats = ("out_of_office", "unsubscribe", "wrong_person", "not_interested")
        cat_conditions.append(or_(ProcessedReply.category == None, ~ProcessedReply.category.in_(no_reply_cats)))
        empty_bodies_cat = ("(empty)", "(no content)", "no content", "empty", "")
        cat_conditions.append(~func.coalesce(func.trim(func.lower(
            func.coalesce(ProcessedReply.email_body, ProcessedReply.reply_text)
        )), '').in_(empty_bodies_cat))
        # Apply project/campaign filter if present
        if project_id:
            from app.models.contact import Project
            proj_r = await session.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
            proj = proj_r.scalar_one_or_none()
            if proj and proj.campaign_filters:
                pc = [c.lower() for c in proj.campaign_filters if isinstance(c, str)]
                if pc:
                    cat_conditions.append(func.lower(ProcessedReply.campaign_name).in_(pc))
        elif campaign_names:
            names = [n.strip().lower() for n in campaign_names.split(",") if n.strip()]
            if names:
                cat_conditions.append(func.lower(ProcessedReply.campaign_name).in_(names))
        cat_q = (
            select(ProcessedReply.category, func.count(func.distinct(ProcessedReply.lead_email)))
            .where(*cat_conditions)
            .group_by(ProcessedReply.category)
        )
        cat_result = await session.execute(cat_q)
        category_counts = {row[0] or "other": row[1] for row in cat_result.all()}
    except Exception as e:
        logger.warning(f"Failed to compute category counts: {e}")
    meeting_count = category_counts.get("meeting_request", 0)

    # Order by category priority (meetings/interested first), then newest
    query = query.order_by(category_priority, desc(ProcessedReply.received_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    replies = result.scalars().all()

    # Batch-load contact info for all replies on this page
    from app.models.contact import Contact
    page_emails = list({r.lead_email.lower() for r in replies if r.lead_email})
    contact_map: dict = {}
    if page_emails:
        contact_result = await session.execute(
            select(Contact).where(
                and_(func.lower(Contact.email).in_(page_emails), Contact.deleted_at.is_(None))
            )
        )
        for c in contact_result.scalars().all():
            contact_map[c.email.lower()] = _build_contact_info(c)

    reply_responses = []
    for r in replies:
        resp = ProcessedReplyResponse.model_validate(r)
        resp.sender_name = _extract_sender_name(r)
        resp.contact_info = contact_map.get(r.lead_email.lower()) if r.lead_email else None
        reply_responses.append(resp)

    return ProcessedReplyListResponse(
        replies=reply_responses,
        total=total,
        meeting_count=meeting_count,
        category_counts=category_counts,
        page=page,
        page_size=page_size
    )


@router.get("/counts")
async def get_reply_counts(
    project_id: Optional[int] = Query(None),
    campaign_names: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    """Lightweight endpoint for polling: returns total + category counts only.
    No reply data, no group_by_contact dedup, no joins.
    """
    base = []
    base.append(or_(ProcessedReply.approval_status == None, ProcessedReply.approval_status == "pending"))
    no_reply_cats = ("out_of_office", "unsubscribe", "wrong_person", "not_interested")
    base.append(or_(ProcessedReply.category == None, ~ProcessedReply.category.in_(no_reply_cats)))
    empty_bodies = ("(empty)", "(no content)", "no content", "empty", "")
    base.append(~func.coalesce(func.trim(func.lower(
        func.coalesce(ProcessedReply.email_body, ProcessedReply.reply_text)
    )), '').in_(empty_bodies))

    if project_id:
        from app.models.contact import Project
        proj_r = await session.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
        proj = proj_r.scalar_one_or_none()
        if proj and proj.campaign_filters:
            pc = [c.lower() for c in proj.campaign_filters if isinstance(c, str)]
            if pc:
                base.append(func.lower(ProcessedReply.campaign_name).in_(pc))
    elif campaign_names:
        names = [n.strip().lower() for n in campaign_names.split(",") if n.strip()]
        if names:
            base.append(func.lower(ProcessedReply.campaign_name).in_(names))

    # Single query: total + category counts via COUNT with FILTER
    total_q = select(func.count(func.distinct(ProcessedReply.lead_email))).where(*base)
    total_r = await session.execute(total_q)
    total = total_r.scalar() or 0

    cat_q = (
        select(ProcessedReply.category, func.count(func.distinct(ProcessedReply.lead_email)))
        .where(*base)
        .group_by(ProcessedReply.category)
    )
    cat_r = await session.execute(cat_q)
    category_counts = {row[0] or "other": row[1] for row in cat_r.all()}

    return {"total": total, "category_counts": category_counts}


@router.post("/contact-info-batch")
async def get_contact_info_batch(
    emails: List[str],
    session: AsyncSession = Depends(get_session)
):
    """Lightweight batch endpoint: returns contact info for multiple emails.
    Used to eagerly load LinkedIn, job title, company, etc. without full history.
    """
    from app.models.contact import Contact
    if not emails or len(emails) > 50:
        return {"contacts": {}}

    results = {}
    for email in emails:
        result = await session.execute(
            select(Contact).where(
                and_(func.lower(Contact.email) == email.lower(), Contact.deleted_at.is_(None))
            ).limit(1)
        )
        contact = result.scalar_one_or_none()
        if contact:
            results[email] = _build_contact_info(contact)
    return {"contacts": results}


@router.get("/contact-campaigns/{lead_email}", response_model=ContactCampaignsResponse)
async def get_contact_campaigns(
    lead_email: str,
    project_id: Optional[int] = Query(None, description="Filter by project's campaign_filters"),
    session: AsyncSession = Depends(get_session)
):
    """Get all campaign replies for a specific contact email.

    Returns all ProcessedReply records for this email within the project filter,
    sorted by received_at DESC (most recent first). Used by the frontend campaign
    selector to switch between campaigns for a deduped contact.
    """
    from sqlalchemy import or_

    conditions = [ProcessedReply.lead_email == lead_email]

    # needs_reply conditions (only show actionable replies)
    conditions.append(or_(
        ProcessedReply.approval_status == None,
        ProcessedReply.approval_status == "pending",
    ))
    no_reply_categories = ("out_of_office", "unsubscribe", "wrong_person", "not_interested")
    conditions.append(or_(
        ProcessedReply.category == None,
        ~ProcessedReply.category.in_(no_reply_categories),
    ))

    if project_id:
        from app.models.contact import Project
        project_result = await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            filter_parts = _build_project_campaign_filter(project)
            if filter_parts:
                conditions.append(or_(*filter_parts))

    query = (
        select(ProcessedReply)
        .where(*conditions)
        .order_by(desc(ProcessedReply.received_at))
    )
    result = await session.execute(query)
    replies = result.scalars().all()

    campaigns = [
        ContactCampaignEntry(
            reply_id=r.id,
            campaign_id=r.campaign_id,
            campaign_name=r.campaign_name,
            category=r.category,
            classification_reasoning=r.classification_reasoning,
            received_at=r.received_at,
            email_subject=r.email_subject,
            email_body=r.email_body,
            reply_text=r.reply_text,
            draft_reply=r.draft_reply,
            draft_subject=r.draft_subject,
            approval_status=r.approval_status,
            inbox_link=r.inbox_link,
            channel=r.channel,
        )
        for r in replies
    ]

    return ContactCampaignsResponse(
        lead_email=lead_email,
        campaigns=campaigns,
        total=len(campaigns),
    )


@router.get("/stats", response_model=ProcessedReplyStats)
async def get_reply_stats(
    automation_id: Optional[int] = None,
    campaign_id: Optional[str] = None,
    campaign_names: Optional[str] = Query(None, description="Comma-separated campaign names to filter by"),
    project_id: Optional[int] = Query(None, description="Filter by project (uses project's campaign_filters)"),
    session: AsyncSession = Depends(get_session)
):
    """Get statistics for processed replies."""
    base_query = select(ProcessedReply)

    if automation_id:
        base_query = base_query.where(ProcessedReply.automation_id == automation_id)
    if campaign_id:
        base_query = base_query.where(ProcessedReply.campaign_id == campaign_id)

    # Filter by project's campaign_filters + prefix match
    _project_filter_condition = None
    _campaign_name_list = None
    if project_id:
        from app.models.contact import Project
        project_result = await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            filter_parts = _build_project_campaign_filter(project)
            if filter_parts:
                _project_filter_condition = or_(*filter_parts)
                base_query = base_query.where(_project_filter_condition)

    # Multi-campaign name filter (from global project selector)
    if campaign_names:
        names = [n.strip() for n in campaign_names.split(",") if n.strip()]
        if names:
            _campaign_name_list = names
            base_query = base_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))
    
    # Total count
    sub = base_query.subquery()
    total_result = await session.execute(
        select(func.count()).select_from(sub)
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
    if _campaign_name_list:
        category_query = category_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    if _campaign_name_list:
        today_query = today_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    if _campaign_name_list:
        week_query = week_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    if _campaign_name_list:
        slack_query = slack_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    if _campaign_name_list:
        status_query = status_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    if _campaign_name_list:
        automation_query = automation_query.where(ProcessedReply.campaign_name.in_(_campaign_name_list))

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
    sender_name: Optional[str] = None,
    sender_position: Optional[str] = None,
    sender_company: Optional[str] = None,
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
        custom_prompt=reply_prompt,
        sender_name=sender_name,
        sender_position=sender_position,
        sender_company=sender_company,
    )
    
    # Generate reply
    draft = await generate_draft_reply(
        subject=subject,
        body=body,
        category=classification["category"],
        first_name=first_name,
        last_name=last_name,
        company=company,
        custom_prompt=reply_prompt,
        sender_name=sender_name,
        sender_position=sender_position,
        sender_company=sender_company,
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


@router.get("/{reply_id}/conversation")
async def get_reply_conversation(
    reply_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get the conversation thread for a reply's contact.

    Cache-first: reads from thread_messages (pre-fetched at processing time).
    If cache is empty (pre-fetch failed), fetches on demand as fallback.
    """
    from app.models.contact import Contact
    from app.models.reply import ThreadMessage
    from app.services.reply_processor import _fetch_and_cache_thread

    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    if not reply.lead_email:
        return {"messages": []}

    # Find contact by email
    contact = None
    if reply.lead_email:
        contact_result = await session.execute(
            select(Contact).where(
                and_(
                    func.lower(Contact.email) == reply.lead_email.lower(),
                    Contact.deleted_at.is_(None),
                )
            )
        )
        contact = contact_result.scalar_one_or_none()

    contact_id = contact.id if contact else None

    # --- Cache miss or stale (>5 min): re-fetch on demand ---
    cache_stale = (
        reply.thread_fetched_at is not None
        and (datetime.utcnow() - reply.thread_fetched_at).total_seconds() > 300
    )
    need_fetch = (reply.thread_fetched_at is None or cache_stale)
    if need_fetch and reply.campaign_id and (not reply.source or reply.source == "smartlead"):
        try:
            ok = await _fetch_and_cache_thread(reply, session)
            if ok:
                await session.commit()
        except Exception as e:
            logger.warning(f"get_reply_conversation: fallback fetch failed for reply {reply_id}: {e}")
            await session.rollback()

    # --- Cache hit: read from thread_messages ---
    messages = []
    if reply.thread_fetched_at is not None:
        tm_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.reply_id == reply.id)
            .order_by(ThreadMessage.position)
        )
        for tm in tm_result.scalars().all():
            messages.append({
                "direction": tm.direction,
                "channel": tm.channel,
                "subject": tm.subject,
                "body": tm.body,
                "activity_at": _utc_iso(tm.activity_at),
                "source": tm.source,
                "activity_type": tm.activity_type,
            })

    contact_info = _build_contact_info(contact) if contact else None

    return {
        "messages": messages,
        "contact_id": contact_id,
        "approval_status": reply.approval_status,
        "contact_info": contact_info,
    }


async def _fetch_getsales_conversation(contact, reply, session) -> None:
    """On-demand: fetch full LinkedIn conversation from GetSales API and cache as ContactActivity.

    Called when a GetSales reply has no outbound activities (messages we sent).
    Uses linkedin_conversation_uuid from the inbound activity or raw_webhook_data.
    """
    from app.models.contact import ContactActivity
    from app.services.crm_sync_service import GetSalesClient
    from app.core.config import settings

    try:
        if not settings.GETSALES_API_KEY:
            return

        # Find conversation UUID from existing activity or reply's raw data
        conv_uuid = None
        existing_activity = await session.execute(
            select(ContactActivity).where(
                and_(
                    ContactActivity.contact_id == contact.id,
                    ContactActivity.channel == "linkedin",
                )
            ).limit(1)
        )
        ca = existing_activity.scalar_one_or_none()
        if ca and ca.extra_data and isinstance(ca.extra_data, dict):
            conv_uuid = ca.extra_data.get("linkedin_conversation_uuid")

        if not conv_uuid and reply.raw_webhook_data and isinstance(reply.raw_webhook_data, dict):
            conv_uuid = (
                reply.raw_webhook_data.get("linkedin_conversation_uuid")
                or (reply.raw_webhook_data.get("linkedin_message") or {}).get("linkedin_conversation_uuid")
            )

        if not conv_uuid:
            logger.info(f"[GETSALES] No conversation UUID for contact {contact.id}, skipping on-demand fetch")
            return

        gs = GetSalesClient(settings.GETSALES_API_KEY)
        messages = await gs.get_conversation_messages(conv_uuid, limit=100)
        if not messages:
            return

        new_count = 0
        for msg in messages:
            message_id = msg.get("uuid")
            if not message_id:
                continue

            existing_check = await session.execute(
                select(ContactActivity.id).where(
                    and_(
                        ContactActivity.source == "getsales",
                        ContactActivity.source_id == str(message_id),
                    )
                )
            )
            if existing_check.scalar_one_or_none():
                continue

            msg_type = msg.get("type", "")
            is_inbound = msg_type == "inbox"
            activity_type = "linkedin_replied" if is_inbound else "linkedin_sent"
            direction = "inbound" if is_inbound else "outbound"

            created_at_str = msg.get("created_at")
            activity_at = datetime.utcnow()
            if created_at_str:
                try:
                    activity_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass

            activity = ContactActivity(
                contact_id=contact.id,
                company_id=contact.company_id or 1,
                activity_type=activity_type,
                channel="linkedin",
                direction=direction,
                source="getsales",
                source_id=str(message_id),
                body=msg.get("text"),
                snippet=(msg.get("text") or "")[:200],
                extra_data={
                    "linkedin_conversation_uuid": conv_uuid,
                    "sender_profile_uuid": msg.get("sender_profile_uuid"),
                },
                activity_at=activity_at,
            )
            session.add(activity)
            new_count += 1

        if new_count:
            await session.flush()
            logger.info(f"[GETSALES] On-demand fetch: created {new_count} activities for contact {contact.id}")

    except Exception as e:
        logger.warning(f"[GETSALES] On-demand conversation fetch failed (non-fatal): {e}")
        await session.rollback()


def _build_contact_info(contact) -> dict:
    """Extract display-safe contact info dict."""
    all_campaigns = (
        contact.get_platform("smartlead").get("campaigns", [])
        + contact.get_platform("getsales").get("campaigns", [])
    )
    return {
        "linkedin_url": contact.linkedin_url,
        "phone": contact.phone,
        "job_title": contact.job_title,
        "company_name": contact.company_name,
        "domain": contact.domain,
        "location": contact.location,
        "segment": contact.segment,
        "source": contact.source,
        "campaigns": all_campaigns,
    }


@router.get("/{reply_id}/full-history")
async def get_reply_full_history(
    reply_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Fast: campaign list (pure DB) + only default campaign's thread.

    No SmartLead API calls for non-default campaigns.
    Other campaigns' threads are loaded on demand via /campaign-thread.
    """
    from app.models.reply import ThreadMessage
    from app.models.contact import Contact, ContactActivity
    from app.services.reply_processor import _fetch_and_cache_thread

    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    if not reply.lead_email:
        return {"campaigns": [], "activities": [], "approval_status": reply.approval_status}

    # 1. Find ALL replies for this lead (cheap DB query — no API calls)
    all_replies_result = await session.execute(
        select(ProcessedReply).where(
            func.lower(ProcessedReply.lead_email) == reply.lead_email.lower()
        ).order_by(desc(ProcessedReply.received_at))
    )
    all_replies = all_replies_result.scalars().all()

    # 2. Build campaign summary from ProcessedReply records (pure DB, instant)
    campaign_map: dict[str, dict] = {}
    for r in all_replies:
        cname = r.campaign_name or f"Campaign {r.campaign_id}"
        ch = r.channel or ("linkedin" if r.source == "getsales" else "email")
        key = f"{ch}::{cname}"
        ts = r.received_at.isoformat() + "Z" if r.received_at else ""
        if key not in campaign_map:
            campaign_map[key] = {
                "campaign_name": cname,
                "channel": ch,
                "message_count": 1,
                "latest_at": ts,
                "earliest_at": ts,
                "reply_id": r.id,
            }
        else:
            campaign_map[key]["message_count"] += 1
            if ts and ts > campaign_map[key]["latest_at"]:
                campaign_map[key]["latest_at"] = ts
            if ts and (not campaign_map[key]["earliest_at"] or ts < campaign_map[key]["earliest_at"]):
                campaign_map[key]["earliest_at"] = ts

    # Pin the reply's own campaign first, then sort rest by recency
    reply_campaign_key = f"{reply.channel or 'email'}::{reply.campaign_name or ''}"
    campaigns_sorted = sorted(
        campaign_map.values(),
        key=lambda c: (
            0 if f"{c['channel']}::{c['campaign_name']}" == reply_campaign_key else 1,
            c.get("latest_at", ""),
        ),
        reverse=False,
    )
    # Re-sort: first item is reply's campaign (sort key 0), rest by latest_at DESC
    own = [c for c in campaigns_sorted if f"{c['channel']}::{c['campaign_name']}" == reply_campaign_key]
    rest = sorted(
        [c for c in campaigns_sorted if f"{c['channel']}::{c['campaign_name']}" != reply_campaign_key],
        key=lambda c: c.get("latest_at", ""),
        reverse=True,
    )
    campaigns_sorted = own + rest

    # 3. Fetch thread ONLY for the default (most recent) campaign's reply
    default_reply = reply
    activities = []
    if default_reply.thread_fetched_at is None and default_reply.campaign_id and (not default_reply.source or default_reply.source == "smartlead"):
        try:
            ok = await _fetch_and_cache_thread(default_reply, session)
            if ok:
                await session.commit()
        except Exception as e:
            logger.warning(f"full-history: default thread fetch failed: {e}")
            await session.rollback()

    if default_reply.thread_fetched_at is not None:
        tm_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.reply_id == default_reply.id)
            .order_by(ThreadMessage.activity_at)
        )
        default_campaign = default_reply.campaign_name or f"Campaign {default_reply.campaign_id}"
        for tm in tm_result.scalars().all():
            activities.append({
                "direction": tm.direction,
                "content": tm.body or "",
                "timestamp": tm.activity_at.isoformat() + "Z" if tm.activity_at else "",
                "channel": tm.channel or "email",
                "campaign": default_campaign,
            })

    # 4. LinkedIn activities (if getsales contact)
    contact = None
    contact_result = await session.execute(
        select(Contact).where(
            and_(func.lower(Contact.email) == reply.lead_email.lower(), Contact.deleted_at.is_(None))
        )
    )
    contact = contact_result.scalar_one_or_none()

    if contact:
        # On-demand fetch: if no outbound activities exist, pull conversation from GetSales API
        outbound_check = await session.execute(
            select(func.count()).select_from(ContactActivity).where(
                and_(
                    ContactActivity.contact_id == contact.id,
                    ContactActivity.channel == "linkedin",
                    ContactActivity.direction == "outbound",
                )
            )
        )
        has_outbound = (outbound_check.scalar() or 0) > 0

        if not has_outbound and (reply.source == "getsales" or reply.channel == "linkedin"):
            await _fetch_getsales_conversation(contact, reply, session)

            # After fetching full conversation, check if operator already replied.
            # If last message is outbound and reply is still pending, auto-dismiss.
            last_outbound_check = await session.execute(
                select(ContactActivity.direction).where(
                    and_(
                        ContactActivity.contact_id == contact.id,
                        ContactActivity.channel == "linkedin",
                    )
                ).order_by(ContactActivity.activity_at.desc()).limit(1)
            )
            last_direction = last_outbound_check.scalar()
            if last_direction == "outbound" and reply.approval_status in (None, "pending"):
                reply.approval_status = "dismissed"
                reply.approved_at = datetime.utcnow()
                session.add(reply)
                await session.commit()
                await session.refresh(reply)
                logger.info(f"[AUTO-DISMISS] Reply {reply.id} auto-dismissed — operator already replied via LinkedIn")

        ca_result = await session.execute(
            select(ContactActivity).where(
                and_(ContactActivity.contact_id == contact.id, ContactActivity.channel == "linkedin")
            ).order_by(ContactActivity.activity_at)
        )
        linkedin_fallback_campaign = reply.campaign_name or "LinkedIn"
        for ca in ca_result.scalars().all():
            direction = ca.direction or ("outbound" if ca.activity_type in ("linkedin_sent",) else "inbound")
            cname = linkedin_fallback_campaign
            if ca.extra_data and isinstance(ca.extra_data, dict):
                cname = ca.extra_data.get("automation_name") or ca.extra_data.get("campaign_name") or linkedin_fallback_campaign
            activities.append({
                "direction": direction,
                "content": ca.body or ca.snippet or "",
                "timestamp": ca.activity_at.isoformat() + "Z" if ca.activity_at else "",
                "channel": "linkedin",
                "campaign": cname,
            })

    activities.sort(key=lambda a: a["timestamp"])

    inbox_links = {
        (r.campaign_name or f"Campaign {r.campaign_id}"): r.inbox_link
        for r in all_replies if r.inbox_link
    }
    contact_info = _build_contact_info(contact) if contact else None

    return {
        "contact_id": contact.id if contact else None,
        "contact_info": contact_info,
        "campaigns": campaigns_sorted,
        "activities": activities,
        "approval_status": reply.approval_status,
        "inbox_links": inbox_links,
    }


@router.get("/{reply_id}/campaign-thread")
async def get_campaign_thread(
    reply_id: int,
    campaign_name: str = Query(..., description="Campaign name to load thread for"),
    session: AsyncSession = Depends(get_session)
):
    """On-demand: fetch a single campaign's conversation thread.

    Called when user clicks a different campaign in the dropdown.
    Only fetches from SmartLead API if thread was never cached.
    """
    from app.models.reply import ThreadMessage
    from app.services.reply_processor import _fetch_and_cache_thread

    result = await session.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    source_reply = result.scalar_one_or_none()
    if not source_reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    if not source_reply.lead_email:
        return {"activities": []}

    # Find the ProcessedReply for the requested campaign
    target_result = await session.execute(
        select(ProcessedReply).where(
            and_(
                func.lower(ProcessedReply.lead_email) == source_reply.lead_email.lower(),
                ProcessedReply.campaign_name == campaign_name,
            )
        ).order_by(desc(ProcessedReply.received_at)).limit(1)
    )
    target_reply = target_result.scalar_one_or_none()
    if not target_reply:
        return {"activities": []}

    # Fetch thread if never cached
    if target_reply.thread_fetched_at is None and target_reply.campaign_id and (not target_reply.source or target_reply.source == "smartlead"):
        try:
            ok = await _fetch_and_cache_thread(target_reply, session)
            if ok:
                await session.commit()
        except Exception as e:
            logger.warning(f"campaign-thread: fetch failed for {campaign_name}: {e}")
            await session.rollback()

    activities = []

    # SmartLead email threads
    if target_reply.thread_fetched_at is not None:
        tm_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.reply_id == target_reply.id)
            .order_by(ThreadMessage.activity_at)
        )
        thread_msgs = tm_result.scalars().all()
        for tm in thread_msgs:
            activities.append({
                "direction": tm.direction,
                "content": tm.body or "",
                "timestamp": tm.activity_at.isoformat() + "Z" if tm.activity_at else "",
                "channel": tm.channel or "email",
                "campaign": campaign_name,
            })
        # Auto-dismiss if operator already replied (last message is outbound)
        if thread_msgs and thread_msgs[-1].direction == "outbound":
            if target_reply.approval_status in (None, "pending"):
                target_reply.approval_status = "dismissed"
                target_reply.approved_at = datetime.utcnow()
                session.add(target_reply)
                await session.commit()
                await session.refresh(target_reply)
                logger.info(f"[AUTO-DISMISS] Reply {target_reply.id} auto-dismissed — operator already replied via email")

    # LinkedIn activities from ContactActivity
    if target_reply.source == "getsales" or target_reply.channel == "linkedin":
        from app.models.contact import Contact, ContactActivity
        contact_result = await session.execute(
            select(Contact).where(
                and_(func.lower(Contact.email) == source_reply.lead_email.lower(), Contact.deleted_at.is_(None))
            )
        )
        contact = contact_result.scalar_one_or_none()
        if contact:
            ca_result = await session.execute(
                select(ContactActivity).where(
                    and_(ContactActivity.contact_id == contact.id, ContactActivity.channel == "linkedin")
                ).order_by(ContactActivity.activity_at)
            )
            for ca in ca_result.scalars().all():
                direction = ca.direction or ("outbound" if ca.activity_type in ("linkedin_sent",) else "inbound")
                activities.append({
                    "direction": direction,
                    "content": ca.body or ca.snippet or "",
                    "timestamp": ca.activity_at.isoformat() + "Z" if ca.activity_at else "",
                    "channel": "linkedin",
                    "campaign": campaign_name,
                })

    activities.sort(key=lambda a: a["timestamp"])
    return {"activities": activities}


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

    # Record operator action for learning system
    if approval_status == "dismissed":
        try:
            from app.services.learning_service import learning_service
            await learning_service.record_correction(
                db, reply, reply.draft_reply, reply.draft_subject,
                None, None, action_type="dismiss",
            )
            await db.commit()
        except Exception as _lrn_err:
            logger.warning(f"Learning correction recording failed (non-fatal): {_lrn_err}")

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

@router.post("/{reply_id}/send")
async def send_reply(
    reply_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Send an approved draft reply via SmartLead API.

    Fetches the message thread, threads the reply onto the last message,
    and queues it for delivery through SmartLead.
    """
    from app.services.smartlead_service import SmartleadService
    from app.models.contact import Contact

    result = await db.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    if not reply.draft_reply:
        raise HTTPException(status_code=400, detail="No draft reply to send")

    # Find the contact's SmartLead lead_id and campaign_id
    contact = None
    if reply.lead_email:
        from sqlalchemy import func
        contact_result = await db.execute(
            select(Contact).where(
                func.lower(Contact.email) == reply.lead_email.lower(),
                Contact.deleted_at.is_(None),
            )
        )
        contact = contact_result.scalar_one_or_none()

    if not contact or not contact.smartlead_id:
        raise HTTPException(status_code=400, detail="Contact not found or no SmartLead ID")

    # Determine campaign_id — use from reply or first SmartLead campaign on contact
    campaign_id = reply.campaign_id
    if not campaign_id and contact.campaigns:
        for c in parse_campaigns(contact.campaigns):
            if isinstance(c, dict) and c.get("source") == "smartlead" and c.get("id"):
                campaign_id = str(c["id"])
                break

    if not campaign_id:
        raise HTTPException(status_code=400, detail="No SmartLead campaign_id found")

    # Send via SmartLead
    sl = SmartleadService()
    send_result = await sl.send_reply(
        campaign_id=str(campaign_id),
        lead_id=contact.smartlead_id,
        email_body=f"<p>{reply.draft_reply}</p>",
    )

    if "error" in send_result:
        raise HTTPException(status_code=502, detail=send_result["error"])

    # Mark as approved + sent
    reply.approval_status = "approved"
    reply.approved_at = datetime.utcnow()
    await db.commit()

    # Record operator action for learning system (draft sent as-is)
    try:
        from app.services.learning_service import learning_service
        await learning_service.record_correction(
            db, reply, reply.draft_reply, reply.draft_subject,
            reply.draft_reply, reply.draft_subject, action_type="send",
        )
        await db.commit()
    except Exception as _lrn_err:
        logger.warning(f"Learning correction recording failed (non-fatal): {_lrn_err}")

    return {
        "status": "sent",
        "reply_id": reply_id,
        "lead_email": reply.lead_email,
        "campaign_id": campaign_id,
        "smartlead_response": send_result.get("message"),
    }


@router.post("/{reply_id}/regenerate-draft")
async def regenerate_draft(
    reply_id: int,
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
):
    """Re-classify and regenerate draft for a failed reply.

    If classification also failed, re-runs classification first.
    Looks up the project by campaign_name to get sender identity and prompt template.
    """
    from app.services.reply_processor import classify_reply, generate_draft_reply
    from app.models.contact import Project
    from sqlalchemy import text as sa_text

    result = await db.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    subject = reply.email_subject or ""
    body = reply.email_body or reply.reply_text or ""

    # Re-classify if classification failed
    classification_failed = bool(
        reply.classification_reasoning
        and ("Classification failed" in reply.classification_reasoning
             or "failed after" in reply.classification_reasoning)
    )
    category = reply.category or "other"
    classification_reasoning = reply.classification_reasoning

    if classification_failed:
        try:
            cls_result = await classify_reply(subject=subject, body=body)
            category = cls_result.get("category", "other")
            classification_reasoning = cls_result.get("reasoning", "")
            reply.category = category
            reply.category_confidence = cls_result.get("confidence")
            reply.classification_reasoning = classification_reasoning
        except Exception as e:
            logger.error(f"Re-classification failed for reply {reply_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Re-classification failed: {e}")

    # Look up project for sender identity + prompt template
    custom_reply_prompt = None
    sender_name = None
    sender_position = None
    sender_company = None

    if reply.campaign_name:
        try:
            project_result = await db.execute(
                select(Project).where(
                    and_(
                        Project.campaign_filters.isnot(None),
                        Project.deleted_at.is_(None),
                        sa_text(
                            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(projects.campaign_filters) AS cf "
                            "WHERE LOWER(cf) = LOWER(:cname))"
                        ),
                    )
                ).params(cname=reply.campaign_name).limit(1)
            )
            project = project_result.scalar()
            if project:
                sender_name = project.sender_name
                sender_position = project.sender_position
                sender_company = project.sender_company
                if project.reply_prompt_template_id:
                    template_result = await db.execute(
                        select(ReplyPromptTemplateModel).where(
                            ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                        )
                    )
                    template = template_result.scalar()
                    if template:
                        custom_reply_prompt = template.prompt_text
                # Load project knowledge to enrich the prompt
                try:
                    from app.models.project_knowledge import ProjectKnowledge
                    knowledge_result = await db.execute(
                        select(ProjectKnowledge).where(
                            ProjectKnowledge.project_id == project.id
                        )
                    )
                    knowledge_entries = knowledge_result.scalars().all()
                    if knowledge_entries:
                        from app.services.reply_processor import _format_knowledge_context
                        knowledge_context = _format_knowledge_context(knowledge_entries, category=category)
                        if custom_reply_prompt:
                            custom_reply_prompt += knowledge_context
                        else:
                            custom_reply_prompt = knowledge_context
                except Exception as ke:
                    logger.warning(f"Knowledge loading failed (non-fatal): {ke}")

                # Load reference examples from operator's past replies
                try:
                    from app.services.reply_processor import _load_reference_examples
                    ref_examples = await _load_reference_examples(
                        db, project.id, category=category
                    )
                    if ref_examples:
                        if custom_reply_prompt:
                            custom_reply_prompt += ref_examples
                        else:
                            custom_reply_prompt = ref_examples
                except Exception as ref_err:
                    logger.warning(f"Reference examples loading failed (non-fatal): {ref_err}")
        except Exception as e:
            logger.warning(f"Project lookup failed for regenerate (non-fatal): {e}")

    # Capture old draft before overwriting (for learning signal)
    _old_draft = reply.draft_reply
    _old_subject = reply.draft_subject

    # Generate draft — allow model override (e.g. "gpt-4o" for higher quality)
    # Validate model to prevent arbitrary model names
    allowed_models = {"gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gemini-2.5-pro", "gemini-2.5-flash"}
    draft_model = model if model in allowed_models else None
    try:
        draft = await generate_draft_reply(
            subject=subject,
            body=body,
            category=category,
            first_name=reply.lead_first_name or "",
            last_name=reply.lead_last_name or "",
            company=reply.lead_company or "",
            custom_prompt=custom_reply_prompt,
            sender_name=sender_name,
            sender_position=sender_position,
            sender_company=sender_company,
            model=draft_model,
        )
    except Exception as e:
        logger.error(f"Draft regeneration failed for reply {reply_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Draft generation failed: {e}")

    reply.draft_reply = draft.get("body", "")
    reply.draft_subject = draft.get("subject", reply.draft_subject)
    reply.draft_generated_at = datetime.utcnow()

    # Re-translate if the reply is in a foreign language
    if reply.detected_language and reply.detected_language not in ("en", "ru") and reply.draft_reply:
        from app.services.reply_processor import detect_and_translate
        draft_lang = await detect_and_translate(reply.draft_reply)
        if draft_lang.get("translation"):
            reply.translated_draft = draft_lang["translation"]

    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    # Record regeneration as learning signal (old draft was rejected)
    try:
        from app.services.learning_service import learning_service
        await learning_service.record_correction(
            db, reply, _old_draft, _old_subject,
            None, None, action_type="regenerate",
        )
        await db.commit()
    except Exception as _lrn_err:
        logger.warning(f"Learning correction recording failed (non-fatal): {_lrn_err}")

    return {
        "reply_id": reply.id,
        "draft_reply": reply.draft_reply,
        "draft_subject": reply.draft_subject,
        "draft_generated_at": _utc_iso(reply.draft_generated_at),
        "translated_draft": reply.translated_draft,
        "category": reply.category,
        "classification_reasoning": reply.classification_reasoning,
    }


class ApproveAndSendBody(BaseModel):
    """Optional body for approve-and-send to allow editing the draft before sending."""
    draft_reply: Optional[str] = None
    draft_subject: Optional[str] = None


@router.post("/{reply_id}/approve-and-send")
async def approve_and_send_reply(
    reply_id: int,
    test_mode: bool = Query(False, description="When true, sends to TEST_RECIPIENT_EMAIL instead of real lead"),
    body: Optional[ApproveAndSendBody] = None,
    db: AsyncSession = Depends(get_session),
):
    """One-click approve and send: validates draft, sends via SmartLead.

    Safety: pass ?test_mode=true to redirect the email to TEST_RECIPIENT_EMAIL
    (defaults to pn@getsally.io) so real leads are never affected during testing.

    Optionally pass { "draft_reply": "...", "draft_subject": "..." } in the body
    to override the AI-generated draft before sending.
    """
    import os
    from app.core.config import settings
    from app.services.smartlead_service import SmartleadService
    from app.models.contact import Contact
    from app.services.google_sheets_service import google_sheets_service

    TEST_RECIPIENT_EMAIL = os.environ.get("TEST_RECIPIENT_EMAIL", "pn@getsally.io")

    result = await db.execute(
        select(ProcessedReply).where(ProcessedReply.id == reply_id)
    )
    reply = result.scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    # Capture AI draft before any edits for learning system
    _original_ai_draft = reply.draft_reply
    _original_ai_subject = reply.draft_subject

    # If caller provided an edited draft, persist it first
    if body and body.draft_reply is not None:
        reply.draft_reply = body.draft_reply
    if body and body.draft_subject is not None:
        reply.draft_subject = body.draft_subject

    if not reply.draft_reply:
        raise HTTPException(status_code=400, detail="No draft reply to send")

    if reply.approval_status in ("approved", "approved_dry_run"):
        raise HTTPException(status_code=400, detail="Reply already approved")

    # --- LinkedIn replies: send via GetSales API ---
    if reply.channel == "linkedin" or reply.source == "getsales":
        reply.approved_at = datetime.utcnow()

        # Extract GetSales identifiers from raw webhook data
        raw = reply.raw_webhook_data or {}
        lead_uuid = raw.get("lead_uuid") or raw.get("lead", {}).get("uuid")
        sender_profile_uuid = raw.get("sender_profile_uuid")

        send_result = None
        send_error = None

        if lead_uuid and sender_profile_uuid and not test_mode:
            try:
                from app.services.crm_sync_service import GetSalesClient
                gs = GetSalesClient(settings.GETSALES_API_KEY)
                try:
                    send_result = await gs.send_linkedin_message(
                        sender_profile_uuid=sender_profile_uuid,
                        lead_uuid=lead_uuid,
                        text=reply.draft_reply,
                    )
                    logger.info(f"GetSales message sent for reply {reply_id}: {send_result.get('uuid', 'ok')}")
                finally:
                    await gs.close()
            except Exception as gs_err:
                send_error = str(gs_err)
                logger.error(f"GetSales send failed for reply {reply_id}: {gs_err}")

        reply.approval_status = "approved"

        # Look up Contact for outbound activity tracking
        contact = None
        try:
            from app.models.contact import Contact as _C, ContactActivity
            _cr = await db.execute(
                select(_C).where(
                    func.lower(_C.email) == reply.lead_email.lower(),
                    _C.deleted_at.is_(None),
                )
            )
            contact = _cr.scalar_one_or_none()
            if contact:
                outbound = ContactActivity(
                    contact_id=contact.id,
                    company_id=contact.company_id,
                    activity_type="linkedin_replied",
                    channel="linkedin",
                    direction="outbound",
                    source="getsales",
                    body=reply.draft_reply,
                    snippet=(reply.draft_reply or "")[:200],
                    extra_data={
                        "processed_reply_id": reply.id,
                        "approved_via": "approve-and-send",
                        "getsales_sent": send_result is not None,
                        "getsales_message_uuid": (send_result or {}).get("uuid"),
                    },
                    activity_at=datetime.utcnow(),
                )
                db.add(outbound)
        except Exception as act_err:
            logger.warning(f"Failed to create outbound activity for LinkedIn reply: {act_err}")

        db.add(reply)
        await db.commit()
        await db.refresh(reply)

        # Record operator correction for learning system + auto-trigger learning
        try:
            from app.services.learning_service import learning_service
            correction = await learning_service.record_correction(
                db, reply, _original_ai_draft, _original_ai_subject,
                reply.draft_reply, reply.draft_subject,
            )
            await db.commit()

            if correction and correction.was_edited and correction.project_id:
                try:
                    log_id = await learning_service.maybe_auto_trigger_learning(
                        db, correction.project_id,
                    )
                    if log_id:
                        await db.commit()
                        _project_id = correction.project_id
                        async def _run_auto_learning_li():
                            from app.db.database import async_session_maker
                            async with async_session_maker() as s:
                                try:
                                    await learning_service.run_learning_cycle(
                                        s, _project_id, trigger="auto_corrections", log_id=log_id,
                                    )
                                    await s.commit()
                                except Exception as e:
                                    logger.error(f"Auto-learning failed for project {_project_id}: {e}")
                        import asyncio
                        asyncio.ensure_future(_run_auto_learning_li())
                except Exception as _at_err:
                    logger.warning(f"Auto-trigger check failed (non-fatal): {_at_err}")
        except Exception as _lrn_err:
            logger.warning(f"Learning correction recording failed (non-fatal): {_lrn_err}")

        status_msg = "Sent via LinkedIn" if send_result else "Approved — copy draft to LinkedIn"
        if send_error:
            status_msg = f"Approved (send failed: {send_error[:100]})"

        return {
            "status": "approved",
            "channel": "linkedin",
            "reply_id": reply_id,
            "lead_email": reply.lead_email,
            "message": status_msg,
            "contact_id": contact.id if contact else None,
            "getsales_sent": send_result is not None,
            "send_error": send_error,
        }

    # --- Find contact and campaign ---
    contact = None
    if reply.lead_email:
        contact_result = await db.execute(
            select(Contact).where(
                func.lower(Contact.email) == reply.lead_email.lower(),
                Contact.deleted_at.is_(None),
            )
        )
        contact = contact_result.scalar_one_or_none()

    campaign_id = reply.campaign_id

    # Try to resolve campaign_id from contact if missing
    if not campaign_id and contact and contact.campaigns:
        for c in parse_campaigns(contact.campaigns):
            if isinstance(c, dict) and c.get("source") == "smartlead" and c.get("id"):
                campaign_id = str(c["id"])
                break

    if not campaign_id:
        raise HTTPException(status_code=400, detail="No SmartLead campaign_id found")

    # --- Determine lead_id to use ---
    # In test_mode we still need a real SmartLead lead_id so the API works,
    # but we prepend "[TEST for <real_email>]" to the body so it's obvious.
    lead_id = contact.smartlead_id if contact else None

    if test_mode:
        # Build a test-safe email body (clean prefix, no campaign IDs)
        body_prefix = (
            f"<p><strong>[TEST — original recipient: {reply.lead_email}]</strong></p><hr/>"
        )
        email_body = body_prefix + _text_to_html(reply.draft_reply)

        # If the lead has no SmartLead ID, we can't send via the thread API.
        # But we still mark it approved so the flow is testable.
        if not lead_id:
            reply.approval_status = "approved_dry_run"
            reply.approved_at = datetime.utcnow()
            db.add(reply)
            await db.commit()
            await db.refresh(reply)
            return {
                "status": "approved_dry_run",
                "dry_run": True,
                "reply_id": reply_id,
                "test_mode": True,
                "message": f"No SmartLead lead_id — marked approved (dry run). Would send to {TEST_RECIPIENT_EMAIL}.",
                "contact_id": contact.id if contact else None,
            }
    else:
        email_body = _text_to_html(reply.draft_reply)
        if not contact or not lead_id:
            raise HTTPException(status_code=400, detail="Contact not found or no SmartLead ID")

    # --- Send via SmartLead ---
    sl = SmartleadService()
    send_result = await sl.send_reply(
        campaign_id=str(campaign_id),
        lead_id=lead_id,
        email_body=email_body,
    )

    if "error" in send_result:
        if test_mode:
            # In test mode, gracefully fall back to dry_run instead of 502
            logger.warning(f"test_mode send_reply failed ({send_result['error']}), falling back to approved_dry_run")
            reply.approval_status = "approved_dry_run"
            reply.approved_at = datetime.utcnow()
            db.add(reply)
            await db.commit()
            await db.refresh(reply)
            return {
                "status": "approved_dry_run",
                "dry_run": True,
                "reply_id": reply_id,
                "test_mode": True,
                "lead_email": reply.lead_email,
                "sent_to": TEST_RECIPIENT_EMAIL,
                "message": f"SmartLead send failed ({send_result['error']}) — marked approved (dry run).",
                "contact_id": contact.id if contact else None,
            }
        raise HTTPException(status_code=502, detail=send_result["error"])

    status = "approved_test" if test_mode else "approved"
    reply.approval_status = status
    reply.approved_at = datetime.utcnow()
    db.add(reply)

    # Create outbound ContactActivity so sent message appears immediately in conversation
    try:
        from app.models.contact import ContactActivity
        if contact:
            outbound = ContactActivity(
                contact_id=contact.id,
                company_id=contact.company_id,
                activity_type='email_sent',
                channel='email',
                direction='outbound',
                source='app_send',
                subject=reply.draft_subject or reply.email_subject,
                body=reply.draft_reply,
                snippet=(reply.draft_reply or '')[:200],
                extra_data={
                    'processed_reply_id': reply.id,
                    'campaign_id': str(campaign_id),
                    'campaign_name': reply.campaign_name,
                    'approved_via': 'approve-and-send',
                },
                activity_at=datetime.utcnow(),
            )
            db.add(outbound)
    except Exception as act_err:
        logger.warning(f"Failed to create outbound activity for email reply: {act_err}")

    await db.commit()
    await db.refresh(reply)

    # Record operator correction for learning system + auto-trigger learning
    try:
        from app.services.learning_service import learning_service
        correction = await learning_service.record_correction(
            db, reply, _original_ai_draft, _original_ai_subject,
            reply.draft_reply, reply.draft_subject,
        )
        await db.commit()

        # Auto-trigger learning if enough edited corrections accumulated
        if correction and correction.was_edited and correction.project_id:
            try:
                log_id = await learning_service.maybe_auto_trigger_learning(
                    db, correction.project_id,
                )
                if log_id:
                    await db.commit()
                    _project_id = correction.project_id
                    async def _run_auto_learning():
                        from app.db.database import async_session_maker
                        async with async_session_maker() as s:
                            try:
                                await learning_service.run_learning_cycle(
                                    s, _project_id, trigger="auto_corrections", log_id=log_id,
                                )
                                await s.commit()
                            except Exception as e:
                                logger.error(f"Auto-learning failed for project {_project_id}: {e}")
                                try:
                                    from app.models.learning import LearningLog as _LL
                                    r = await s.execute(select(_LL).where(_LL.id == log_id))
                                    ll = r.scalar_one_or_none()
                                    if ll:
                                        ll.status = "failed"
                                        ll.error_message = str(e)[:2000]
                                        await s.commit()
                                except Exception:
                                    pass
                    import asyncio
                    asyncio.ensure_future(_run_auto_learning())
            except Exception as _at_err:
                logger.warning(f"Auto-trigger check failed (non-fatal): {_at_err}")
    except Exception as _lrn_err:
        logger.warning(f"Learning correction recording failed (non-fatal): {_lrn_err}")

    # Sync to Google Sheets
    await _sync_approval_to_sheet(db, reply, status, google_sheets_service)

    return {
        "status": status,
        "dry_run": False,
        "test_mode": test_mode,
        "reply_id": reply_id,
        "lead_email": reply.lead_email,
        "sent_to": TEST_RECIPIENT_EMAIL if test_mode else reply.lead_email,
        "campaign_id": campaign_id,
        "smartlead_response": send_result.get("message"),
        "contact_id": contact.id if contact else None,
    }


async def _sync_approval_to_sheet(db, reply, status, google_sheets_service):
    """Sync approval status to Google Sheets if configured."""
    try:
        if reply.automation_id and reply.google_sheet_row:
            auto_result = await db.execute(
                select(ReplyAutomation).where(ReplyAutomation.id == reply.automation_id)
            )
            automation = auto_result.scalar_one_or_none()
            if automation and automation.google_sheet_id:
                google_sheets_service.update_reply_status(
                    automation.google_sheet_id,
                    reply.google_sheet_row,
                    status,
                    approved_by='',
                    approved_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                )
    except Exception as e:
        logger.warning(f"Failed to sync approval to Google Sheets: {e}")


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
    campaign_name: str = Query("", description="Campaign name (auto-resolved from Smartlead if empty)"),
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

    import os
    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key

    # Auto-resolve campaign name and lead ID from Smartlead
    resolved_name = campaign_name
    sl_lead_id = None
    sl_lead_map_id = None

    if api_key:
        # Resolve campaign name
        if not resolved_name:
            try:
                resp = await smartlead_request(
                    "GET",
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}",
                    params={"api_key": api_key},
                    timeout=15.0,
                )
                data = resp.json()
                resolved_name = data.get("name", "")
            except Exception:
                pass

        # Look up lead_id by email in campaign leads
        try:
            resp = await smartlead_request(
                "GET",
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                params={"api_key": api_key, "limit": 100, "offset": 0},
                timeout=30.0,
            )
            leads_resp = resp.json()
            for entry in (leads_resp.get("data") or []):
                lead_obj = entry.get("lead", {}) if isinstance(entry, dict) else {}
                if lead_obj.get("email", "").lower() == lead_email.lower():
                    sl_lead_id = str(lead_obj.get("id") or "")
                    sl_lead_map_id = str(entry.get("campaign_lead_map_id") or "")
                    break
        except Exception:
            pass

    inbox_link = f"https://app.smartlead.ai/app/master-inbox?action=INBOX&leadMap={sl_lead_map_id}" if sl_lead_map_id else None

    # Create test payload matching Smartlead format
    test_payload = {
        "event_type": "EMAIL_REPLY",
        "campaign_id": campaign_id,
        "campaign_name": resolved_name,
        "sl_lead_email": lead_email,
        "sl_email_lead_id": sl_lead_id,
        "sl_email_lead_map_id": sl_lead_map_id,
        "ui_master_inbox_link": inbox_link,
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
    import os

    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key

    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead API key not configured")

    response = await smartlead_request(
        "GET",
        "https://server.smartlead.ai/api/v1/email-accounts",
        params={"api_key": api_key, "limit": 50},
        timeout=60.0,
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
    import os
    import uuid

    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")

    test_id = uuid.uuid4().hex[:8]
    campaign_name = f"Auto-Reply Test {test_id}"

    # 0. Auto-select email account if not provided
    if not email_account_id:
        acct_resp = await smartlead_request(
            "GET",
            "https://server.smartlead.ai/api/v1/email-accounts",
            params={"api_key": api_key},
            timeout=30.0,
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
    resp = await smartlead_request(
        "POST",
        "https://server.smartlead.ai/api/v1/campaigns/create",
        params={"api_key": api_key},
        json={"name": campaign_name},
        timeout=30.0,
    )
    campaign_data = resp.json()

    if "id" not in campaign_data:
        return {"success": False, "error": f"Failed to create campaign: {campaign_data}"}

    campaign_id = campaign_data["id"]

    # 2. Add email sequence
    await smartlead_request(
        "POST",
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
        }]},
        timeout=30.0,
    )

    # 3. Add sender account (required for launch)
    await smartlead_request(
        "POST",
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts",
        params={"api_key": api_key},
        json={"email_account_ids": [email_account_id]},
        timeout=30.0,
    )

    # 4. Configure schedule for sending (days 0=Sun to 6=Sat)
    await smartlead_request(
        "POST",
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/schedule",
        params={"api_key": api_key},
        json={
            "timezone": "UTC",
            "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
            "start_hour": "00:00",
            "end_hour": "23:59",
            "min_time_btw_emails": 3,
            "max_new_leads_per_day": 100
        },
        timeout=30.0,
    )

    # 5. Add user as lead
    parts = user_name.split() if user_name else ["Test", "User"]
    await smartlead_request(
        "POST",
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
        params={"api_key": api_key},
        json={"lead_list": [{
            "email": user_email,
            "first_name": parts[0],
            "last_name": parts[-1] if len(parts) > 1 else "User",
            "company_name": "Test Company"
        }]},
        timeout=30.0,
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
    import os

    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        return {"campaigns": []}

    resp = await smartlead_request(
        "GET",
        "https://server.smartlead.ai/api/v1/campaigns",
        params={"api_key": api_key, "limit": 100},
        timeout=60.0,
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
    import os

    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")

    resp = await smartlead_request(
        "GET",
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}",
        params={"api_key": api_key},
        timeout=60.0,
    )
    data = resp.json()

    return {
        "campaign_id": campaign_id,
        "name": data.get("name"),
        "status": data.get("status"),  # DRAFT, ACTIVE, PAUSED, COMPLETED
        "created_at": data.get("created_at")
    }


@router.post("/campaign/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause a Smartlead campaign."""
    import os

    api_key = os.environ.get('SMARTLEAD_API_KEY') or smartlead_service.api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Smartlead not configured")

    resp = await smartlead_request(
        "POST",
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status",
        params={"api_key": api_key},
        json={"status": "PAUSE"},
        timeout=60.0,
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
        try:
            lead_resp = await smartlead_request(
                "GET",
                'https://server.smartlead.ai/api/v1/leads',
                params={'api_key': api_key, 'email': q},
                timeout=10.0,
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
    import os
    import re

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
                "timestamp": _utc_iso(r.received_at),
                "category": r.category
            })
            if r.draft_reply:
                messages.append({
                    "type": "SENT",
                    "body": r.draft_reply,
                    "subject": f"Re: {r.email_subject}" if r.email_subject else "Draft Reply",
                    "timestamp": _utc_iso(r.received_at),
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
        lead_resp = await smartlead_request(
            "GET",
            "https://server.smartlead.ai/api/v1/leads",
            params={"api_key": api_key, "email": lead_email},
            timeout=30.0,
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

            hist_resp = await smartlead_request(
                "GET",
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                params={"api_key": api_key},
                timeout=30.0,
            )
            from app.services.smartlead_service import parse_history_response as _parse_hist

            for msg in _parse_hist(hist_resp.json()):
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


@router.get("/smartlead/rate-limit-stats")
async def get_rate_limit_stats():
    """Get SmartLead API rate limiter stats."""
    from app.services.smartlead_service import _sl_429_count, _sl_total_count, _sl_timestamps
    return {
        "total_requests": _sl_total_count,
        "429_count": _sl_429_count,
        "window_size": len(_sl_timestamps),
    }


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

# ============= Automation Controls (DISABLED) =============
# Same reason as above: per-automation controls are redundant.

@router.post("/automations/{automation_id}/pause")
async def pause_automation(
    automation_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Pause an automation (sets active=False)."""
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    _check_automations_disabled()
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
    _check_automations_disabled()
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
        import os
        api_key = os.environ.get("SMARTLEAD_API_KEY")
        if api_key:
            for campaign_id in (automation.campaign_ids or []):
                try:
                    resp = await smartlead_request(
                        "GET",
                        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                        params={"api_key": api_key, "limit": limit * 10},
                        timeout=60.0,
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
                            "status": ""
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


# ============= Rizzult Comparison =============

RIZZULT_REFERENCE_SHEET_ID = "1Zg-ER4ZlhlHuLFWya_ROi5VuMJ6ld_ERh3ONcB2sJ3s"
RIZZULT_REFERENCE_GID = "1599376288"


@router.get("/rizzult-comparison")
async def rizzult_comparison(
    session: AsyncSession = Depends(get_session),
):
    """Compare our collected replies with n8n's reference Google Sheet.

    Reads the Rizzult reference sheet (gid 1599376288), queries local
    ProcessedReply records, and returns:
    - missed: replies in n8n sheet but NOT in our DB
    - extra: replies in our DB but NOT in n8n sheet
    - matched: replies present in both
    """
    from app.services.google_sheets_service import google_sheets_service

    # Read reference sheet
    # The gid maps to a tab; we need to figure out the tab name.
    # Try reading metadata first to resolve gid -> tab name.
    tab_name = None
    try:
        if google_sheets_service._initialize():
            meta = google_sheets_service.sheets_service.spreadsheets().get(
                spreadsheetId=RIZZULT_REFERENCE_SHEET_ID
            ).execute()
            for sheet in meta.get("sheets", []):
                props = sheet.get("properties", {})
                if str(props.get("sheetId")) == RIZZULT_REFERENCE_GID:
                    tab_name = props.get("title")
                    break
    except Exception as e:
        logger.warning(f"Could not resolve gid to tab name: {e}")

    if not tab_name:
        tab_name = "Sheet1"  # fallback

    sheet_rows = google_sheets_service.read_sheet_data(
        RIZZULT_REFERENCE_SHEET_ID, tab_name
    )

    if not sheet_rows:
        return {
            "error": "Could not read reference sheet or sheet is empty",
            "sheet_id": RIZZULT_REFERENCE_SHEET_ID,
            "tab": tab_name,
        }

    # Build set of (email, campaign_id) from n8n sheet
    # Headers are lowercased by read_sheet_data; look for common column names
    n8n_replies = {}
    for row in sheet_rows:
        email = (
            row.get("target_lead_email")
            or row.get("lead_email")
            or row.get("email")
            or ""
        ).strip().lower()
        cid = (
            row.get("campaign_id")
            or row.get("campaignid")
            or ""
        ).strip()
        if email:
            key = (email, cid)
            n8n_replies[key] = {
                "email": email,
                "campaign_id": cid,
                "campaign": row.get("campaign", ""),
                "text": (row.get("text") or "")[:200],
                "time": row.get("time", ""),
                "category": row.get("category", ""),
                "source": row.get("source", ""),
                "name": f"{row.get('first name', '')} {row.get('last name', '')}".strip(),
                "company": row.get("company ", row.get("company", "")),
            }

    # Query local ProcessedReply records
    result = await session.execute(select(ProcessedReply))
    local_replies_list = result.scalars().all()

    local_replies = {}
    for r in local_replies_list:
        email = (r.lead_email or "").strip().lower()
        cid = (r.campaign_id or "").strip()
        key = (email, cid)
        local_replies[key] = {
            "id": r.id,
            "email": email,
            "campaign_id": cid,
            "campaign_name": r.campaign_name,
            "category": r.category,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "body_preview": (r.email_body or "")[:200],
        }

    n8n_keys = set(n8n_replies.keys())
    local_keys = set(local_replies.keys())

    missed_keys = n8n_keys - local_keys
    extra_keys = local_keys - n8n_keys
    matched_keys = n8n_keys & local_keys

    # Break down by source (Email vs LinkedIn)
    missed_by_source = {"Email": 0, "LinkedIn": 0, "other": 0}
    for k in missed_keys:
        source = n8n_replies[k].get("source", "")
        if "LinkedIn" in source:
            missed_by_source["LinkedIn"] += 1
        elif "Email" in source or not source:
            missed_by_source["Email"] += 1
        else:
            missed_by_source["other"] += 1

    return {
        "summary": {
            "n8n_total": len(n8n_keys),
            "local_total": len(local_keys),
            "matched": len(matched_keys),
            "missed": len(missed_keys),
            "extra": len(extra_keys),
            "missed_by_source": missed_by_source,
            "coverage_pct": round(len(matched_keys) / len(n8n_keys) * 100, 1) if n8n_keys else 0,
        },
        "missed": [n8n_replies[k] for k in sorted(missed_keys)],
        "extra": [local_replies[k] for k in sorted(extra_keys)[:50]],
        "matched": [
            {"n8n": n8n_replies[k], "local": local_replies[k]}
            for k in sorted(matched_keys)[:50]
        ],
    }


# ============= Smartlead Outbound Sync =============


async def _classify_reply_needs_action(reply_text: str) -> str:
    """Use GPT-4o-mini to classify whether an inbound reply needs operator action.

    Returns one of: needs_reply, ooo, unsubscribe, bounce, not_interested, already_handled
    """
    from app.services.openai_service import openai_service

    if not openai_service.is_connected():
        # Fallback: assume needs reply if GPT unavailable
        return "needs_reply"

    prompt = (
        "Classify this email reply into exactly one category:\n"
        "- needs_reply: Real human response requiring operator attention "
        "(question, interest, scheduling, objection, referral)\n"
        "- ooo: Out-of-office / vacation auto-reply\n"
        "- unsubscribe: Wants to be removed from mailing list\n"
        "- bounce: Delivery failure / mailbox full / invalid address\n"
        "- not_interested: Clear rejection, no further action needed\n"
        "- already_handled: Generic acknowledgment ('thanks', 'ok', 'received') "
        "that doesn't need a response\n\n"
        f'Reply text: """{reply_text[:2000]}"""\n\n'
        "Return ONLY the category name, nothing else."
    )

    try:
        result = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=20,
        )
        category = (result or "").strip().lower().replace('"', '').replace("'", "")
        valid = {"needs_reply", "ooo", "unsubscribe", "bounce", "not_interested", "already_handled"}
        return category if category in valid else "needs_reply"
    except Exception as e:
        logger.warning(f"GPT classify failed, defaulting to needs_reply: {e}")
        return "needs_reply"


@router.post("/sync-outbound-status")
async def sync_outbound_status(
    project_id: Optional[int] = Query(None, description="Limit to a project's campaigns"),
    days_back: int = Query(2, ge=1, le=30, description="Only check replies from last N days"),
    limit: int = Query(50, ge=1, le=200, description="Max replies to check"),
    dry_run: bool = Query(False, description="Preview without updating"),
    auto_dismiss: bool = Query(False, description="Auto-dismiss OOO/unsubscribe/bounce via GPT"),
    db: AsyncSession = Depends(get_session),
):
    """Check Smartlead conversations for recent pending replies to detect operator replies.

    Resolves lead_id from DB only (zero API calls for resolution).
    Fetches message-history only for recent pending leads (~5-10 API calls).
    """
    import asyncio
    from app.services.smartlead_service import SmartleadService
    from app.models.contact import Contact

    sl = SmartleadService()
    if not sl._api_key:
        raise HTTPException(status_code=500, detail="SMARTLEAD_API_KEY not configured")

    # Only check recent replies (last N days)
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    # Build query for pending replies
    query = select(ProcessedReply).where(
        and_(
            or_(
                ProcessedReply.approval_status == None,
                ProcessedReply.approval_status == "pending",
            ),
            ProcessedReply.received_at >= cutoff,
        )
    ).order_by(ProcessedReply.received_at.desc())

    # Filter by project campaigns if specified
    if project_id:
        from app.models.contact import Project
        proj_result = await db.execute(
            select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        )
        project = proj_result.scalar_one_or_none()
        if project and project.campaign_filters:
            camp_names = [c for c in project.campaign_filters if isinstance(c, str)]
            if camp_names:
                query = query.where(ProcessedReply.campaign_name.in_(camp_names))

    query = query.limit(limit)
    result = await db.execute(query)
    pending_replies = result.scalars().all()

    if not pending_replies:
        return {"checked": 0, "already_replied": 0, "still_pending": 0,
                "auto_dismissed": 0, "skipped_no_lead_id": 0, "errors": 0}

    # Deduplicate by (campaign_id, lead_email)
    seen = set()
    to_check = []
    reply_groups = {}
    for r in pending_replies:
        email_lower = (r.lead_email or "").lower()
        group_key = (r.campaign_id, email_lower)
        reply_groups.setdefault(group_key, []).append(r)
        if group_key not in seen and r.campaign_id and r.lead_email:
            seen.add(group_key)
            to_check.append(r)

    # Resolve lead_id from DB + fetch message-history
    already_replied = []
    still_pending_list = []
    auto_dismissed = []
    skipped_no_lead_id = []
    errors = []
    delay = 1.5

    for r in to_check:
        email_lower = (r.lead_email or "").lower()

        # Resolve lead_id from local data only — zero Smartlead API calls
        lead_id = None

        # 1. Contact.smartlead_id from DB
        contact_result = await db.execute(
            select(Contact.id, Contact.smartlead_id).where(
                func.lower(Contact.email) == email_lower,
                Contact.deleted_at.is_(None),
            )
        )
        row = contact_result.first()
        if row and row[1]:
            lead_id = str(row[1])

        # 2. Webhook raw data (sl_email_lead_id is the primary field Smartlead sends)
        if not lead_id and r.raw_webhook_data and isinstance(r.raw_webhook_data, dict):
            lead_id = str(
                r.raw_webhook_data.get("sl_email_lead_id")
                or r.raw_webhook_data.get("sl_lead_id")
                or r.raw_webhook_data.get("lead_id")
                or ""
            ).strip() or None

        # Backfill Contact.smartlead_id if null
        if lead_id and row and not row[1]:
            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(Contact).where(Contact.id == row[0]).values(smartlead_id=lead_id)
            )

        if not lead_id:
            skipped_no_lead_id.append({
                "reply_id": r.id, "email": r.lead_email,
                "campaign": r.campaign_name,
            })
            continue

        cid = r.campaign_id

        try:
            await asyncio.sleep(delay)
            resp = await smartlead_request(
                "GET",
                f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads/{lead_id}/message-history",
                params={"api_key": sl._api_key},
                timeout=30.0,
            )

            if resp.status_code == 429:
                delay = min(delay * 2, 15.0)
                errors.append({"reply_id": r.id, "error": "429 after retry", "email": r.lead_email})
                continue

            if resp.status_code != 200:
                errors.append({"reply_id": r.id, "error": f"API {resp.status_code}"})
                continue

            delay = max(delay * 0.9, 1.0)

            from app.services.smartlead_service import parse_history_response as _ph
            history = _ph(resp.json())
            if not history:
                still_pending_list.append({"reply_id": r.id, "email": r.lead_email,
                                           "campaign": r.campaign_name})
                continue

            last_msg = history[-1]
            msg_type = last_msg.get("type", "")

            if msg_type != "REPLY":
                already_replied.append({
                    "reply_id": r.id,
                    "lead_email": r.lead_email,
                    "campaign": r.campaign_name,
                    "last_msg_type": msg_type,
                    "messages_total": len(history),
                })
            else:
                if auto_dismiss:
                    reply_text = last_msg.get("email_body", "") or ""
                    classification = await _classify_reply_needs_action(reply_text)
                    if classification != "needs_reply":
                        auto_dismissed.append({
                            "reply_id": r.id, "lead_email": r.lead_email,
                            "campaign": r.campaign_name, "reason": classification,
                        })
                        if not dry_run:
                            group_key = (r.campaign_id, email_lower)
                            for gr in reply_groups.get(group_key, []):
                                if gr.approval_status in (None, "pending"):
                                    gr.approval_status = "dismissed"
                                    gr.approved_at = datetime.utcnow()
                                    db.add(gr)
                    else:
                        still_pending_list.append({
                            "reply_id": r.id, "email": r.lead_email,
                            "campaign": r.campaign_name,
                        })
                else:
                    still_pending_list.append({
                        "reply_id": r.id, "email": r.lead_email,
                        "campaign": r.campaign_name,
                    })

        except Exception as e:
            logger.error(f"sync: error checking {r.lead_email}: {e}")
            errors.append({"reply_id": r.id, "error": str(e)})

    if not dry_run:
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"sync-outbound commit failed: {e}")
            await db.rollback()

    return {
        "checked": len(to_check),
        "already_replied": len(already_replied),
        "still_pending": len(still_pending_list),
        "auto_dismissed": len(auto_dismissed),
        "skipped_no_lead_id": len(skipped_no_lead_id),
        "errors": len(errors),
        "dry_run": dry_run,
        "days_back": days_back,
        "details": {
            "already_replied": already_replied[:20],
            "still_pending": still_pending_list[:20],
            "auto_dismissed": auto_dismissed[:20],
            "skipped": skipped_no_lead_id[:10],
            "errors": errors[:10],
        },
    }


@router.get("/campaign/{campaign_id}/analytics-summary")
async def campaign_analytics_summary(campaign_id: str):
    """Return campaign reply stats matching Smartlead analytics page.

    Uses the bulk statistics endpoint (GET /campaigns/{id}/statistics)
    to compute: unique replied, unique replied w/OOO, and breakdown by category.
    """
    from app.services.smartlead_service import SmartleadService

    sl = SmartleadService()
    if not sl._api_key:
        raise HTTPException(status_code=500, detail="SMARTLEAD_API_KEY not configured")

    replied_leads = await sl.get_all_campaign_replied_leads(campaign_id)
    total_replied = len(replied_leads)
    categories: dict[str, int] = {}
    for lead in replied_leads:
        cat = lead.get("lead_category") or "uncategorized"
        categories[cat] = categories.get(cat, 0) + 1

    ooo_count = categories.get("Out Of Office", 0)
    return {
        "campaign_id": campaign_id,
        "unique_replied": total_replied - ooo_count,
        "unique_replied_with_ooo": total_replied,
        "unique_positive": categories.get("Interested", 0),
        "by_category": categories,
    }


# ============= Telegram Bot Endpoints =============


@router.get("/telegram/project-status")
async def telegram_project_status(
    project_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Return all Telegram subscribers for a project.

    Used by the frontend to poll after the operator clicks 'Connect Telegram'
    and to show the connected accounts list.
    """
    from app.models.contact import Project
    from app.models.reply import TelegramSubscription

    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    subs_result = await db.execute(
        select(TelegramSubscription).where(
            TelegramSubscription.project_id == project_id
        ).order_by(TelegramSubscription.subscribed_at)
    )
    subs = subs_result.scalars().all()

    return {
        "connected": len(subs) > 0,
        "first_name": subs[0].first_name if subs else project.telegram_first_name,
        "username": subs[0].username if subs else project.telegram_username,
        "subscribers": [
            {
                "id": s.id,
                "chat_id": s.chat_id,
                "username": s.username,
                "first_name": s.first_name,
                "subscribed_at": s.subscribed_at.isoformat() if s.subscribed_at else None,
            }
            for s in subs
        ],
    }


@router.post("/telegram/disconnect")
async def telegram_disconnect(
    project_id: int = Query(...),
    chat_id: str = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Disconnect a specific subscriber or all from a project."""
    from app.models.contact import Project
    from app.models.reply import TelegramSubscription

    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if chat_id:
        await db.execute(
            TelegramSubscription.__table__.delete().where(
                and_(
                    TelegramSubscription.project_id == project_id,
                    TelegramSubscription.chat_id == chat_id,
                )
            )
        )
    else:
        await db.execute(
            TelegramSubscription.__table__.delete().where(
                TelegramSubscription.project_id == project_id
            )
        )

    remaining = await db.execute(
        select(func.count(TelegramSubscription.id)).where(
            TelegramSubscription.project_id == project_id
        )
    )
    if remaining.scalar() == 0:
        project.telegram_chat_id = None
        project.telegram_username = None
        project.telegram_first_name = None

    await db.commit()

    return {"ok": True}


@router.post("/telegram/webhook")
async def telegram_webhook(
    request_body: dict,
    db: AsyncSession = Depends(get_session),
):
    """Handle Telegram bot webhook updates (fallback if HTTPS is available).

    Supports deep links: /start project_22 -> auto-links chat to project 22.
    The primary handler is the polling loop in crm_scheduler.py.
    """
    from app.models.contact import Project
    from app.models.reply import TelegramRegistration
    from app.services.notification_service import send_telegram_notification

    message = request_body.get("message", {})
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    from_user = message.get("from", {})
    text = (message.get("text") or "").strip()
    chat_id = str(chat.get("id", ""))
    username = (from_user.get("username") or "").lower().strip()
    first_name = from_user.get("first_name", "")

    if not chat_id:
        return {"ok": True}

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""

        # Deep link: /start project_<id>
        if payload.startswith("project_"):
            try:
                project_id = int(payload.replace("project_", ""))
            except ValueError:
                return {"ok": True}

            result = await db.execute(
                select(Project).where(
                    and_(Project.id == project_id, Project.deleted_at.is_(None))
                )
            )
            project = result.scalar_one_or_none()
            if project:
                project.telegram_chat_id = chat_id
                project.telegram_first_name = first_name
                if username:
                    project.telegram_username = username
                await db.commit()

                await send_telegram_notification(
                    f"Connected to <b>{project.name}</b>!\n\n"
                    f"You'll receive notifications for new replies in this project.",
                    chat_id=chat_id, parse_mode="HTML",
                )
            return {"ok": True}

        # Plain /start
        if username:
            existing = await db.execute(
                select(TelegramRegistration).where(
                    TelegramRegistration.telegram_username == username
                )
            )
            reg = existing.scalar_one_or_none()
            if reg:
                reg.telegram_chat_id = chat_id
                reg.telegram_first_name = first_name
                reg.updated_at = datetime.utcnow()
            else:
                reg = TelegramRegistration(
                    telegram_username=username,
                    telegram_chat_id=chat_id,
                    telegram_first_name=first_name,
                )
                db.add(reg)
            await db.commit()

        await send_telegram_notification(
            f"Hi {first_name}! To connect to a project, "
            f"use the <b>Connect Telegram</b> button in the app.",
            chat_id=chat_id, parse_mode="HTML",
        )
        return {"ok": True}

    return {"ok": True}
