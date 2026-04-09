#!/usr/bin/env python3
"""
Daily cron: sync OOO leads from ALL OnSocial campaigns into re-engagement.

Improvements over smartlead_infplat_ooo_sync.py:
- Covers ALL segments: INFPLAT, IMAGENCY, AFFPERF
- Parses return date from OOO email body (regex)
- Schedules re-engagement = return_date + 7 days
- Fallback: reply_date + 14 days if no return date found
- Stores parsed dates in JSON state file to avoid re-fetching

Run daily via cron (6:00 UTC = 9:00 MSK):
  0 6 * * * cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_ooo_sync.py >> /tmp/ooo_sync.log 2>&1
"""

import httpx
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

KEY = os.environ.get("SMARTLEAD_API_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7380803777")
BASE = "https://server.smartlead.ai/api/v1"

# ── Segment config: keywords → re-engagement campaign ID ──
SEGMENTS = {
    "INFPLAT": {
        "keywords": ["INFLUENCER PLATFORMS", "INFPLAT", "PLATFORM"],
        "campaign_id": 3123881,
    },
    "IMAGENCY": {
        "keywords": ["IMAGENCY", "IM AGENCIES", "IM-FIRST", "IM_FIRST", "IM agencies"],
        "campaign_id": 3121190,
    },
    # AFFPERF: not scanning yet — uncomment when re-engagement campaign is created
    # "AFFPERF": {
    #     "keywords": ["AFFPERF", "AFFILIATE", "PERFORMANCE"],
    #     "campaign_id": None,
    # },
}

EXCLUDE_KEYWORDS = [
    "Re-engagement", "iGaming", "trading", "GWC", "Inxy", "Gcore",
    "SquareFi", "Deliryo", "CrowdControl", "gaming",
]

# State file: stores parsed return dates so we don't re-fetch emails daily
STATE_FILE = Path(__file__).parent / "ooo_sync_state.json"
DAYS_AFTER_RETURN = 7   # re-engage 7 days after return
FALLBACK_DAYS = 21      # if no return date found, wait 21 days from OOO reply

DRY_RUN = "--dry-run" in sys.argv or "-n" in sys.argv

if not KEY:
    print("ERROR: SMARTLEAD_API_KEY not set")
    sys.exit(1)


# ── API helpers ──

API_DELAY = 0.6  # seconds between API calls (SmartLead rate limit ~2/sec)


def _api_call(method, url, params, json_data=None, timeout=60):
    """Execute API call with retry on 429."""
    for attempt in range(4):
        if method == "GET":
            r = httpx.get(url, params=params, timeout=timeout)
        else:
            r = httpx.post(url, params=params, json=json_data, timeout=timeout)
        if r.status_code == 429:
            wait = 2 ** attempt + 1  # 2, 3, 5, 9 seconds
            print(f"    Rate limited, waiting {wait}s (attempt {attempt + 1}/4)...")
            time.sleep(wait)
            continue
        return r
    return r  # return last response even if still 429


def get(path, params=None):
    time.sleep(API_DELAY)
    p = {"api_key": KEY}
    if params:
        p.update(params)
    r = _api_call("GET", f"{BASE}{path}", p)
    r.raise_for_status()
    return r.json()


def post(path, data, timeout=30):
    time.sleep(API_DELAY)
    r = _api_call("POST", f"{BASE}{path}", {"api_key": KEY}, json_data=data, timeout=timeout)
    if r.status_code >= 400:
        print(f"  API error {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    return r.json()


def tg(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"  TG error: {e}")


def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26].rstrip("Z"), fmt.rstrip("Z")).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ── Return date extraction from OOO email body ──

# Month name → number mapping (EN + a few common languages)
MONTH_MAP = {}
for i, names in enumerate([
    ["january", "jan", "enero", "janvier", "januar", "gennaio", "janeiro", "januari"],
    ["february", "feb", "febrero", "février", "februar", "febbraio", "fevereiro", "februari"],
    ["march", "mar", "marzo", "mars", "märz", "marz"],
    ["april", "apr", "abril", "avril", "aprile"],
    ["may", "mayo", "mai", "maggio", "maio", "mei"],
    ["june", "jun", "junio", "juin", "juni", "giugno", "junho"],
    ["july", "jul", "julio", "juillet", "juli", "luglio", "julho"],
    ["august", "aug", "agosto", "août", "aout", "augusti"],
    ["september", "sep", "sept", "septiembre", "septembre", "settembre", "setembro"],
    ["october", "oct", "octubre", "octobre", "oktober", "ottobre", "outubro"],
    ["november", "nov", "noviembre", "novembre"],
    ["december", "dec", "diciembre", "décembre", "dezember", "dicembre", "dezembro"],
], start=1):
    for name in names:
        MONTH_MAP[name] = i

