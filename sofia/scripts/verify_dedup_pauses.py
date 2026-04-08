#!/usr/bin/env python3
"""
Verify that the 115 PAUSE actions from OS_Dedup_Plan_2026-04-08.csv
were actually executed in SmartLead.

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


def api_get(endpoint, params=""):
    url = f"{BASE_URL}{endpoint}?api_key={API_KEY}"
    if params:
        url += f"&{params}"
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
                print(f"  429 rate limit, waiting {wait}s...")
                time.sleep(wait)
                continue
            body = e.read().decode() if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {body}"}
    return {"error": "max retries exceeded"}


def load_pause_actions():
    """Load all PAUSE rows from the dedup plan."""
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


def check_lead_status(campaign_id: int, lead_id: int) -> dict:
    """
    Fetch lead status from SmartLead.
    SmartLead API: GET /campaigns/{campaign_id}/leads/{lead_id}
    Returns the lead object with 'status' field.
    """
    data = api_get(f"/campaigns/{campaign_id}/leads/{lead_id}")
    return data


def main():
    pauses = load_pause_actions()
    print(f"Checking {len(pauses)} PAUSE actions from dedup plan...")
    print()

    results = []
    paused_ok = []
    not_paused = []
    errors = []

    # Group by campaign to minimize API calls (if we need to batch)
    by_campaign = defaultdict(list)
    for p in pauses:
        by_campaign[p["campaign_id"]].append(p)

    total = len(pauses)
    done = 0

    for campaign_id, leads in by_campaign.items():
        campaign_name = leads[0]["campaign_name"]
        print(f"Campaign {campaign_id} — {campaign_name} ({len(leads)} leads)")

        for p in leads:
            done += 1
            data = check_lead_status(campaign_id, p["lead_id"])

            if data.get("error"):
                status = "API_ERROR"
                detail = data["error"]
                errors.append({**p, "sl_status": status, "detail": detail})
                print(f"  [{done}/{total}] ERROR {p['email']:45s} → {detail[:60]}")
            else:
                # SmartLead lead object has 'status' field: 'ACTIVE', 'PAUSED', 'COMPLETED', etc.
                sl_status = data.get("status", "UNKNOWN")
                lead_status = data.get("lead_status", "")
                entry = {
                    **p,
                    "sl_status": sl_status,
                    "lead_status": lead_status,
                    "is_replied": data.get("is_replied", False),
                }

                if sl_status == "PAUSED":
                    paused_ok.append(entry)
                    print(f"  [{done}/{total}] OK     {p['email']:45s} → PAUSED ✓")
                else:
                    not_paused.append(entry)
                    flag = "⚠ NOT PAUSED" if sl_status != "COMPLETED" else "(completed)"
                    print(
                        f"  [{done}/{total}] {flag:12s} {p['email']:45s} → {sl_status}"
                    )

            results.append(
                {
                    "email": p["email"],
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "lead_id": p["lead_id"],
                    "plan_action": "pause",
                    "sl_status": data.get("status", "API_ERROR")
                    if not data.get("error")
                    else "API_ERROR",
                    "lead_status": data.get("lead_status", "")
                    if not data.get("error")
                    else "",
                    "verified": "yes" if data.get("status") == "PAUSED" else "no",
                    "detail": data.get("error", ""),
                }
            )

        print()

    # Summary
    print("=" * 60)
    print(f"TOTAL PAUSE ACTIONS: {len(pauses)}")
    print(f"  Confirmed PAUSED:  {len(paused_ok)}")
    print(f"  NOT paused:        {len(not_paused)}")
    print(f"  API errors:        {len(errors)}")
    print()

    if not_paused:
        print("NOT PAUSED (need attention):")
        for r in not_paused:
            print(f"  {r['email']:45s} camp={r['campaign_id']} status={r['sl_status']}")

    # Save results
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
                "paused_ok": paused_ok,
                "errors": errors,
                "all_results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nResults saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
