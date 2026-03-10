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
