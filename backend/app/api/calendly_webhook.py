"""Calendly webhook endpoint — receives booking events and creates Meeting records.

Webhook URL to configure in Calendly:
  POST https://your-domain.com/api/webhooks/calendly

Events handled:
  - invitee.created — new booking → create Meeting + TG notification
  - invitee.canceled — cancellation → update Meeting status
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import async_session_maker
from app.models.meeting import Meeting
from app.models.contact import Project, Contact
from app.services.notification_service import send_telegram_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _build_project_dict(session, project) -> dict:
    """Build project info dict with telegram subscribers."""
    from app.models.reply import TelegramSubscription

    subs_result = await session.execute(
        select(TelegramSubscription).where(
            TelegramSubscription.project_id == project.id
        )
    )
    subscribers = [s.chat_id for s in subs_result.scalars().all() if s.chat_id]

    return {
        "id": project.id,
        "name": project.name,
        "company_id": project.company_id,
        "telegram_chat_id": project.telegram_chat_id,
        "telegram_subscribers": subscribers,
    }


async def find_project_by_invitee_email(email: str) -> Optional[dict]:
    """Find project by looking up invitee email in contacts table (cross-project).

    Priority: contact with most recent conversation activity wins.
    Returns dict with project info + pre-found contact_id, or None.
    """
    if not email:
        return None

    async with async_session_maker() as session:
        result = await session.execute(
            select(Contact).where(
                Contact.email == email.lower(),
                Contact.deleted_at.is_(None)
            )
        )
        contacts = result.scalars().all()

        if not contacts:
            return None

        # Pick best contact: most recent activity
        def _activity_key(c):
            return c.last_reply_at or c.updated_at or c.created_at or datetime.min

        winner = max(contacts, key=_activity_key)

        # Load project
        project = await session.get(Project, winner.project_id)
        if not project or project.deleted_at:
            return None

        proj_dict = await _build_project_dict(session, project)
        proj_dict["contact_id"] = winner.id
        logger.info(
            f"[CALENDLY] Matched {email} to project '{project.name}' "
            f"(contact {winner.id}) via contact lookup"
        )
        return proj_dict


async def find_project_by_calendly_user(host_email: str) -> Optional[dict]:
    """Find project that has this Calendly user in calendly_config.members.

    Returns dict with project info including telegram_subscribers or None.
    Fallback when invitee email is not found in contacts.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Project).where(
                Project.calendly_config.isnot(None),
                Project.deleted_at.is_(None)
            )
        )
        projects = result.scalars().all()

        for project in projects:
            config = project.calendly_config or {}
            members = config.get("members", [])
            for member in members:
                # Check if host email matches member's email or ID
                member_id = member.get("id", "").lower()
                if host_email.lower() in member_id or member_id in host_email.lower():
                    return await _build_project_dict(session, project)

        # Fallback: return first project with calendly_config
        for project in projects:
            logger.warning(
                f"[CALENDLY] No member match for host {host_email}, "
                f"falling back to project '{project.name}'"
            )
            return await _build_project_dict(session, project)

    return None


async def find_contact_with_history(email: str, project_id: int) -> Optional[dict]:
    """Find contact by email and enrich with CRM data.

    Returns dict with contact info + last reply + message count, or None.
    """
    if not email:
        return None

    from app.models.reply import ProcessedReply
    from sqlalchemy import func, desc

    async with async_session_maker() as session:
        # Find contact
        result = await session.execute(
            select(Contact).where(
                Contact.email == email.lower(),
                Contact.project_id == project_id,
                Contact.deleted_at.is_(None)
            ).limit(1)
        )
        contact = result.scalar()

        if not contact:
            return None

        # Get last reply from this contact
        reply_result = await session.execute(
            select(ProcessedReply)
            .where(ProcessedReply.lead_email == email.lower())
            .order_by(desc(ProcessedReply.received_at))
            .limit(1)
        )
        last_reply = reply_result.scalar()

        # Count total messages
        count_result = await session.execute(
            select(func.count(ProcessedReply.id))
            .where(ProcessedReply.lead_email == email.lower())
        )
        message_count = count_result.scalar() or 0

        # Get campaign name from platform_state or smartlead_raw
        campaign_name = None
        if contact.platform_state:
            sl_state = contact.platform_state.get("smartlead", {})
            campaigns = sl_state.get("campaigns", [])
            if campaigns:
                campaign_name = campaigns[0] if isinstance(campaigns[0], str) else campaigns[0].get("name")

        return {
            "id": contact.id,
            "company_name": contact.company_name,
            "job_title": contact.job_title,
            "segment": contact.segment,
            "source": contact.source,  # email, linkedin, telegram
            "status": contact.status,
            "campaign_name": campaign_name,
            "linkedin_url": contact.linkedin_url,
            "last_reply_text": last_reply.reply_text[:150] + "..." if last_reply and last_reply.reply_text and len(last_reply.reply_text) > 150 else (last_reply.reply_text if last_reply else None),
            "last_reply_at": last_reply.received_at if last_reply else None,
            "message_count": message_count,
        }


FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.ru",
    "icloud.com", "yandex.ru", "protonmail.com", "live.com", "me.com",
    "aol.com", "zoho.com", "inbox.ru", "bk.ru", "list.ru", "yandex.com",
    "rambler.ru", "ukr.net", "gmx.com", "fastmail.com",
}


async def find_similar_contacts(email: str, name: str) -> list[dict]:
    """Find possible CRM matches for an unknown Calendly invitee.

    Strategy (in priority order):
      1. Same corporate email domain → most likely the same company,
         different person who forwarded the Calendly link internally
      2. Last name match (more unique than first name) among contacts
         with recent activity → might be the same person with a different email

    Returns up to 5 candidates with project/campaign info.
    """
    from sqlalchemy import func

    candidates = []
    seen_ids = set()

    async with async_session_maker() as session:
        # 1. Domain match — highest signal (skip free email providers)
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain and domain not in FREE_EMAIL_DOMAINS:
            result = await session.execute(
                select(Contact).where(
                    Contact.domain == domain,
                    Contact.deleted_at.is_(None)
                ).order_by(Contact.last_reply_at.desc().nullslast()).limit(5)
            )
            for c in result.scalars().all():
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    candidates.append(c)

        # 2. Last name match — only if we have a last name (2+ word name)
        #    More unique than first name, less noise
        parts = name.strip().split() if name and name.strip() else []
        last_name = parts[-1] if len(parts) >= 2 else ""
        if last_name and len(last_name) >= 3:
            result = await session.execute(
                select(Contact).where(
                    func.lower(Contact.last_name) == last_name.lower(),
                    Contact.deleted_at.is_(None)
                ).order_by(Contact.last_reply_at.desc().nullslast()).limit(5)
            )
            for c in result.scalars().all():
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    candidates.append(c)

        # Enrich with project names
        results = []
        for c in candidates[:5]:
            proj = await session.get(Project, c.project_id)
            campaign_name = None
            if c.platform_state:
                sl = c.platform_state.get("smartlead", {})
                camps = sl.get("campaigns", [])
                if camps:
                    campaign_name = camps[0] if isinstance(camps[0], str) else camps[0].get("name")

            results.append({
                "name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
                "email": c.email,
                "company": c.company_name or "",
                "project": proj.name if proj else "?",
                "campaign": campaign_name or "",
                "source": c.source or "",
            })

        return results


