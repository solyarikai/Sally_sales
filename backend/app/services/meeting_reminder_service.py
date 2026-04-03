"""
Meeting reminder service — sends 24h and 2h reminders for booked meetings.

Currently scoped to Mifort (project_id=21).
Sends via SmartLead (email reply-in-thread) or GetSales (LinkedIn message)
based on meeting.channel.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.meeting import Meeting

logger = logging.getLogger(__name__)

# Only Mifort for now
ENABLED_PROJECT_IDS = [21]

TEMPLATE_24H = """<p>Hi {first_name},</p>

<p>Just a friendly reminder about our call tomorrow at <b>{time}</b>.</p>

<p>Here's the link: <a href="{meeting_link}">Join Meeting</a></p>

<p>If you need to reschedule, just let me know.</p>

<p>Best,<br>{sender_name}</p>"""

TEMPLATE_2H = """<p>Hi {first_name},</p>

<p>Looking forward to our call at <b>{time}</b> today.</p>

<p>Meeting link: <a href="{meeting_link}">Join Meeting</a></p>

<p>See you soon!</p>"""

TEMPLATE_24H_LINKEDIN = """Hi {first_name},

Just a friendly reminder about our call tomorrow at {time}.

Here's the link: {meeting_link}

If you need to reschedule, just let me know.

Best,
{sender_name}"""

TEMPLATE_2H_LINKEDIN = """Hi {first_name},

Looking forward to our call at {time} today.

Meeting link: {meeting_link}