MONTH_PATTERN = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))

# Patterns to find return date in OOO body
RETURN_PATTERNS = [
    # "back on April 15" / "return on March 20" / "returning April 20"
    rf"(?:back|return(?:ing)?|available|in\s+(?:the\s+)?office)\s+(?:on\s+)?({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
    # "back on 15 April" / "return 20 March"
    rf"(?:back|return(?:ing)?|available|in\s+(?:the\s+)?office)\s+(?:on\s+)?(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s*,?\s*(\d{{4}}))?",
    # "until April 15" / "through March 20" / "till April 20"
    rf"(?:until|till|through|avant le|bis|hasta)\s+({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
    # "until 15 April"
    rf"(?:until|till|through|avant le|bis|hasta)\s+(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s*,?\s*(\d{{4}}))?",
    # "back on 2026-04-15" / "return 2026-04-15"
    r"(?:back|return(?:ing)?|available|until|till|through)\s+(?:on\s+)?(\d{4})-(\d{2})-(\d{2})",
    # "back on 04/15/2026" or "15/04/2026"
    r"(?:back|return(?:ing)?|available|until|till|through)\s+(?:on\s+)?(\d{1,2})[/.](\d{1,2})[/.](\d{4})",
    # "back Monday, April 15"
    rf"(?:back|return(?:ing)?)\s+(?:on\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
]


def strip_html(html_text):
    """Strip HTML tags and decode entities."""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_return_date(email_body, reply_date):
    """
    Parse OOO email body for a return date.
    Returns datetime or None.
    """
    if not email_body:
        return None

    text = strip_html(email_body).lower()
    now = datetime.now(timezone.utc)
    current_year = now.year

    for i, pattern in enumerate(RETURN_PATTERNS):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue

        groups = m.groups()

        try:
            if i == 4:
                # ISO format: YYYY-MM-DD
                return datetime(int(groups[0]), int(groups[1]), int(groups[2]), tzinfo=timezone.utc)

            if i == 5:
                # DD/MM/YYYY or MM/DD/YYYY — assume DD/MM for international
                d1, d2, y = int(groups[0]), int(groups[1]), int(groups[2])
                if d1 > 12:
                    return datetime(y, d2, d1, tzinfo=timezone.utc)
                elif d2 > 12:
                    return datetime(y, d1, d2, tzinfo=timezone.utc)
                # Ambiguous — assume DD/MM (most OOO are international)
                return datetime(y, d2, d1, tzinfo=timezone.utc)

            if i in (0, 2, 6):
                # Month Day [Year]
                month_str, day_str = groups[0], groups[1]
                year_str = groups[2] if len(groups) > 2 else None
            elif i in (1, 3):
                # Day Month [Year]
                day_str, month_str = groups[0], groups[1]
                year_str = groups[2] if len(groups) > 2 else None
            else:
                continue

            month = MONTH_MAP.get(month_str.lower())
            if not month:
                continue
            day = int(day_str)
            year = int(year_str) if year_str else current_year

            result = datetime(year, month, day, tzinfo=timezone.utc)
            # If the parsed date is in the past by >6 months, bump year
            if result < now - timedelta(days=180):
                result = result.replace(year=year + 1)
            return result

        except (ValueError, TypeError):
            continue

    return None


def fetch_ooo_reply_text(campaign_id, lead_id):
    """Fetch the OOO reply text from SmartLead message history."""
    try:
        resp = get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")
        history = resp if isinstance(resp, list) else resp.get("history", [])
        # Find last REPLY message
        for msg in reversed(history):
            msg_type = msg.get("type", "").upper()
            if msg_type == "REPLY" or msg.get("direction") == "inbound":
                return msg.get("email_body", msg.get("body", msg.get("text", "")))
    except Exception as e:
        print(f"    Failed to fetch message history for lead {lead_id}: {e}")
    return None


