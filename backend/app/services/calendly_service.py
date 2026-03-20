"""Calendly integration — fetch available time slots and format for reply drafts.

Uses Calendly API v2 with Personal Access Tokens (one per team member).
Fetches next 3 business days of availability, merges consecutive 30-min slots
into human-readable ranges, and formats for prompt injection.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

CALENDLY_API = "https://api.calendly.com"
CET = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")

# Minimum number of total slots across all days before triggering multi-calendar fallback
MIN_SLOTS_THRESHOLD = 3


# ────────────────────────── API helpers ──────────────────────────

async def _get_user_uri(token: str) -> Optional[str]:
    """Get the current user's URI from Calendly."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CALENDLY_API}/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            logger.warning(f"[CALENDLY] /users/me failed: {resp.status_code} {resp.text[:200]}")
            return None
        return resp.json().get("resource", {}).get("uri")


async def _get_event_type_uri(token: str, user_uri: str) -> Optional[str]:
    """Get the first active event type for this user (typically their 30-min meeting)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CALENDLY_API}/event_types",
            headers={"Authorization": f"Bearer {token}"},
            params={"user": user_uri, "active": "true", "count": 5},
        )
        if resp.status_code != 200:
            logger.warning(f"[CALENDLY] /event_types failed: {resp.status_code}")
            return None
        collection = resp.json().get("collection", [])
        if not collection:
            return None
        # Prefer the shortest-duration event type (typically 30-min intro call)
        collection.sort(key=lambda et: et.get("duration", 999))
        return collection[0].get("uri")


async def _get_available_times(
    token: str, event_type_uri: str, start_time: str, end_time: str,
) -> list[dict]:
    """Fetch available time slots from Calendly for a date range."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CALENDLY_API}/event_type_available_times",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "event_type": event_type_uri,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        if resp.status_code != 200:
            logger.warning(f"[CALENDLY] /available_times failed: {resp.status_code}")
            return []
        return resp.json().get("collection", [])


# ────────────────────────── Business day calculation ──────────────────────────

def _next_business_days(n: int = 3) -> list[datetime]:
    """Return next N business days (Mon-Fri) starting from tomorrow in CET."""
    now_cet = datetime.now(CET)
    days = []
    candidate = now_cet + timedelta(days=1)
    while len(days) < n:
        if candidate.weekday() < 5:  # Mon=0, Fri=4
            days.append(candidate.replace(hour=0, minute=0, second=0, microsecond=0))
        candidate += timedelta(days=1)
    return days


# ────────────────────────── Slot merging ──────────────────────────

def _merge_slots_to_ranges(slots_by_date: dict[str, list[datetime]]) -> list[str]:
    """Merge consecutive 30-min slots into ranges, format as 'dd.MM с HH:MM - HH:MM'.

    If there are gaps on the same day, separate with ' / '.
    Example: '06.03 с 8:00 - 10:30 / 11:30 - 14:30'
    """
    lines = []
    for date_key in sorted(slots_by_date.keys()):
        times = sorted(slots_by_date[date_key])
        if not times:
            continue

        # Build ranges: a range is a sequence of slots where each is 30 min after the previous
        ranges = []
        range_start = times[0]
        range_end = times[0] + timedelta(minutes=30)  # slot end = start + 30min

        for i in range(1, len(times)):
            expected_next = range_end
            if times[i] == expected_next:
                # Consecutive — extend the range
                range_end = times[i] + timedelta(minutes=30)
            else:
                # Gap — close current range, start new one
                ranges.append((range_start, range_end))
                range_start = times[i]
                range_end = times[i] + timedelta(minutes=30)

        ranges.append((range_start, range_end))

        # Format: dd.MM с HH:MM - HH:MM / HH:MM - HH:MM
        date_str = times[0].strftime("%d.%m")
        range_strs = []
        for rs, re in ranges:
            start_str = rs.strftime("%-H:%M") if rs.strftime("%M") != "00" else rs.strftime("%-H:%M")
            end_str = re.strftime("%-H:%M") if re.strftime("%M") != "00" else re.strftime("%-H:%M")
            range_strs.append(f"{start_str} - {end_str}")

        lines.append(f"{date_str} с {' / '.join(range_strs)}")

    return lines


