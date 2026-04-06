#!/usr/bin/env python3
"""
Daily cron: sync OOO leads from INFPLAT campaigns into re-engagement.

Logic:
- Fetch all OOO leads from all OnSocial INFPLAT campaigns
- Skip leads already in c-OnSocial_Re-engagement_INFPLAT
- Upload only those where reply_time >= 14 days ago (ready to re-engage)
- Leads with no reply_time: use sent_time + 14 days fallback

Run daily via cron (6:00 UTC = 9:00 MSK):
  0 6 * * * cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_infplat_ooo_sync.py >> /tmp/infplat_ooo_sync.log 2>&1
"""

import httpx
import os
import sys
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("SMARTLEAD_API_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7380803777")
BASE = "https://server.smartlead.ai/api/v1"
REENGAGEMENT_CAMPAIGN_ID = 3123881

INFPLAT_KEYWORDS = ["INFLUENCER PLATFORMS", "INFPLAT", "PLATFORM"]
INFPLAT_EXCLUDE_KEYWORDS = ["Re-engagement", "iGaming", "trading", "GWC", "Inxy", "Gcore",
                             "SquareFi", "Deliryo", "CrowdControl", "gaming"]

if not KEY:
    print("ERROR: SMARTLEAD_API_KEY not set")
    sys.exit(1)


def get(path, params=None):
    p = {"api_key": KEY}
    if params:
        p.update(params)
    r = httpx.get(f"{BASE}{path}", params=p, timeout=60)
    r.raise_for_status()
    return r.json()


def post(path, data, timeout=30):
    r = httpx.post(f"{BASE}{path}", params={"api_key": KEY}, json=data, timeout=timeout)
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


now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=14)
print(f"[{now.strftime('%Y-%m-%d %H:%M')} UTC] Running INFPLAT OOO sync")
print(f"Cutoff: leads replied before {cutoff.strftime('%Y-%m-%d')} are ready to re-engage\n")

# ── Step 0: Discover INFPLAT campaigns dynamically ──
print("Discovering INFPLAT campaigns...")
all_camps = get("/campaigns")
if isinstance(all_camps, dict):
    all_camps = all_camps.get("campaigns", all_camps.get("data", []))

INFPLAT_CAMPAIGN_IDS = []
for c in all_camps:
    name = c.get("name", "")
    name_upper = name.upper()
    if c["id"] == REENGAGEMENT_CAMPAIGN_ID:
        continue
    if any(kw.upper() in name_upper for kw in INFPLAT_EXCLUDE_KEYWORDS):
        continue
    if any(kw.upper() in name_upper for kw in INFPLAT_KEYWORDS):
        INFPLAT_CAMPAIGN_IDS.append((c["id"], name))

print(f"  Found {len(INFPLAT_CAMPAIGN_IDS)} INFPLAT campaigns:")
for cid, cname in sorted(INFPLAT_CAMPAIGN_IDS):
    print(f"    [{cid}] {cname}")
print()

# ── Step 1: Get emails already in re-engagement ──
print("Fetching leads already in re-engagement campaign...")
existing_emails = set()
offset = 0
while True:
    resp = get(f"/campaigns/{REENGAGEMENT_CAMPAIGN_ID}/leads", {"limit": 100, "offset": offset})
    leads = resp if isinstance(resp, list) else resp.get("leads", resp.get("data", []))
    if not leads:
        break
    for l in leads:
        lead = l.get("lead", l)
        email = lead.get("email", "")
        if email:
            existing_emails.add(email.lower())
    if len(leads) < 100:
        break
    offset += 100
print(f"  Already in re-engagement: {len(existing_emails)} leads\n")

# ── Step 2: Collect OOO leads from all INFPLAT campaigns ──
ooo_leads = {}  # email -> best row