# ── State management ──

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Main logic ──

now = datetime.now(timezone.utc)
mode = "DRY RUN" if DRY_RUN else "LIVE"
print(f"[{now.strftime('%Y-%m-%d %H:%M')} UTC] Running universal OOO sync ({mode})")
print(f"Logic: re-engage {DAYS_AFTER_RETURN}d after parsed return date, fallback {FALLBACK_DAYS}d after OOO reply\n")

state = load_state()

# ── Step 0: Discover campaigns by segment ──
print("Discovering OnSocial campaigns...")
all_camps = get("/campaigns")
if isinstance(all_camps, dict):
    all_camps = all_camps.get("campaigns", all_camps.get("data", []))

segment_campaigns = {seg: [] for seg in SEGMENTS}
all_reengagement_ids = {
    cfg["campaign_id"] for cfg in SEGMENTS.values() if cfg["campaign_id"]
}

for c in all_camps:
    name = c.get("name", "")
    name_upper = name.upper()
    cid = c["id"]

    if cid in all_reengagement_ids:
        continue
    if any(kw.upper() in name_upper for kw in EXCLUDE_KEYWORDS):
        continue

    for seg, cfg in SEGMENTS.items():
        if any(kw.upper() in name_upper for kw in cfg["keywords"]):
            segment_campaigns[seg].append((cid, name))
            break

for seg, camps in segment_campaigns.items():
    re_id = SEGMENTS[seg]["campaign_id"]
    status = f"→ campaign #{re_id}" if re_id else "→ NO re-engagement campaign yet"
    print(f"  {seg}: {len(camps)} campaigns {status}")

# ── Step 1: Get emails already in re-engagement, check for repeat OOO ──
print("\nFetching leads already in re-engagement campaigns...")
existing_emails = {}  # segment → set of emails (excluding repeat OOO)

for seg, cfg in SEGMENTS.items():
    re_id = cfg["campaign_id"]
    if not re_id:
        existing_emails[seg] = set()
        continue

    # 1a: Get all leads in re-engagement
    all_emails = set()
    offset = 0
    while True:
        resp = get(f"/campaigns/{re_id}/leads", {"limit": 100, "offset": offset})
        leads = resp if isinstance(resp, list) else resp.get("leads", resp.get("data", []))
        if not leads:
            break
        for l in leads:
            lead = l.get("lead", l)
            email = lead.get("email", "")
            if email:
                all_emails.add(email.lower())
        if len(leads) < 100:
            break
        offset += 100

    # 1b: Find OOO leads WITHIN re-engagement (repeat OOO)
    repeat_ooo = set()
    offset = 0
    while True:
        try:
            resp = get(f"/campaigns/{re_id}/statistics", {"limit": 500, "offset": offset})
            data = resp if isinstance(resp, list) else resp.get("data", [])
        except Exception as e:
            print(f"  [{seg}] re-engagement stats error: {e}")
            break
        if not data:
            break
        for row in data:
            if row.get("lead_category") == "Out Of Office":
                email = (row.get("lead_email") or "").lower()
                if email:
                    repeat_ooo.add(email)
        if len(data) < 500:
            break
        offset += 500

    # Exclude repeat OOO from "already added" — they need re-engagement again
    existing_emails[seg] = all_emails - repeat_ooo
    print(f"  {seg}: {len(all_emails)} in re-engagement, {len(repeat_ooo)} repeat OOO (will re-process)")

# ── Step 2: Collect OOO leads + build email→lead_id mapping ──
print("\nScanning campaigns for OOO leads...")
ooo_leads = {}  # email → lead info
email_to_lead_id = {}  # (campaign_id, email) → lead_id