See you soon!"""


def _format_time_cet(dt: datetime) -> str:
    """Format datetime as HH:MM CET for display."""
    from zoneinfo import ZoneInfo
    cet = dt.astimezone(ZoneInfo("Europe/Berlin"))
    return cet.strftime("%H:%M CET")


def _extract_first_name(full_name: str) -> str:
    """Extract first name from full name, fallback to 'there'."""
    if not full_name or full_name.lower() in ("test", "unknown"):
        return "there"
    return full_name.strip().split()[0]


def _parse_channel(channel: str):
    """Parse channel string into (platform, identifier).

    Examples:
        'smartlead:3081653' -> ('smartlead', '3081653')
        'getsales:430e90e2-...' -> ('getsales', '430e90e2-...')
        'email' -> ('email', None)
        None -> (None, None)
    """
    if not channel:
        return None, None
    if ":" in channel:
        platform, identifier = channel.split(":", 1)
        return platform, identifier
    return channel, None


async def _find_smartlead_lead_id(campaign_id: str, invitee_email: str) -> str | None:
    """Find SmartLead lead_id by email in a campaign."""
    from app.services.smartlead_service import smartlead_service, smartlead_request

    if not smartlead_service._api_key:
        return None

    try:
        resp = await smartlead_request(
            "GET",
            f"{smartlead_service.base_url}/campaigns/{campaign_id}/leads",
            params={"api_key": smartlead_service._api_key, "limit": 100},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        leads = data.get("data", []) if isinstance(data, dict) else data
        for lead_entry in leads:
            lead = lead_entry.get("lead", lead_entry) if isinstance(lead_entry, dict) else {}
            if isinstance(lead, dict) and lead.get("email", "").lower() == invitee_email.lower():
                return str(lead.get("id", ""))
    except Exception as e:
        logger.error(f"[REMINDER] Error finding SmartLead lead: {e}")
    return None


async def _find_getsales_lead_uuid(invitee_email: str, session: AsyncSession) -> str | None:
    """Find GetSales lead_uuid from processed_replies or contacts."""
    from app.models.reply import ProcessedReply

    # Check processed_replies for this email
    result = await session.execute(
        select(ProcessedReply.getsales_lead_uuid).where(
            ProcessedReply.lead_email == invitee_email,
            ProcessedReply.getsales_lead_uuid.isnot(None),
        ).order_by(ProcessedReply.created_at.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        return row

    # Fallback: search GetSales API
    try:
        from app.services.crm_sync_service import get_crm_sync_service
        sync = get_crm_sync_service()
        if sync.getsales:
            leads, _ = await sync.getsales.search_leads({"email": invitee_email}, limit=1)
            if leads:
                lead = leads[0]
                lead_data = lead.get("lead", lead) if isinstance(lead, dict) else {}
                return lead_data.get("uuid")
    except Exception as e:
        logger.error(f"[REMINDER] Error searching GetSales lead: {e}")
    return None


async def _send_email_reminder(meeting: Meeting, template: str, reminder_type: str) -> bool:
    """Send email reminder via SmartLead reply-in-thread."""
    from app.services.smartlead_service import smartlead_service

    platform, campaign_id = _parse_channel(meeting.channel)
    if not campaign_id:
        logger.warning(f"[REMINDER] Meeting {meeting.id}: no campaign_id in channel '{meeting.channel}'")
        return False

    lead_id = await _find_smartlead_lead_id(campaign_id, meeting.invitee_email)
    if not lead_id:
        logger.warning(f"[REMINDER] Meeting {meeting.id}: SmartLead lead not found for {meeting.invitee_email}")
        return False

    first_name = _extract_first_name(meeting.invitee_name)
    time_str = _format_time_cet(meeting.scheduled_at)
    sender_name = (meeting.host_name or "").split()[0] if meeting.host_name else "Team"

    body = template.format(
        first_name=first_name,
        time=time_str,
        meeting_link=meeting.meeting_link or "",
        sender_name=sender_name,
    )

    result = await smartlead_service.send_reply(campaign_id, lead_id, body)
    if result.get("error"):
        logger.error(f"[REMINDER] Meeting {meeting.id} {reminder_type} email failed: {result}")
        return False

    logger.info(f"[REMINDER] Meeting {meeting.id} {reminder_type} email sent to {meeting.invitee_email}")
    return True


async def _send_linkedin_reminder(meeting: Meeting, template: str, reminder_type: str, session: AsyncSession) -> bool:
    """Send LinkedIn reminder via GetSales."""
    from app.services.crm_sync_service import get_crm_sync_service

    platform, sender_profile_uuid = _parse_channel(meeting.channel)
    if not sender_profile_uuid:
        logger.warning(f"[REMINDER] Meeting {meeting.id}: no sender_profile_uuid in channel '{meeting.channel}'")
        return False

    lead_uuid = await _find_getsales_lead_uuid(meeting.invitee_email, session)
    if not lead_uuid:
        logger.warning(f"[REMINDER] Meeting {meeting.id}: GetSales lead not found for {meeting.invitee_email}")
        return False

    first_name = _extract_first_name(meeting.invitee_name)
    time_str = _format_time_cet(meeting.scheduled_at)
    sender_name = (meeting.host_name or "").split()[0] if meeting.host_name else "Team"

    text = template.format(
        first_name=first_name,
        time=time_str,
        meeting_link=meeting.meeting_link or "",
        sender_name=sender_name,
    )

    sync = get_crm_sync_service()
    if not sync.getsales:
        logger.error(f"[REMINDER] Meeting {meeting.id}: GetSales client not available")
        return False

    try:
        await sync.getsales.send_linkedin_message(sender_profile_uuid, lead_uuid, text)
        logger.info(f"[REMINDER] Meeting {meeting.id} {reminder_type} LinkedIn sent to {meeting.invitee_email}")
        return True
    except Exception as e:
        logger.error(f"[REMINDER] Meeting {meeting.id} {reminder_type} LinkedIn failed: {e}")
        return False


async def send_meeting_reminder(meeting: Meeting, reminder_type: str, session: AsyncSession) -> bool:
    """Send a reminder for a meeting via the appropriate channel.

    Args:
        meeting: Meeting record
        reminder_type: '24h' or '2h'
        session: DB session

    Returns:
        True if sent successfully
    """
    platform, _ = _parse_channel(meeting.channel)

    if platform == "smartlead":
        template = TEMPLATE_24H if reminder_type == "24h" else TEMPLATE_2H
        return await _send_email_reminder(meeting, template, reminder_type)
    elif platform == "getsales":
        template = TEMPLATE_24H_LINKEDIN if reminder_type == "24h" else TEMPLATE_2H_LINKEDIN
        return await _send_linkedin_reminder(meeting, template, reminder_type, session)
    else:
        logger.warning(f"[REMINDER] Meeting {meeting.id}: unknown channel '{meeting.channel}', skipping")
        return False


async def process_meeting_reminders():
    """Check all upcoming meetings and send due reminders.

    Called by CRMScheduler every 5 minutes.
    """
    now = datetime.now(timezone.utc)
    sent_count = 0

    async with async_session_maker() as session:
        # Get scheduled meetings for enabled projects in the next 26 hours
        meetings = await session.execute(
            select(Meeting).where(
                and_(
                    Meeting.project_id.in_(ENABLED_PROJECT_IDS),
                    Meeting.status == "scheduled",
                    Meeting.scheduled_at > now,
                    Meeting.scheduled_at <= now + timedelta(hours=26),
                    Meeting.channel.isnot(None),
                )
            )
        )
        meetings = meetings.scalars().all()

        for meeting in meetings:
            hours_until = (meeting.scheduled_at - now).total_seconds() / 3600

            # 24h reminder: send when 22-26 hours before meeting
            if 22 <= hours_until <= 26 and not meeting.reminder_24h_sent_at:
                ok = await send_meeting_reminder(meeting, "24h", session)
                if ok:
                    meeting.reminder_24h_sent_at = now
                    sent_count += 1

            # 2h reminder: send when 1.5-2.5 hours before meeting
            if 1.5 <= hours_until <= 2.5 and not meeting.reminder_2h_sent_at:
                ok = await send_meeting_reminder(meeting, "2h", session)
                if ok:
                    meeting.reminder_2h_sent_at = now
                    sent_count += 1

        await session.commit()

    if sent_count > 0:
        logger.info(f"[REMINDER] Sent {sent_count} meeting reminders")
    return sent_count