for cid, cname in INFPLAT_CAMPAIGN_IDS:
    offset = 0
    camp_count = 0
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
            # Use reply_time, fall back to sent_time
            date_str = row.get("reply_time") or row.get("sent_time")
            lead_date = parse_date(date_str)
            # Keep earliest date per email (first OOO occurrence)
            if email not in ooo_leads or (lead_date and lead_date < (ooo_leads[email]["date"] or now)):
                ooo_leads[email] = {
                    "email": email,
                    "name": row.get("lead_name", ""),
                    "campaign": cname,
                    "date": lead_date,
                    "date_str": (date_str or "")[:10],
                }
                camp_count += 1
        if len(data) < 500:
            break
        offset += 500
    if camp_count:
        print(f"  [{cid}] {cname}: {camp_count} OOO")

print(f"\nTotal unique OOO leads found: {len(ooo_leads)}")

# ── Step 3: Filter — not already in re-engagement, 14 days passed ──
to_upload = []
skipped_already_added = []
skipped_too_recent = []

for email, lead in ooo_leads.items():
    if email in existing_emails:
        skipped_already_added.append(email)
        continue
    lead_date = lead["date"]
    if lead_date is None or lead_date <= cutoff:
        to_upload.append(lead)
    else:
        days_left = (lead_date + timedelta(days=14) - now).days
        skipped_too_recent.append(f"{email} (ready in ~{days_left}d)")

print(f"  Already in re-engagement: {len(skipped_already_added)}")
print(f"  Too recent (<14 days):    {len(skipped_too_recent)}")
print(f"  Ready to upload:          {len(to_upload)}")

if skipped_too_recent:
    print("\nWaiting (not yet 14 days):")
    for s in skipped_too_recent:
        print(f"  - {s}")

if not to_upload:
    print("\nNothing to upload today.")
    # Still report waiting leads if any
    if skipped_too_recent:
        waiting_lines = "\n".join(f"  • {s}" for s in skipped_too_recent)
        tg(
            f"📭 INFPLAT OOO sync — {now.strftime('%d.%m.%Y')}\n\n"
            f"Новых лидов для re-engagement нет.\n\n"
            f"Ждут (ещё не 14 дней):\n{waiting_lines}"
        )
    else:
        tg(f"📭 INFPLAT OOO sync — {now.strftime('%d.%m.%Y')}\nОчередь пуста, новых OOO нет.")
    sys.exit(0)

# ── Step 4: Upload ──
print(f"\nUploading {len(to_upload)} leads to re-engagement...")
lead_list = []
for lead in to_upload:
    parts = lead["name"].split(" ", 1)
    entry = {
        "email": lead["email"],
        "first_name": parts[0] if parts else "",
        "last_name": parts[1] if len(parts) > 1 else "",
    }
    lead_list.append(entry)

resp = post(f"/campaigns/{REENGAGEMENT_CAMPAIGN_ID}/leads", {"lead_list": lead_list}, timeout=60)
uploaded = resp.get("upload_count", len(lead_list))
dupes = resp.get("duplicate_count", 0)
print(f"  Uploaded: {uploaded}, duplicates skipped: {dupes}")

print("\nUploaded leads:")
for lead in to_upload:
    print(f"  - {lead['email']} ({lead['name']}) — OOO date: {lead['date_str']}")

# ── Telegram notification ──
uploaded_lines = "\n".join(
    f"  • {l['name']} ({l['email']}) — OOO: {l['date_str']}"
    for l in to_upload
)
waiting_lines = ""
if skipped_too_recent:
    waiting_lines = "\n\nЕщё ждут:\n" + "\n".join(f"  • {s}" for s in skipped_too_recent)

tg(
    f"✅ INFPLAT OOO → Re-engagement — {now.strftime('%d.%m.%Y')}\n\n"
    f"Добавлено в кампанию: {uploaded}\n\n"
    f"{uploaded_lines}"
    f"{waiting_lines}"
)

print(f"\nDone. Next run tomorrow.")