async def notify_meeting_booked(meeting: Meeting, project: dict, contact_info: Optional[dict] = None) -> bool:
    """Send Telegram notification about new meeting booking.

    Routing:
      1. Admin chat (TELEGRAM_CHAT_ID) — always
      2. Project telegram_subscribers — project leads/operators

    If contact_info is provided, enriches notification with CRM data.
    """
    from app.core.config import settings as cfg
    from html import escape
    from zoneinfo import ZoneInfo

    project_name = project.get("name", "Unknown")

    # Format datetime in Moscow timezone
    MSK = ZoneInfo("Europe/Moscow")
    dt = meeting.scheduled_at
    if dt.tzinfo:
        dt_msk = dt.astimezone(MSK)
    else:
        dt_msk = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(MSK)
    time_str = dt_msk.strftime("%d.%m.%Y %H:%M") + " МСК"

    # Build message — prefer CRM data over Calendly if available
    name = escape(meeting.invitee_name or "Unknown")
    email = escape(meeting.invitee_email or "")
    host = escape(meeting.host_name or "")

    # Company/title: prefer CRM, fallback to Calendly
    company = ""
    title = ""
    if contact_info:
        company = escape(contact_info.get("company_name") or meeting.invitee_company or "")
        title = escape(contact_info.get("job_title") or meeting.invitee_title or "")
    else:
        company = escape(meeting.invitee_company or "")
        title = escape(meeting.invitee_title or "")

    # Website: extract domain from email (if corporate)
    email_raw = meeting.invitee_email or ""
    email_domain = email_raw.split("@")[-1].lower() if "@" in email_raw else ""
    website = ""
    if email_domain and email_domain not in FREE_EMAIL_DOMAINS:
        website = email_domain

    company_line = f"\n<b>Компания:</b> {company}" if company else ""
    title_line = f"\n<b>Должность:</b> {title}" if title else ""
    website_line = f"\n<b>Сайт:</b> {escape(website)}" if website else ""
    host_line = f"\n<b>Host:</b> {host}" if host else ""

    # Questions from Calendly form
    questions_line = ""
    if meeting.invitee_questions:
        q_preview = meeting.invitee_questions[:200]
        if len(meeting.invitee_questions) > 200:
            q_preview += "..."
        questions_line = f"\n\n<b>Notes:</b>\n<i>{escape(q_preview)}</i>"

    message = f"""📅 <b>Новый звонок забукан!</b>

<b>Кто:</b> {name}
<b>Email:</b> {email}{company_line}{title_line}{website_line}

<b>Когда:</b> {time_str}{host_line}
<b>Проект:</b> {project_name}"""

    # Add CRM enrichment section if contact found
    if contact_info:
        crm_lines = []

        segment = contact_info.get("segment")
        if segment:
            crm_lines.append(f"<b>Segment:</b> {escape(segment)}")

        source = contact_info.get("source")
        if source:
            channel_emoji = {"email": "📧", "linkedin": "💼", "telegram": "📱"}.get(source, "📧")
            crm_lines.append(f"<b>Channel:</b> {channel_emoji} {escape(source)}")

        campaign = contact_info.get("campaign_name")
        if campaign:
            crm_lines.append(f"<b>Campaign:</b> {escape(campaign)}")

        status = contact_info.get("status")
        if status:
            crm_lines.append(f"<b>Status:</b> {escape(status)}")

        msg_count = contact_info.get("message_count", 0)
        if msg_count > 0:
            crm_lines.append(f"<b>Messages:</b> {msg_count} total")

        last_reply = contact_info.get("last_reply_text")
        last_reply_at = contact_info.get("last_reply_at")
        if last_reply:
            # Calculate "X days ago"
            days_ago = ""
            if last_reply_at:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc) if last_reply_at.tzinfo else datetime.utcnow()
                delta = now - last_reply_at
                if delta.days == 0:
                    days_ago = "today"
                elif delta.days == 1:
                    days_ago = "yesterday"
                else:
                    days_ago = f"{delta.days} days ago"

            reply_preview = escape(last_reply)
            time_info = f" ({days_ago})" if days_ago else ""
            crm_lines.append(f"<b>Last reply:</b> <i>\"{reply_preview}\"</i>{time_info}")

        if crm_lines:
            message += "\n\n── <b>From CRM</b> ──\n" + "\n".join(crm_lines)

    else:
        # Contact NOT found — warn operator and search for similar
        message += "\n\n⚠️ <b>Не найден в CRM</b>"

        try:
            similar = await find_similar_contacts(
                meeting.invitee_email or "",
                meeting.invitee_name or ""
            )
            if similar:
                message += "\n\n🔍 <b>Похожие контакты:</b>"
                for s in similar:
                    line = f"• {escape(s['name'])}"
                    if s["company"]:
                        line += f" — {escape(s['company'])}"
                    line += f" ({escape(s['email'])})"
                    if s["project"]:
                        line += f"\n  📁 {escape(s['project'])}"
                    if s["campaign"]:
                        line += f" | 📧 {escape(s['campaign'])}"
                    message += f"\n{line}"
            else:
                message += "\nПохожих контактов не найдено"
        except Exception as e:
            logger.warning(f"[CALENDLY] Similar contacts search failed: {e}")

    # Add Calendly form answers
    message += questions_line

    # Add meeting link if available
    if meeting.meeting_link:
        message += f'\n\n<a href="{meeting.meeting_link}">🔗 Join Meeting</a>'

    message = message.strip()

    # 1. Always send to admin chat (начальник)
    admin_chat = cfg.TELEGRAM_CHAT_ID
    admin_sent = False
    sent_chats = set()

    if admin_chat:
        admin_sent = await send_telegram_notification(message, chat_id=admin_chat)
        sent_chats.add(admin_chat)

    # 2. Send to project subscribers (лиды проекта)
    subscribers = project.get("telegram_subscribers", [])
    for subscriber_chat in subscribers:
        if subscriber_chat and subscriber_chat not in sent_chats:
            await send_telegram_notification(message, chat_id=subscriber_chat)
            sent_chats.add(subscriber_chat)

    if len(sent_chats) > 1:
        logger.info(f"[CALENDLY] Meeting notification sent to {len(sent_chats)} chats for project '{project_name}'")

    return admin_sent


