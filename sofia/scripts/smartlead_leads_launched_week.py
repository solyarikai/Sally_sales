#!/usr/bin/env python3
"""
SmartLead — Leads Launched This Week (OnSocial campaigns)
Counts unique leads added to OnSocial campaigns this week (Mon–Sun).
"""

import os
import time
import json
from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# This week: Monday 00:00 UTC
NOW = datetime.now(timezone.utc)
# Get Monday of current week
WEEK_START = NOW - timedelta(days=NOW.weekday())
WEEK_START = WEEK_START.replace(hour=0, minute=0, second=0, microsecond=0)


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    if resp.status_code == 429:
        print("  Rate limited, waiting 5s...")
        time.sleep(5)
        resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_all_campaigns():
    data = api_get("/campaigns")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("campaigns", []))
    return []


def get_campaign_leads(campaign_id):
    """Fetch all leads from a campaign with pagination."""
    all_leads = []
    offset = 0
    limit = 100
    while True:
        data = api_get(f"/campaigns/{campaign_id}/leads", {"offset": offset, "limit": limit})
        if not data:
            break
        # Response can be a list or dict
        if isinstance(data, list):
            leads = data
        elif isinstance(data, dict):
            leads = data.get("data", data.get("leads", []))
        else:
            break
        if not leads:
            break
        all_leads.extend(leads)
        if len(leads) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return all_leads


def parse_time(s):
    if not s:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def main():
    print("=" * 65)
    print(f"  LEADS LAUNCHED THIS WEEK — {WEEK_START.strftime('%a %b %d')} to {NOW.strftime('%a %b %d, %Y')}")
    print("=" * 65)

    all_campaigns = get_all_campaigns()
    onsocial = [c for c in all_campaigns if "onsocial" in c.get("name", "").lower()]
    print(f"Total campaigns: {len(all_campaigns)} | OnSocial: {len(onsocial)}\n")

    results = []
    grand_total = 0

    for camp in onsocial:
        cid = camp["id"]
        cname = camp.get("name", f"#{cid}")
        status = camp.get("status", "?")
        print(f"  [{status:>8}] {cname[:50]}...", end=" ", flush=True)

        try:
            leads = get_campaign_leads(cid)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Count leads added this week
        this_week = []
        for lead in leads:
            # Try created_at, added_at, or updated_at
            ts = lead.get("created_at") or lead.get("added_at") or lead.get("updated_at")
            dt = parse_time(ts)
            if dt and dt >= WEEK_START:
                this_week.append(lead)

        count = len(this_week)
        total_leads = len(leads)
        grand_total += count
        print(f"{count} new ({total_leads} total)")

        if count > 0:
            results.append({
                "campaign": cname,
                "id": cid,
                "status": status,
                "leads_this_week": count,
                "total_leads": total_leads,
            })

        time.sleep(0.2)

    # Sort by count
    results.sort(key=lambda x: x["leads_this_week"], reverse=True)

    print()
    print("=" * 65)
    print(f"{'Campaign':<50} {'New':>5} {'Total':>7}")
    print("-" * 65)
    for r in results:
        name = r["campaign"][:49]
        print(f"{name:<50} {r['leads_this_week']:>5} {r['total_leads']:>7}")
    print("-" * 65)
    print(f"{'TOTAL LEADS LAUNCHED THIS WEEK':<50} {grand_total:>5}")
    print()
    print(f"  Week: {WEEK_START.strftime('%Y-%m-%d')} (Mon) — {NOW.strftime('%Y-%m-%d')} (today)")


if __name__ == "__main__":
    main()