for seg, camps in segment_campaigns.items():
    for cid, cname in camps:
        # 2a: Find OOO leads via statistics
        ooo_emails_in_camp = set()
        offset = 0
        while True:
            try:
                resp = get(f"/campaigns/{cid}/statistics", {"limit": 500, "offset": offset})
                data = resp if isinstance(resp, list) else resp.get("data", [])
            except Exception as e:
                print(f"  [{cid}] error: {e}")
                break
            if not data:
                break
            for row in data:
                if row.get("lead_category") != "Out Of Office":
                    continue
                email = (row.get("lead_email") or "").lower()
                if not email:
                    continue
                date_str = row.get("reply_time") or row.get("sent_time")
                lead_date = parse_date(date_str)

                ooo_emails_in_camp.add(email)
                if email not in ooo_leads or (lead_date and lead_date < (ooo_leads[email].get("reply_date") or now)):
                    ooo_leads[email] = {
                        "email": email,
                        "name": row.get("lead_name", ""),
                        "segment": seg,
                        "campaign": cname,
                        "campaign_id": cid,
                        "reply_date": lead_date,
                        "reply_date_str": (date_str or "")[:10],
                    }
            if len(data) < 500:
                break
            offset += 500

        if not ooo_emails_in_camp:
            continue
        print(f"  [{seg}] [{cid}] {cname}: {len(ooo_emails_in_camp)} OOO")

        # 2b: Build email→lead_id mapping for OOO leads that need parsing
        needs_parsing = {e for e in ooo_emails_in_camp if e not in state or not state[e].get("parsed")}
        if not needs_parsing:
            continue

        offset = 0
        while needs_parsing:
            resp = get(f"/campaigns/{cid}/leads", {"limit": 100, "offset": offset})
            leads_list = resp if isinstance(resp, list) else resp.get("leads", resp.get("data", []))
            if not leads_list:
                break
            for l in leads_list:
                lead_obj = l.get("lead", l)
                e = (lead_obj.get("email") or "").lower()
                lid = lead_obj.get("id")
                if e in needs_parsing and lid:
                    email_to_lead_id[(cid, e)] = lid
                    needs_parsing.discard(e)
            if len(leads_list) < 100:
                break
            offset += 100

print(f"\nTotal unique OOO leads: {len(ooo_leads)}")
print(f"Lead IDs resolved for parsing: {len(email_to_lead_id)}")

# ── Step 3: Parse return dates (fetch email body for new leads only) ──
print("\nParsing return dates from OOO emails...")
new_parsed = 0
cached = 0
no_date = 0

for email, lead in ooo_leads.items():
    # Check if we already parsed this lead
    if email in state and state[email].get("return_date"):
        lead["return_date"] = parse_date(state[email]["return_date"])
        lead["return_source"] = "cached"
        cached += 1
        continue

    if email in state and state[email].get("parsed") and not state[email].get("return_date"):
        lead["return_date"] = None
        lead["return_source"] = "cached_none"
        cached += 1
        continue

    # Fetch and parse
    campaign_id = lead.get("campaign_id")
    lead_id = email_to_lead_id.get((campaign_id, email))
    if not lead_id or not campaign_id:
        lead["return_date"] = None
        lead["return_source"] = "no_lead_id"
        no_date += 1
        continue

    body = fetch_ooo_reply_text(campaign_id, lead_id)
    return_date = extract_return_date(body, lead.get("reply_date"))

    lead["return_date"] = return_date
    lead["return_source"] = "parsed"

    # Save to state
    state[email] = {
        "parsed": True,
        "return_date": return_date.isoformat() if return_date else None,
        "reply_date": lead["reply_date"].isoformat() if lead.get("reply_date") else None,
        "segment": lead["segment"],
        "name": lead["name"],
        "ooo_snippet": (strip_html(body)[:100] if body else ""),
    }

    if return_date:
        new_parsed += 1
        print(f"  {email}: returns {return_date.strftime('%Y-%m-%d')}")
    else:
        no_date += 1

save_state(state)
print(f"  Parsed new: {new_parsed}, cached: {cached}, no date found: {no_date}")

# ── Step 4: Decide who is ready for re-engagement ──
print("\nFiltering leads ready for re-engagement...")

to_upload = {}   # segment → list of leads
skipped = {"already_added": 0, "too_early": 0, "no_campaign": 0}
waiting_leads = []

