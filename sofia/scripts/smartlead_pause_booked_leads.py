#!/usr/bin/env python3
"""Auto-pause leads with 'Meeting Booked' or 'Qualified' in OnSocial campaigns.

Runs daily before sending windows start. Finds leads in active OnSocial
campaigns that have been categorized as Meeting Booked or Qualified,
and pauses them per-campaign (NOT global unsubscribe) so they stop
receiving cold outreach but remain contactable in other projects.

Sends a Telegram report via @ImpecableBot after execution.

Usage:
    python3 smartlead_pause_booked_leads.py              # dry-run (default)
    python3 smartlead_pause_booked_leads.py --execute     # actually pause
    python3 smartlead_pause_booked_leads.py --verbose     # show all leads checked
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
RATE_LIMIT_PAUSE = 0.35

# Telegram @ImpecableBot
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7380803777")

# Categories that mean "don't send more cold emails"
PAUSE_CATEGORY_IDS = {
    77598,  # Meeting Booked
    77597,  # Qualified
}

PAUSE_CATEGORY_NAMES = {
    77598: "Meeting Booked",
    77597: "Qualified",
}

# Only process campaigns matching this filter
CAMPAIGN_FILTER = "onsocial"

# Ghost campaigns: exist in API as ACTIVE but deleted/missing in UI
SKIP_CAMPAIGN_IDS = {
    3078491,  # c-OnSocial_Re-engagement (ghost — never ran, 213 drafted leads)
}


def _request(url, method="GET", body=None, retries=3):
    """Execute HTTP request with retry on 429."""
    data_bytes = json.dumps(body).encode("utf-8") if body else None
    for attempt in range(retries):
        req = Request(url, data=data_bytes, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
        try:
            with urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(RATE_LIMIT_PAUSE)
                if not raw.strip():
                    return {}
                return json.loads(raw)
        except HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def api_get(endpoint, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="GET")


def api_post(endpoint, body=None, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
    return _request(url, method="POST", body=body)


def send_telegram(message):
    """Send message to Telegram via @ImpecableBot."""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN missing), skipping notification")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        body = {
            "chat_id": TG_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("Telegram notification sent")
            else:
                print(f"Telegram error: {result}")
    except Exception as e:
        print(f"Telegram send failed: {e}")


def get_active_onsocial_campaigns():
    """Fetch all active campaigns with 'onsocial' in the name."""
    data = api_get("/campaigns/", {"include_tags": "true"})
    campaigns = data if isinstance(data, list) else data.get("campaigns", data)
    return [
        c for c in campaigns
        if CAMPAIGN_FILTER in c.get("name", "").lower()
        and c.get("status", "").upper() == "ACTIVE"
        and c.get("id") not in SKIP_CAMPAIGN_IDS
    ]


def get_campaign_leads(campaign_id):
    """Fetch all leads from a campaign (paginated)."""
    all_leads = []
    offset = 0
    limit = 100
    while True:
        resp = api_get(f"/campaigns/{campaign_id}/leads", {
            "offset": offset,
            "limit": limit,
        })
        # API returns {"data": [...], "total_leads": "N", ...}
        data = resp.get("data", []) if isinstance(resp, dict) else resp
        if not data:
            break
        all_leads.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_leads


def pause_lead(campaign_id, lead_id):
    """Pause a lead in a specific campaign."""
    return api_post(f"/campaigns/{campaign_id}/leads/{lead_id}/pause")


def main():
    parser = argparse.ArgumentParser(description="Pause Meeting Booked / Qualified leads in OnSocial campaigns")
    parser.add_argument("--execute", action="store_true", help="Actually pause leads (default is dry-run)")
    parser.add_argument("--verbose", action="store_true", help="Show all leads being checked")
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] SmartLead Auto-Pause - {mode}")
    print(f"Categories to pause: {list(PAUSE_CATEGORY_NAMES.values())}")
    print()

    # 1. Get active OnSocial campaigns
    campaigns = get_active_onsocial_campaigns()
    print(f"Found {len(campaigns)} active OnSocial campaigns")
    print()

    total_paused = 0
    total_already_paused = 0
    total_checked = 0
    log = []

    for camp in campaigns:
        cid = camp["id"]
        cname = camp["name"]
        print(f"--- {cname} (ID: {cid}) ---")

        # 2. Get all leads
        leads = get_campaign_leads(cid)
        total_checked += len(leads)

        if args.verbose:
            print(f"  Total leads: {len(leads)}")

        paused_in_campaign = 0
        for lead_entry in leads:
            cat_id = lead_entry.get("lead_category_id")
            status = lead_entry.get("status", "")
            lead = lead_entry.get("lead", {})
            lead_id = lead.get("id")
            email = lead.get("email", "")
            name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()

            if cat_id not in PAUSE_CATEGORY_IDS:
                continue

            cat_name = PAUSE_CATEGORY_NAMES.get(cat_id, str(cat_id))

            # Skip if already paused or completed
            if status in ("PAUSED", "COMPLETED", "BLOCKED"):
                total_already_paused += 1
                if args.verbose:
                    print(f"  SKIP ({status.lower()}): {name} <{email}> [{cat_name}]")
                continue

            # 3. Pause
            print(f"  PAUSE: {name} <{email}> [{cat_name}] (status was: {status})")
            log.append({
                "campaign": cname,
                "campaign_id": cid,
                "lead_id": lead_id,
                "email": email,
                "name": name,
                "category": cat_name,
                "prev_status": status,
            })

            if args.execute:
                try:
                    result = pause_lead(cid, lead_id)
                    if result.get("ok"):
                        total_paused += 1
                        paused_in_campaign += 1
                    else:
                        print(f"    WARN: unexpected response: {result}")
                except Exception as e:
                    print(f"    ERROR pausing {email}: {e}")
            else:
                total_paused += 1
                paused_in_campaign += 1

        if paused_in_campaign > 0:
            print(f"  -> Paused: {paused_in_campaign}")
        else:
            print(f"  -> Nothing to pause")
        print()

    # Summary
    print("=" * 60)
    print(f"SUMMARY ({mode})")
    print(f"  Campaigns checked:  {len(campaigns)}")
    print(f"  Leads checked:      {total_checked}")
    print(f"  Leads paused:       {total_paused}")
    print(f"  Already paused/done:{total_already_paused}")

    if log:
        print("\nPaused leads:")
        for entry in log:
            print(f"  {entry['name']} <{entry['email']}> - {entry['category']} - {entry['campaign']}")

    if not args.execute and total_paused > 0:
        print("\nThis was a DRY RUN. To actually pause, run with --execute")

    # 4. Send Telegram notification (only in execute mode)
    if args.execute:
        tg_lines = [f"<b>OnSocial Auto-Pause</b> - {now}"]
        tg_lines.append(f"Campaigns: {len(campaigns)} | Leads checked: {total_checked}")

        if total_paused > 0:
            tg_lines.append(f"\n<b>Paused {total_paused} leads:</b>")
            for entry in log:
                short_campaign = entry["campaign"].replace("c-OnSocial_", "")
                tg_lines.append(f"  {entry['name']} ({entry['email']}) - {entry['category']} - {short_campaign}")
        else:
            tg_lines.append("\nNo new leads to pause today")

        if total_already_paused > 0:
            tg_lines.append(f"\nAlready paused/done: {total_already_paused}")

        send_telegram("\n".join(tg_lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