async def process_invitee_created(payload: dict) -> dict:
    """Process invitee.created event — new booking."""
    event_data = payload.get("payload", {})

    # Extract event info
    event = event_data.get("event", {})
    invitee = event_data.get("invitee", {})

    event_uri = event.get("uri", "")
    invitee_uri = invitee.get("uri", "")

    # Get invitee details
    invitee_name = invitee.get("name", "")
    invitee_email = invitee.get("email", "")

    # Try to get company/title from questions_and_answers
    invitee_company = ""
    invitee_title = ""
    questions_text = ""

    questions = event_data.get("questions_and_answers", [])
    for qa in questions:
        question = qa.get("question", "").lower()
        answer = qa.get("answer", "")

        if "company" in question or "organization" in question:
            invitee_company = answer
        elif "title" in question or "role" in question or "position" in question:
            invitee_title = answer

        # Collect all Q&A
        questions_text += f"{qa.get('question', '')}: {answer}\n"

    # Event details
    event_type_name = event.get("event_type", {}).get("name", "") or event.get("name", "")
    start_time_str = event.get("start_time", "")
    end_time_str = event.get("end_time", "")
    location_data = event.get("location", {})
    meeting_link = location_data.get("join_url", "") or location_data.get("location", "")
    location_type = location_data.get("type", "")

    # Parse datetime
    try:
        scheduled_at = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    except Exception:
        scheduled_at = datetime.utcnow()

    # Calculate duration
    duration_minutes = 30
    try:
        if end_time_str and start_time_str:
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            duration_minutes = int((end_time - scheduled_at).total_seconds() / 60)
    except Exception:
        pass

    # Host info
    event_memberships = event.get("event_memberships", [])
    host_name = ""
    host_email = ""
    if event_memberships:
        user = event_memberships[0].get("user", {})
        host_name = user.get("name", "")
        host_email = user.get("email", "")

    # Find project: contact-first, then fallback to host-based
    project = await find_project_by_invitee_email(invitee_email)
    pre_matched_contact_id = project.get("contact_id") if project else None

    if not project:
        project = await find_project_by_calendly_user(host_email)

    if not project:
        logger.warning(f"[CALENDLY] No project found for {invitee_email} / host {host_email}")
        return {"status": "no_project", "event_uri": event_uri}

    project_id = project["id"]
    company_id = project["company_id"] or 1  # fallback to default company

    # Find contact with CRM history (use pre-matched project_id for correct lookup)
    contact_info = await find_contact_with_history(invitee_email, project_id)
    contact_id = contact_info["id"] if contact_info else pre_matched_contact_id

    # Enrich meeting data from CRM if Calendly didn't have it
    if contact_info:
        if not invitee_company and contact_info.get("company_name"):
            invitee_company = contact_info["company_name"]
        if not invitee_title and contact_info.get("job_title"):
            invitee_title = contact_info["job_title"]

    # Check for duplicate
    async with async_session_maker() as session:
        existing = await session.execute(
            select(Meeting).where(Meeting.calendly_event_uri == event_uri).limit(1)
        )
        if existing.scalar():
            logger.info(f"[CALENDLY] Meeting already exists for event {event_uri}")
            return {"status": "duplicate", "event_uri": event_uri}

        # Create meeting (enriched with CRM data)
        meeting = Meeting(
            company_id=company_id,
            project_id=project_id,
            contact_id=contact_id,
            calendly_event_uri=event_uri,
            calendly_invitee_uri=invitee_uri,
            invitee_name=invitee_name,
            invitee_email=invitee_email,
            invitee_company=invitee_company,
            invitee_title=invitee_title,
            event_type_name=event_type_name,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            meeting_link=meeting_link,
            location=location_type,
            host_name=host_name,
            host_email=host_email,
            status="scheduled",
            invitee_questions=questions_text.strip() if questions_text.strip() else None,
            # CRM enrichment
            channel=contact_info.get("source") if contact_info else None,
            segment=contact_info.get("segment") if contact_info else None,
            campaign_name=contact_info.get("campaign_name") if contact_info else None,
        )

        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)

        logger.info(f"[CALENDLY] Created meeting {meeting.id} for {invitee_name} ({invitee_email})")

        # Update contact status to meeting_booked if contact found
        if contact_id:
            contact_result = await session.execute(
                select(Contact).where(Contact.id == contact_id)
            )
            contact = contact_result.scalar()
            if contact and contact.status not in ('qualified', 'meeting_held'):
                old_status = contact.status
                contact.status = 'meeting_booked'
                await session.commit()
                logger.info(f"[CALENDLY] Updated contact {contact_id} status: {old_status} → meeting_booked")

        # Send TG notification to admin + project subscribers (enriched with CRM data)
        await notify_meeting_booked(meeting, project, contact_info)

        return {
            "status": "created",
            "meeting_id": meeting.id,
            "project": project["name"],
            "invitee": invitee_name,
        }