# ────────────────────────── Public API ──────────────────────────

async def get_slots_for_member(token: str, days: int = 3) -> list[dict]:
    """Full pipeline: token → user_uri → event_type → available_times in CET.

    Returns list of {'start': datetime_cet, 'date_key': 'YYYY-MM-DD'} dicts.
    """
    if not token:
        return []

    user_uri = await _get_user_uri(token)
    if not user_uri:
        return []

    event_type_uri = await _get_event_type_uri(token, user_uri)
    if not event_type_uri:
        logger.warning("[CALENDLY] No active event types found")
        return []

    biz_days = _next_business_days(days)
    start_time = biz_days[0].astimezone(UTC).isoformat()
    # End at 23:59 of the last business day
    end_dt = biz_days[-1].replace(hour=23, minute=59, second=59)
    end_time = end_dt.astimezone(UTC).isoformat()

    raw_slots = await _get_available_times(token, event_type_uri, start_time, end_time)

    # Convert to CET
    result = []
    for slot in raw_slots:
        status = slot.get("status")
        if status != "available":
            continue
        start_utc = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
        start_cet = start_utc.astimezone(CET)
        result.append({
            "start": start_cet,
            "date_key": start_cet.strftime("%Y-%m-%d"),
        })

    return result


def format_slots_for_display(slots: list[dict]) -> list[str]:
    """Convert slot list to formatted display lines."""
    slots_by_date: dict[str, list[datetime]] = {}
    for s in slots:
        dk = s["date_key"]
        if dk not in slots_by_date:
            slots_by_date[dk] = []
        slots_by_date[dk].append(s["start"])
    return _merge_slots_to_ranges(slots_by_date)


def format_slots_for_prompt(slots_display: list[str], person_name: str) -> str:
    """Build the prompt injection block with available slots."""
    if not slots_display:
        return ""

    slot_lines = "\n".join(slots_display)
    return (
        f"\nДОСТУПНЫЕ СЛОТЫ для записи на демо с {person_name} (CET):\n"
        f"{slot_lines}\n\n"
        "ИНСТРУКЦИЯ: Предложи лиду выбрать удобный слот. Используй формат: "
        '"Подскажите, пожалуйста, подойдут ли какие-то из этих слотов вам по CET?" '
        "+ слоты из списка выше.\n"
    )