for email, lead in ooo_leads.items():
    seg = lead["segment"]

    # No re-engagement campaign for this segment
    if not SEGMENTS[seg]["campaign_id"]:
        skipped["no_campaign"] += 1
        continue

    # Already in re-engagement
    if email in existing_emails.get(seg, set()):
        skipped["already_added"] += 1
        continue

    # Calculate ready date
    return_date = lead.get("return_date")
    reply_date = lead.get("reply_date")

    if return_date:
        ready_date = return_date + timedelta(days=DAYS_AFTER_RETURN)
        source = f"return {return_date.strftime('%m/%d')} + {DAYS_AFTER_RETURN}d"
    elif reply_date:
        ready_date = reply_date + timedelta(days=FALLBACK_DAYS)
        source = f"reply {reply_date.strftime('%m/%d')} + {FALLBACK_DAYS}d (no return date)"
    else:
        # No dates at all — upload immediately
        ready_date = now - timedelta(days=1)
        source = "no dates, uploading"

    if ready_date <= now:
        to_upload.setdefault(seg, []).append(lead)
    else:
        days_left = (ready_date - now).days
        waiting_leads.append(f"{email} [{seg}] (ready in ~{days_left}d — {source})")
        skipped["too_early"] += 1

print(f"  Already in re-engagement: {skipped['already_added']}")
print(f"  Too early:                {skipped['too_early']}")
print(f"  No re-engagement campaign:{skipped['no_campaign']}")
for seg, leads in to_upload.items():
    print(f"  Ready [{seg}]:             {len(leads)}")

if waiting_leads:
    print(f"\nWaiting ({len(waiting_leads)} leads):")
    for w in waiting_leads[:20]:
        print(f"  - {w}")
    if len(waiting_leads) > 20:
        print(f"  ... and {len(waiting_leads) - 20} more")

# ── Step 5: Upload ──
total_uploaded = 0
upload_summary = []

for seg, leads in to_upload.items():
    re_id = SEGMENTS[seg]["campaign_id"]
    if not re_id:
        continue

    print(f"\n{'[DRY RUN] Would upload' if DRY_RUN else 'Uploading'} {len(leads)} [{seg}] leads to campaign #{re_id}...")

    for lead in leads:
        ret = lead.get("return_date")
        if ret:
            src = f"returns {ret.strftime('%Y-%m-%d')} + {DAYS_AFTER_RETURN}d"
        else:
            src = f"fallback (reply + {FALLBACK_DAYS}d)"
        print(f"  - {lead['email']} ({lead['name']}) — {src}")
        upload_summary.append(f"  - {lead['name']} ({lead['email']}) [{seg}] — {src}")

    if DRY_RUN:
        total_uploaded += len(leads)
        continue

    lead_list = []
    for lead in leads:
        parts = lead["name"].split(" ", 1)
        lead_list.append({
            "email": lead["email"],
            "first_name": parts[0] if parts else "",
            "last_name": parts[1] if len(parts) > 1 else "",
        })

    try:
        resp = post(f"/campaigns/{re_id}/leads", {"lead_list": lead_list}, timeout=60)
        uploaded = resp.get("upload_count", len(lead_list))
        dupes = resp.get("duplicate_count", 0)
        total_uploaded += uploaded
        print(f"  Uploaded: {uploaded}, duplicates: {dupes}")
    except Exception as e:
        print(f"  Upload error for {seg}: {e}")

# ── Step 6: Telegram notification (skip in dry run) ──
if DRY_RUN:
    print(f"\n[DRY RUN] Would upload {total_uploaded} leads total. No changes made.")
    sys.exit(0)

if total_uploaded > 0:
    uploaded_lines = "\n".join(upload_summary)
    waiting_section = ""
    if waiting_leads:
        top_waiting = "\n".join(f"  - {w}" for w in waiting_leads[:10])
        waiting_section = f"\n\nЕщё ждут ({len(waiting_leads)}):\n{top_waiting}"

    tg(
        f"✅ OOO → Re-engagement — {now.strftime('%d.%m.%Y')}\n\n"
        f"Добавлено: {total_uploaded}\n\n"
        f"{uploaded_lines}"
        f"{waiting_section}"
    )
elif waiting_leads:
    top_waiting = "\n".join(f"  - {w}" for w in waiting_leads[:10])
    tg(
        f"📭 OOO sync — {now.strftime('%d.%m.%Y')}\n\n"
        f"Новых лидов нет.\n\n"
        f"Ждут ({len(waiting_leads)}):\n{top_waiting}"
    )
else:
    tg(f"📭 OOO sync — {now.strftime('%d.%m.%Y')}\nОчередь пуста.")

print(f"\nDone. Uploaded: {total_uploaded}. Next run tomorrow.")
