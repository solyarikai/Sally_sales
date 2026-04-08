#!/usr/bin/env python3
"""
Verify that the 115 PAUSE actions from OS_Dedup_Plan_2026-04-08.csv
were actually executed in SmartLead.

Fetches all leads from each affected campaign, checks if target lead_ids
are currently PAUSED.

Usage:
  python3.11 sofia/scripts/verify_dedup_pauses.py
"""

import csv
import json
import ssl
import time
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
SSL_CTX = ssl._create_unverified_context()

PLAN_PATH = (
    Path(__file__).resolve().parent.parent
    / "output"
    / "OnSocial"
    / "OS_Dedup_Plan_2026-04-08.csv"
)
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "output"
    / "OnSocial"
    / "OS_Dedup_Verify_2026-04-08.json"
)


def api_get(endpoint, params=None):
    qs = f"api_key={API_KEY}"
    if params:
        for k, v in params.items():
            qs += f"&{k}={v}"
    url = f"{BASE_URL}{endpoint}?{qs}"
    req = Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
    for attempt in range(5):
        try:
            with urlopen(req, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(0.4)
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"  [429] rate limit, waiting {wait}s...")
                time.sleep(wait)
                continue
            body = e.read().decode() if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {body[:200]}"}
    return {"error": "max retries exceeded"}


def fetch_campaign_leads(campaign_id: int) -> dict[int, dict]:
    """Fetch all leads in a campaign. Returns {lead_id: lead_obj}."""
    all_leads = {}
    offset = 0
    limit = 100
    while True:
        data = api_get(
            f"/campaigns/{campaign_id}/leads",
            {"offset": offset, "limit": limit},
        )
        if data.get("error"):
            print(f"  ERROR fetching campaign {campaign_id}: {data['error']}")
            break

        if isinstance(data, dict):
            rows = data.get("data", [])
            total = int(data.get("total_leads", data.get("total", 0)))
        elif isinstance(data, list):
            rows = data
            total = len(data)
        else:
            break

        if not rows:
            break

        for row in rows:
            # API structure: {campaign_lead_map_id, status, lead: {id, email, ...}}
            nested = row.get("lead") or row
            lead_id = nested.get("id") or nested.get("lead_id") or row.get("lead_id")
            if lead_id:
                all_leads[int(lead_id)] = {
                    "status": row.get("status", "UNKNOWN"),
                    "lead_category_id": row.get("lead_category_id"),
                    "email": nested.get("email", ""),
                }

        print(f"  Fetched {len(all_leads)}/{total} leads from campaign {campaign_id}")

        if len(all_leads) >= total or len(leads) < limit:
            break
        offset += limit

    return all_leads


def load_pause_actions():
    pauses = []
    with open(PLAN_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["action"] == "pause":
                pauses.append(
                    {
                        "email": row["email"],
                        "campaign_id": int(row["campaign_id"]),
                        "campaign_name": row["campaign_name"],
                        "lead_id": int(row["lead_id"]),
                        "reason": row["reason"],
                    }
                )
    return pauses


def main():
    pauses = load_pause_actions()
    print(f"Dedup plan: {len(pauses)} PAUSE actions across campaigns")

    # Group pause actions by campaign
    by_campaign = defaultdict(list)
    for p in pauses:
        by_campaign[p["campaign_id"]].append(p)

    print(f"Unique campaigns to check: {len(by_campaign)}")
    print()

    paused_ok = []
    not_paused = []
    errors = []

    for campaign_id, actions in by_campaign.items():
        campaign_name = actions[0]["campaign_name"]
        print(f"Campaign {campaign_id} — {campaign_name}")
        print("  Fetching all leads...")

        all_leads = fetch_campaign_leads(campaign_id)

        if not all_leads:
            print(f"  ERROR: could not fetch leads for campaign {campaign_id}")
            for a in actions:
                errors.append({**a, "sl_status": "FETCH_ERROR"})
            continue

        # Now check each target lead_id
        for a in actions:
            lead_id = a["lead_id"]
            lead = all_leads.get(lead_id)

            if lead is None:
                # Lead not found in campaign — might have been deleted or lead_id is wrong
                entry = {**a, "sl_status": "NOT_FOUND_IN_CAMPAIGN"}
                errors.append(entry)
                print(
                    f"  NOT_FOUND  {a['email']:45s} (lead_id={lead_id} not in campaign)"
                )
                continue

            # Check status field — SmartLead uses 'status' on the lead object
            # Possible values vary; look for 'isPaused', 'status', 'lead_status'
            sl_status = (
                lead.get("status")
                or lead.get("lead_status")
                or lead.get("email_status")
                or "UNKNOWN"
            )
            is_paused_flag = lead.get("isPaused") or lead.get("is_paused")

            is_paused = (
                str(sl_status).upper() in ("PAUSED", "PAUSE") or is_paused_flag is True
            )

            entry = {
                **a,
                "sl_status": sl_status,
                "is_paused_flag": is_paused_flag,
                "raw_keys": list(lead.keys())[:10],
            }

            if is_paused:
                paused_ok.append(entry)
                print(f"  OK (PAUSED) {a['email']:45s}")
            else:
                not_paused.append(entry)
                print(
                    f"  ⚠ ACTIVE   {a['email']:45s} → status={sl_status}, isPaused={is_paused_flag}"
                )

        print()

    # Print a sample lead structure so we know what fields are available
    print("=" * 60)
    print(f"TOTAL PAUSE ACTIONS: {len(pauses)}")
    print(f"  Confirmed PAUSED:  {len(paused_ok)}")
    print(f"  NOT paused/ACTIVE: {len(not_paused)}")
    print(f"  Errors/not found:  {len(errors)}")

    if not_paused:
        print()
        print("NEEDS ATTENTION (still active):")
        for r in not_paused:
            print(f"  {r['email']:45s} camp={r['campaign_id']} status={r['sl_status']}")

    if errors:
        print()
        print("ERRORS/NOT FOUND:")
        for r in errors:
            print(f"  {r['email']:45s} → {r['sl_status']}")

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "summary": {
                    "total": len(pauses),
                    "paused_ok": len(paused_ok),
                    "not_paused": len(not_paused),
                    "errors": len(errors),
                },
                "not_paused": not_paused,
                "paused_ok": [
                    {"email": r["email"], "campaign_name": r["campaign_name"]}
                    for r in paused_ok
                ],
                "errors": errors,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