async def count_project_meetings(config: dict, since: datetime, until: datetime) -> int:
    """Count unique scheduled meetings across all Calendly members for a project.

    Uses organization-level query via the first available PAT token.
    Returns total active (non-cancelled) events in the date range.
    """
    members = config.get("members", [])
    if not members:
        return 0

    token = next((m.get("pat_token", "") for m in members if m.get("pat_token")), "")
    if not token:
        return 0

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get organization URI from user profile
            me_resp = await client.get(
                f"{CALENDLY_API}/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.status_code != 200:
                logger.warning(f"[CALENDLY] /users/me failed: {me_resp.status_code}")
                return 0
            org_uri = me_resp.json().get("resource", {}).get("current_organization")
            if not org_uri:
                return 0

            # Fetch all scheduled events for the organization in date range
            resp = await client.get(
                f"{CALENDLY_API}/scheduled_events",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "organization": org_uri,
                    "min_start_time": since.strftime("%Y-%m-%dT00:00:00.000000Z"),
                    "max_start_time": until.strftime("%Y-%m-%dT23:59:59.000000Z"),
                    "status": "active",
                    "count": 100,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"[CALENDLY] /scheduled_events failed: {resp.status_code}")
                return 0
            return len(resp.json().get("collection", []))
    except Exception as e:
        logger.warning(f"[CALENDLY] count_project_meetings failed: {e}")
        return 0


async def sync_calendly_events_for_project(
    project_id: int, project_name: str, config: dict, session
) -> dict:
    """Sync scheduled events from Calendly API to meetings table.

    Fetches events for the past 7 days and next 30 days.
    Creates new Meeting records for events not yet in DB.
    Updates contact status to meeting_booked if contact found.

    Returns: {"synced": int, "skipped": int, "errors": list}
    """
    from datetime import timezone
    from app.models.meeting import Meeting
    from app.models.contact import Contact
    from sqlalchemy import select

    members = config.get("members", [])
    if not members:
        return {"synced": 0, "skipped": 0, "errors": ["No members configured"]}

    # Use first member's token for org-level query
    token = next((m.get("pat_token", "") for m in members if m.get("pat_token")), "")
    if not token:
        return {"synced": 0, "skipped": 0, "errors": ["No PAT token found"]}

    synced = 0
    skipped = 0
    errors = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get user/org info
            me_resp = await client.get(
                f"{CALENDLY_API}/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.status_code != 200:
                return {"synced": 0, "skipped": 0, "errors": [f"API error: {me_resp.status_code}"]}

            user_data = me_resp.json().get("resource", {})
            org_uri = user_data.get("current_organization")
            if not org_uri:
                return {"synced": 0, "skipped": 0, "errors": ["No organization found"]}

            # Fetch events: past 7 days + next 30 days
            now = datetime.now(timezone.utc)
            min_start = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
            max_start = (now + timedelta(days=30)).strftime("%Y-%m-%dT23:59:59Z")

            events_resp = await client.get(
                f"{CALENDLY_API}/scheduled_events",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "organization": org_uri,
                    "min_start_time": min_start,
                    "max_start_time": max_start,
                    "status": "active",
                    "count": 100,
                },
            )
            if events_resp.status_code != 200:
                return {"synced": 0, "skipped": 0, "errors": [f"Events API error: {events_resp.status_code}"]}

            events = events_resp.json().get("collection", [])
            logger.info(f"[CALENDLY SYNC] {project_name}: found {len(events)} events")

            for event in events:
                event_uri = event.get("uri", "")

                # Check if already exists
                existing = await session.execute(
                    select(Meeting).where(Meeting.calendly_event_uri == event_uri).limit(1)
                )
                if existing.scalar():
                    skipped += 1
                    continue

                # Fetch invitee details
                invitees_resp = await client.get(
                    f"{event_uri}/invitees",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if invitees_resp.status_code != 200:
                    errors.append(f"Invitee fetch failed for {event_uri}")
                    continue

                invitees = invitees_resp.json().get("collection", [])
                if not invitees:
                    continue

                invitee = invitees[0]
                invitee_email = invitee.get("email", "").lower()
                invitee_name = invitee.get("name", "")
                invitee_uri = invitee.get("uri", "")

                # Parse event data
                start_time_str = event.get("start_time", "")
                end_time_str = event.get("end_time", "")
                try:
                    scheduled_at = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                except:
                    scheduled_at = now

                duration_minutes = 30
                try:
                    if end_time_str and start_time_str:
                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                        duration_minutes = int((end_time - scheduled_at).total_seconds() / 60)
                except:
                    pass

                # Host info
                memberships = event.get("event_memberships", [])
                host_name = ""
                host_email = ""
                if memberships:
                    host_name = memberships[0].get("user_name", "")
                    host_email = memberships[0].get("user_email", "")

                # Location/meeting link
                location = event.get("location", {})
                meeting_link = location.get("join_url", "")
                location_type = location.get("type", "")

                event_type_name = event.get("name", "Meeting")

                # Find contact by email
                contact_id = None
                contact_info = None
                if invitee_email:
                    contact_result = await session.execute(
                        select(Contact).where(
                            Contact.email == invitee_email,
                            Contact.project_id == project_id,
                            Contact.deleted_at.is_(None)
                        ).limit(1)
                    )
                    contact = contact_result.scalar()
                    if contact:
                        contact_id = contact.id
                        contact_info = {
                            "company_name": contact.company_name,
                            "job_title": contact.job_title,
                            "segment": contact.segment,
                            "source": contact.source,
                        }
                        # Update contact status
                        if contact.status not in ('qualified', 'meeting_held', 'meeting_booked'):
                            contact.status = 'meeting_booked'
                            logger.info(f"[CALENDLY SYNC] Updated contact {contact_id} to meeting_booked")

                # Create meeting (use string values for status/outcome since DB uses varchar)
                meeting = Meeting(
                    company_id=1,
                    project_id=project_id,
                    contact_id=contact_id,
                    calendly_event_uri=event_uri,
                    calendly_invitee_uri=invitee_uri,
                    invitee_name=invitee_name,
                    invitee_email=invitee_email,
                    invitee_company=contact_info.get("company_name") if contact_info else None,
                    invitee_title=contact_info.get("job_title") if contact_info else None,
                    event_type_name=event_type_name,
                    scheduled_at=scheduled_at,
                    duration_minutes=duration_minutes,
                    meeting_link=meeting_link,
                    location=location_type,
                    host_name=host_name,
                    host_email=host_email,
                    status="scheduled",
                    channel=contact_info.get("source") if contact_info else None,
                    segment=contact_info.get("segment") if contact_info else None,
                )
                session.add(meeting)
                synced += 1
                logger.info(f"[CALENDLY SYNC] Created meeting for {invitee_name} ({invitee_email})")

            await session.commit()

    except Exception as e:
        logger.error(f"[CALENDLY SYNC] Error for {project_name}: {e}")
        errors.append(str(e))

    return {"synced": synced, "skipped": skipped, "errors": errors}


async def sync_all_calendly_projects() -> dict:
    """Sync Calendly events for all projects with calendly_config.

    Called by scheduler every 5 minutes.
    Returns: {"total_synced": int, "projects_processed": int}
    """
    from app.db import async_session_maker
    from app.models.contact import Project
    from sqlalchemy import select

    total_synced = 0
    projects_processed = 0

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
            if not config.get("members"):
                continue

            sync_result = await sync_calendly_events_for_project(
                project.id, project.name, config, session
            )
            total_synced += sync_result["synced"]
            projects_processed += 1

            if sync_result["synced"] > 0:
                logger.info(f"[CALENDLY SYNC] {project.name}: synced {sync_result['synced']}, skipped {sync_result['skipped']}")

    return {"total_synced": total_synced, "projects_processed": projects_processed}


async def get_slots_with_fallback(
    config: dict, member_id: Optional[str] = None, days: int = 3,
) -> dict:
    """Fetch slots for a member, fallback to merging all members if too few.

    Returns:
        {
            "member_id": str,
            "display_name": str,
            "slots": [{"start": datetime, "date_key": str}, ...],
            "slots_display": ["dd.MM с HH:MM - HH:MM", ...],
            "formatted_for_prompt": str,
            "is_fallback": bool,
        }
    """
    members = config.get("members", [])
    if not members:
        return {"member_id": "", "display_name": "", "slots": [], "slots_display": [],
                "formatted_for_prompt": "", "is_fallback": False}

    # Find target member (default if not specified)
    target = None
    if member_id:
        target = next((m for m in members if m["id"] == member_id), None)
    if not target:
        target = next((m for m in members if m.get("is_default")), members[0])

    display_name = target.get("display_name", target["id"])
    token = target.get("pat_token", "")

    slots = await get_slots_for_member(token, days)

    is_fallback = False
    if len(slots) < MIN_SLOTS_THRESHOLD:
        # Merge from all members
        logger.info(f"[CALENDLY] {display_name} has {len(slots)} slots, merging all calendars")
        all_slots = list(slots)  # keep existing
        seen_starts = {s["start"] for s in slots}
        for m in members:
            if m["id"] == target["id"]:
                continue
            m_token = m.get("pat_token", "")
            if not m_token:
                continue
            try:
                m_slots = await get_slots_for_member(m_token, days)
                for s in m_slots:
                    if s["start"] not in seen_starts:
                        all_slots.append(s)
                        seen_starts.add(s["start"])
            except Exception as e:
                logger.warning(f"[CALENDLY] Fallback fetch failed for {m['id']}: {e}")
        slots = all_slots
        is_fallback = True
        display_name = "Команда"

    slots_display = format_slots_for_display(slots)
    formatted = format_slots_for_prompt(slots_display, display_name)

    return {
        "member_id": target["id"],
        "display_name": display_name if not is_fallback else f"{target.get('display_name', target['id'])} + команда",
        "slots": slots,
        "slots_display": slots_display,
        "formatted_for_prompt": formatted,
        "is_fallback": is_fallback,
    }