async def process_invitee_canceled(payload: dict) -> dict:
    """Process invitee.canceled event — cancellation."""
    event_data = payload.get("payload", {})
    event = event_data.get("event", {})
    event_uri = event.get("uri", "")

    cancellation = event_data.get("cancellation", {})
    cancellation_reason = cancellation.get("reason", "")
    canceled_by = cancellation.get("canceled_by", "")

    async with async_session_maker() as session:
        result = await session.execute(
            select(Meeting).where(Meeting.calendly_event_uri == event_uri).limit(1)
        )
        meeting = result.scalar()

        if not meeting:
            logger.info(f"[CALENDLY] No meeting found for cancelled event {event_uri}")
            return {"status": "not_found", "event_uri": event_uri}

        meeting.status = "cancelled"
        meeting.cancellation_reason = f"{canceled_by}: {cancellation_reason}" if cancellation_reason else canceled_by
        meeting.cancelled_at = datetime.utcnow()

        await session.commit()

        logger.info(f"[CALENDLY] Cancelled meeting {meeting.id}")
        return {"status": "cancelled", "meeting_id": meeting.id}


@router.post("/calendly")
async def calendly_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Calendly webhook events.

    Calendly sends:
    - invitee.created — when someone books a meeting
    - invitee.canceled — when a booking is cancelled

    Webhook URL: https://your-domain.com/api/webhooks/calendly
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"[CALENDLY] Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event", "")
    logger.info(f"[CALENDLY] Received webhook: {event_type}")

    if event_type == "invitee.created":
        result = await process_invitee_created(payload)
        return result

    elif event_type == "invitee.canceled":
        result = await process_invitee_canceled(payload)
        return result

    else:
        logger.info(f"[CALENDLY] Ignoring event type: {event_type}")
        return {"status": "ignored", "event": event_type}
