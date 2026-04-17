#!/usr/bin/env python3
"""
Universal OOO → Re-engagement sync for any SmartLead project.

Usage:
  python3 smartlead_ooo_sync_universal.py --project OnSocial          # one project
  python3 smartlead_ooo_sync_universal.py --project Inxy EasyStaff    # multiple
  python3 smartlead_ooo_sync_universal.py --all                       # all projects in config
  python3 smartlead_ooo_sync_universal.py --all --dry-run             # dry run
  python3 smartlead_ooo_sync_universal.py --project Inxy --create-re  # create re-engagement campaign

Config: ooo_sync_config.json (same directory)

Features:
- Parses return date from OOO email body (15+ languages)
- Re-engagement = return_date + 7 days (configurable)
- Fallback = reply_date + 21 days if no return date found
- Handles repeat OOO in re-engagement campaigns
- State file per project to avoid re-fetching emails
- Telegram notifications

Cron (weekdays 9:00 MSK):
  0 6 * * 1-5 cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_ooo_sync_universal.py --all >> /tmp/ooo_sync_universal.log 2>&1
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
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "ooo_sync_config.json"

if not KEY:
    print("ERROR: SMARTLEAD_API_KEY not set")
    sys.exit(1)


# ── Parse args ──

DRY_RUN = "--dry-run" in sys.argv or "-n" in sys.argv
CREATE_RE = "--create-re" in sys.argv
RUN_ALL = "--all" in sys.argv
NO_TG = "--no-tg" in sys.argv

project_names = []
if "--project" in sys.argv:
    idx = sys.argv.index("--project")
    for a in sys.argv[idx + 1:]:
        if a.startswith("-"):
            break
        project_names.append(a)

# Load config
config = json.loads(CONFIG_FILE.read_text())
defaults = config.get("defaults", {})
all_projects = config.get("projects", {})

if RUN_ALL:
    project_names = list(all_projects.keys())
elif not project_names:
    print("Usage: smartlead_ooo_sync_universal.py --project <name> [<name2>...] | --all")
    print(f"Available: {', '.join(all_projects.keys())}")
    sys.exit(1)

for pn in project_names:
    if pn not in all_projects:
        print(f"ERROR: Unknown project '{pn}'. Available: {', '.join(all_projects.keys())}")
        sys.exit(1)


# ── API helpers ──

API_DELAY = 0.6


def _api_call(method, url, params, json_data=None, timeout=60):
    for attempt in range(4):
        if method == "GET":
            r = httpx.get(url, params=params, timeout=timeout)
        else:
            r = httpx.post(url, params=params, json=json_data, timeout=timeout)
        if r.status_code == 429:
            wait = 2 ** attempt + 1
            print(f"    Rate limited, waiting {wait}s (attempt {attempt + 1}/4)...")
            time.sleep(wait)
            continue
        return r
    return r


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


def delete(path, timeout=30):
    time.sleep(API_DELAY)
    p = {"api_key": KEY}
    for attempt in range(4):
        r = httpx.delete(f"{BASE}{path}", params=p, timeout=timeout)
        if r.status_code == 429:
            wait = 2 ** attempt + 1
            time.sleep(wait)
            continue
        break
    if r.status_code >= 400:
        print(f"  DELETE error {r.status_code}: {r.text[:200]}")
        return None
    try:
        return r.json()
    except Exception:
        return {}


def tg(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": message},
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


# ── Return date extraction ──

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

RETURN_PATTERNS = [
    rf"(?:back|return(?:ing)?|available|in\s+(?:the\s+)?office)\s+(?:on\s+)?({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
    rf"(?:back|return(?:ing)?|available|in\s+(?:the\s+)?office)\s+(?:on\s+)?(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s*,?\s*(\d{{4}}))?",
    rf"(?:until|till|through|avant le|bis|hasta)\s+({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
    rf"(?:until|till|through|avant le|bis|hasta)\s+(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s*,?\s*(\d{{4}}))?",
    r"(?:back|return(?:ing)?|available|until|till|through)\s+(?:on\s+)?(\d{4})-(\d{2})-(\d{2})",
    r"(?:back|return(?:ing)?|available|until|till|through)\s+(?:on\s+)?(\d{1,2})[/.](\d{1,2})[/.](\d{4})",
    rf"(?:back|return(?:ing)?)\s+(?:on\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+({MONTH_PATTERN})\s+(\d{{1,2}})(?:\s*,?\s*(\d{{4}}))?",
]


def strip_html(html_text):
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_return_date(email_body, reply_date):
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
                return datetime(int(groups[0]), int(groups[1]), int(groups[2]), tzinfo=timezone.utc)
            if i == 5:
                d1, d2, y = int(groups[0]), int(groups[1]), int(groups[2])
                if d1 > 12:
                    return datetime(y, d2, d1, tzinfo=timezone.utc)
                elif d2 > 12:
                    return datetime(y, d1, d2, tzinfo=timezone.utc)
                return datetime(y, d2, d1, tzinfo=timezone.utc)
            if i in (0, 2, 6):
                month_str, day_str = groups[0], groups[1]
                year_str = groups[2] if len(groups) > 2 else None
            elif i in (1, 3):
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
            if result < now - timedelta(days=180):
                result = result.replace(year=year + 1)
            return result
        except (ValueError, TypeError):
            continue
    return None


def fetch_ooo_reply_text(campaign_id, lead_id):
    try:
        resp = get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")
        history = resp if isinstance(resp, list) else resp.get("history", [])
        for msg in reversed(history):
            msg_type = msg.get("type", "").upper()
            if msg_type == "REPLY" or msg.get("direction") == "inbound":
                return msg.get("email_body", msg.get("body", msg.get("text", "")))
    except Exception as e:
        print(f"    Failed to fetch message history for lead {lead_id}: {e}")
    return None


# ── State management ──

def load_state(project_name):
    path = SCRIPT_DIR / f"ooo_sync_state_{project_name.lower()}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(project_name, state):
    path = SCRIPT_DIR / f"ooo_sync_state_{project_name.lower()}.json"
    path.write_text(json.dumps(state, indent=2, default=str))


# ── Create re-engagement campaign ──

def create_reengagement_campaign(project_name, segment_name):
    name = f"c-{project_name}_Re-engagement"
    if segment_name != "ALL":
        name += f"_{segment_name}"

    print(f"\nCreating re-engagement campaign: {name}")
    resp = post("/campaigns/create", {"name": name})
    cid = resp["id"]
    print(f"  Created: #{cid}")
    print(f"  IMPORTANT: Add email accounts and activate manually in SmartLead UI")
    print(f"  Update ooo_sync_config.json with re_engagement_campaign_id: {cid}")
    return cid


# ── Main: process one project ──

def process_project(project_name, project_cfg, all_campaigns):
    now = datetime.now(timezone.utc)

    campaign_match = project_cfg.get("campaign_match", [])
    segments = project_cfg.get("segments", {})
    exclude_kw = project_cfg.get("exclude_keywords", defaults.get("exclude_keywords", []))
    days_after_return = project_cfg.get("days_after_return", defaults.get("days_after_return", 7))
    fallback_days = project_cfg.get("fallback_days", defaults.get("fallback_days", 21))

    print(f"\n{'='*60}")
    print(f"PROJECT: {project_name}")
    print(f"{'='*60}")
    print(f"Logic: return_date + {days_after_return}d / fallback reply + {fallback_days}d")

    state = load_state(project_name)

    # Collect re-engagement campaign IDs
    re_ids = set()
    for seg_cfg in segments.values():
        rid = seg_cfg.get("re_engagement_campaign_id")
        if rid:
            re_ids.add(rid)

    # ── Step 0: Find project campaigns ──
    print(f"\nDiscovering {project_name} campaigns...")
    segment_campaigns = {seg: [] for seg in segments}

    for c in all_campaigns:
        name = c.get("name", "")
        cid = c.get("id", 0)

        if cid in re_ids:
            continue

        # Check if campaign belongs to this project
        if not any(m in name for m in campaign_match):
            continue

        # Check excludes
        name_upper = name.upper()
        if any(kw.upper() in name_upper for kw in exclude_kw):
            continue

        # Assign to segment
        assigned = False
        for seg_name, seg_cfg in segments.items():
            seg_keywords = seg_cfg.get("keywords", [])
            if not seg_keywords:
                # Empty keywords = catch-all (ALL segment)
                segment_campaigns[seg_name].append((cid, name))
                assigned = True
                break
            if any(kw.upper() in name_upper for kw in seg_keywords):
                segment_campaigns[seg_name].append((cid, name))
                assigned = True
                break

    for seg_name, camps in segment_campaigns.items():
        re_id = segments[seg_name].get("re_engagement_campaign_id")
        status = f"-> #{re_id}" if re_id else "-> NO re-engagement campaign"
        print(f"  {seg_name}: {len(camps)} campaigns {status}")

    # Check if any segments have campaigns but no re-engagement
    active_segments = {}
    for seg_name, seg_cfg in segments.items():
        re_id = seg_cfg.get("re_engagement_campaign_id")
        camps = segment_campaigns.get(seg_name, [])
        if not camps:
            continue
        if not re_id:
            if CREATE_RE:
                re_id = create_reengagement_campaign(project_name, seg_name)
                seg_cfg["re_engagement_campaign_id"] = re_id
                re_ids.add(re_id)
            else:
                print(f"  WARNING: {seg_name} has {len(camps)} campaigns but no re-engagement. Run with --create-re to create one.")
                continue
        active_segments[seg_name] = seg_cfg

    if not active_segments:
        print(f"  No active segments with re-engagement campaigns. Skipping.")
        return {"project": project_name, "uploaded": 0, "waiting": 0, "ooo_total": 0}

    # ── Step 1: Existing leads + repeat OOO ──
    print(f"\nChecking re-engagement campaigns...")
    existing_emails = {}
    repeat_ooo_data = {}  # email -> {"re_cid": int, "re_lead_id": int, "reply_date": datetime}

    for seg_name, seg_cfg in active_segments.items():
        re_id = seg_cfg["re_engagement_campaign_id"]

        all_emails = set()
        email_to_re_lead_id = {}
        offset = 0
        while True:
            resp = get(f"/campaigns/{re_id}/leads", {"limit": 100, "offset": offset})
            leads = resp if isinstance(resp, list) else resp.get("leads", resp.get("data", []))
            if not leads:
                break
            for l in leads:
                lead = l.get("lead", l)
                email = (lead.get("email") or "").lower()
                lid = lead.get("id")
                if email:
                    all_emails.add(email)
                    if lid:
                        email_to_re_lead_id[email] = lid
            if len(leads) < 100:
                break
            offset += 100

        repeat_ooo = set()
        offset = 0
        while True:
            try:
                resp = get(f"/campaigns/{re_id}/statistics", {"limit": 500, "offset": offset})
                data = resp if isinstance(resp, list) else resp.get("data", [])
            except Exception as e:
                print(f"  [{seg_name}] re-engagement stats error: {e}")
                break
            if not data:
                break
            for row in data:
                if row.get("lead_category") == "Out Of Office":
                    email = (row.get("lead_email") or "").lower()
                    if not email:
                        continue
                    repeat_ooo.add(email)
                    reply_date = parse_date(row.get("reply_time") or row.get("sent_time"))
                    re_lead_id = email_to_re_lead_id.get(email)
                    if re_lead_id:
                        repeat_ooo_data[email] = {
                            "re_cid": re_id,
                            "re_lead_id": re_lead_id,
                            "reply_date": reply_date,
                            "segment": seg_name,
                        }
            if len(data) < 500:
                break
            offset += 500

        existing_emails[seg_name] = all_emails - repeat_ooo
        print(f"  {seg_name}: {len(all_emails)} in re-engagement, {len(repeat_ooo)} repeat OOO")

    # ── Step 2: Collect OOO leads ──
    print(f"\nScanning for OOO leads...")
    ooo_leads = {}
    email_to_lead_id = {}

    for seg_name in active_segments:
        for cid, cname in segment_campaigns.get(seg_name, []):
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
                            "segment": seg_name,
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
            print(f"  [{seg_name}] [{cid}] {cname}: {len(ooo_emails_in_camp)} OOO")

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

    print(f"\n  Total OOO: {len(ooo_leads)}, need parsing: {len(email_to_lead_id)}")

    # ── Step 3: Parse return dates ──
    new_parsed = 0
    cached = 0
    no_date = 0
    reparsed_repeat = 0

    for email, lead in ooo_leads.items():
        repeat = repeat_ooo_data.get(email)

        # For repeat OOO: bypass cache, parse the latest OOO body from re-engagement
        if repeat:
            re_cid = repeat["re_cid"]
            re_lid = repeat["re_lead_id"]
            body = fetch_ooo_reply_text(re_cid, re_lid)
            return_date = extract_return_date(body, repeat.get("reply_date"))
            lead["return_date"] = return_date
            # Override reply_date with latest from re-engagement so fallback uses fresh date
            if repeat.get("reply_date"):
                lead["reply_date"] = repeat["reply_date"]
                lead["reply_date_str"] = repeat["reply_date"].isoformat()[:10]
            state[email] = {
                "parsed": True,
                "return_date": return_date.isoformat() if return_date else None,
                "reply_date": lead["reply_date"].isoformat() if lead.get("reply_date") else None,
                "segment": lead["segment"],
                "name": lead["name"],
                "ooo_snippet": (strip_html(body)[:100] if body else ""),
                "repeat_ooo": True,
            }
            reparsed_repeat += 1
            if return_date:
                print(f"    [REPEAT] {email}: returns {return_date.strftime('%Y-%m-%d')}")
            continue

        if email in state and state[email].get("return_date"):
            lead["return_date"] = parse_date(state[email]["return_date"])
            cached += 1
            continue
        if email in state and state[email].get("parsed"):
            lead["return_date"] = None
            cached += 1
            continue

        campaign_id = lead.get("campaign_id")
        lead_id = email_to_lead_id.get((campaign_id, email))
        if not lead_id:
            lead["return_date"] = None
            no_date += 1
            continue

        body = fetch_ooo_reply_text(campaign_id, lead_id)
        return_date = extract_return_date(body, lead.get("reply_date"))
        lead["return_date"] = return_date

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
            print(f"    {email}: returns {return_date.strftime('%Y-%m-%d')}")
        else:
            no_date += 1

    save_state(project_name, state)
    if new_parsed or no_date or reparsed_repeat:
        print(f"  Parsed: {new_parsed} new, {cached} cached, {no_date} no date, {reparsed_repeat} repeat re-parsed")

    # ── Step 4: Filter ready leads ──
    to_upload = {}
    waiting_leads = []
    skipped_existing = 0

    for email, lead in ooo_leads.items():
        seg = lead["segment"]
        if seg not in active_segments:
            continue
        if email in existing_emails.get(seg, set()):
            skipped_existing += 1
            continue

        return_date = lead.get("return_date")
        reply_date = lead.get("reply_date")

        if return_date:
            ready_date = return_date + timedelta(days=days_after_return)
            source = f"return {return_date.strftime('%m/%d')} + {days_after_return}d"
        elif reply_date:
            ready_date = reply_date + timedelta(days=fallback_days)
            source = f"reply {reply_date.strftime('%m/%d')} + {fallback_days}d"
        else:
            ready_date = now - timedelta(days=1)
            source = "no dates"

        if ready_date <= now:
            to_upload.setdefault(seg, []).append(lead)
        else:
            days_left = (ready_date - now).days
            waiting_leads.append(f"{email} [{seg}] (~{days_left}d - {source})")

    total_ready = sum(len(v) for v in to_upload.values())
    print(f"\n  Already in re-engagement: {skipped_existing}")
    print(f"  Waiting: {len(waiting_leads)}")
    print(f"  Ready to upload: {total_ready}")

    # ── Step 5: Upload ──
    total_uploaded = 0
    upload_summary = []

    for seg, leads in to_upload.items():
        re_id = active_segments[seg]["re_engagement_campaign_id"]

        action = "[DRY RUN] Would upload" if DRY_RUN else "Uploading"
        print(f"\n  {action} {len(leads)} [{seg}] -> #{re_id}")

        for lead in leads:
            ret = lead.get("return_date")
            src = f"ret {ret.strftime('%m/%d')}+{days_after_return}d" if ret else f"fb {fallback_days}d"
            tag = "[REPEAT]" if lead["email"] in repeat_ooo_data else ""
            print(f"    {tag}{lead['email']} ({lead['name']}) - {src}")
            upload_summary.append(f"{lead['name']} ({lead['email']}) [{seg}]")

        if DRY_RUN:
            total_uploaded += len(leads)
            continue

        # Step 5a: Delete repeat OOO leads from re-engagement so POST can re-add fresh
        repeat_in_batch = [l for l in leads if l["email"] in repeat_ooo_data]
        if repeat_in_batch:
            print(f"    Deleting {len(repeat_in_batch)} repeat OOO leads before re-upload...")
            deleted_count = 0
            for lead in repeat_in_batch:
                rd = repeat_ooo_data[lead["email"]]
                res = delete(f"/campaigns/{rd['re_cid']}/leads/{rd['re_lead_id']}")
                if res is not None:
                    deleted_count += 1
            print(f"    Deleted: {deleted_count}/{len(repeat_in_batch)}")

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
            uploaded = resp.get("upload_count", 0)
            already = resp.get("already_added_to_campaign", 0)
            invalid = resp.get("invalid_email_count", 0)
            total_uploaded += uploaded
            print(f"    API response: upload_count={uploaded}, already_added={already}, invalid={invalid}")
            if uploaded < len(lead_list) - already - invalid:
                print(f"    WARNING: sent {len(lead_list)} leads, only {uploaded} accepted")
        except Exception as e:
            print(f"    Upload error: {e}")

    return {
        "project": project_name,
        "uploaded": total_uploaded,
        "waiting": len(waiting_leads),
        "ooo_total": len(ooo_leads),
        "upload_summary": upload_summary,
        "waiting_leads": waiting_leads,
    }


# ── Run ──

now = datetime.now(timezone.utc)
mode = "DRY RUN" if DRY_RUN else "LIVE"
print(f"[{now.strftime('%Y-%m-%d %H:%M')} UTC] Universal OOO sync ({mode})")
print(f"Projects: {', '.join(project_names)}\n")

# Fetch all campaigns once (shared across projects)
all_campaigns = get("/campaigns")
if isinstance(all_campaigns, dict):
    all_campaigns = all_campaigns.get("campaigns", all_campaigns.get("data", []))
print(f"Total campaigns in SmartLead: {len(all_campaigns)}")

# Process each project
results = []
for pn in project_names:
    result = process_project(pn, all_projects[pn], all_campaigns)
    results.append(result)

# ── Summary + Telegram ──
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")

tg_lines = []
has_uploads = False

for r in results:
    proj = r["project"]
    uploaded = r["uploaded"]
    waiting = r["waiting"]
    total = r["ooo_total"]

    status = f"  {proj}: {total} OOO, {uploaded} uploaded, {waiting} waiting"
    print(status)

    if uploaded > 0:
        has_uploads = True
        names = "\n".join(f"  - {s}" for s in r.get("upload_summary", []))
        tg_lines.append(f"{proj}: +{uploaded} uploaded, {waiting} waiting, {total} total OOO\n{names}")
    else:
        tg_lines.append(f"{proj}: 0 uploaded, {waiting} waiting, {total} total OOO")

if DRY_RUN:
    print(f"\n[DRY RUN] No changes made.")
    sys.exit(0)

if not NO_TG:
    emoji = "✅" if has_uploads else "📭"
    tg(f"{emoji} OOO Sync - {now.strftime('%d.%m.%Y')}\n\n" + "\n\n".join(tg_lines))

print("\nDone.")
