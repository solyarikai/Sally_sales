#!/usr/bin/env python3
"""
Export non-replied leads with LinkedIn URLs from 4 SmartLead campaigns.
Produces one CSV per campaign + one combined CSV with scoring.

Usage (on Hetzner):
    set -a && source .env && set +a
    python3 sofia/scripts/getsales_export_leads.py

Output:
    sofia/get_sales_hub/2026-04-01/
        INFPLAT_MENA_APAC_leads.csv
        INFPLAT_INDIA_leads.csv
        IMAGENCY_INDIA_leads.csv
        INDIA_GENERAL_leads.csv
        ALL_CAMPAIGNS_scored.csv
"""

import os
import csv
import json
import time
import asyncio
import io
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
    import httpx

# ── Config ─────────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("SMARTLEAD_API_KEY", "")
BASE_URL = "https://server.smartlead.ai/api/v1"

CAMPAIGNS = {
    3065429: "INFPLAT_MENA_APAC",
    3059650: "INFPLAT_INDIA",
    3063527: "IMAGENCY_INDIA",
    3064966: "INDIA_GENERAL",
}

# Statuses to include (not replied)
INCLUDE_STATUSES = {"SENT", "OPENED", "NOT_CONTACTED", "EMAIL_OPENED"}

# Output dir — use absolute path relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent          # sofia/scripts/
SOFIA_DIR  = SCRIPT_DIR.parent                        # sofia/
TODAY      = datetime.now().strftime("%Y-%m-%d")
OUT_DIR    = SOFIA_DIR / "get_sales_hub" / TODAY
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Scoring ────────────────────────────────────────────────────────────────────

TITLE_SCORE = {
    # C-suite / Founder: 10
    "founder": 10, "co-founder": 10, "ceo": 10, "chief executive": 10,
    "managing director": 9, "md": 9, "president": 9,
    # VP / Head: 8
    "vp": 8, "vice president": 8, "head of": 8, "chief": 8,
    # Director: 6
    "director": 6, "gm": 6, "general manager": 6,
    # Manager / Lead: 4
    "manager": 4, "lead": 4, "principal": 4,
    # Other: 2
}

ENGAGEMENT_SCORE = {
    "OPENED": 3,   # opened email but didn't reply
    "SENT": 1,     # just sent
    "NOT_CONTACTED": 0,
}

GEO_SCORE = {
    # Higher for strategic geos
    "india": 5,
    "united arab emirates": 5, "uae": 5, "dubai": 5,
    "singapore": 4,
    "united states": 4, "us": 4, "usa": 4,
    "united kingdom": 4, "uk": 4,
    "australia": 3,
    "indonesia": 3, "malaysia": 3, "philippines": 3,
    "saudi arabia": 3, "qatar": 3,
}


def score_title(title: str) -> int:
    if not title:
        return 1
    t = title.lower()
    for kw, pts in TITLE_SCORE.items():
        if kw in t:
            return pts
    return 2


def score_geo(location: str) -> int:
    if not location:
        return 1
    loc = location.lower()
    for kw, pts in GEO_SCORE.items():
        if kw in loc:
            return pts
    return 1


def score_engagement(status: str) -> int:
    return ENGAGEMENT_SCORE.get(status, 0)


def has_linkedin(row: dict) -> bool:
    li = row.get("linkedin_profile", "") or row.get("linkedin", "") or ""
    for cf in ["linkedin_url", "linkedin", "linkedin_profile"]:
        val = row.get(cf, "") or ""
        if "linkedin.com" in val.lower():
            return True
    return "linkedin.com" in li.lower()


def extract_linkedin(row: dict) -> str:
    for field in ["linkedin_profile", "linkedin_url", "linkedin"]:
        val = row.get(field, "") or ""
        if "linkedin.com" in val.lower():
            return val.strip()

    # Check custom fields JSON
    cf_raw = row.get("custom_fields", "") or ""
    if cf_raw:
        try:
            cf = json.loads(cf_raw) if isinstance(cf_raw, str) else cf_raw
            if isinstance(cf, list):
                for item in cf:
                    v = str(item.get("value", ""))
                    if "linkedin.com" in v.lower():
                        return v.strip()
            elif isinstance(cf, dict):
                for v in cf.values():
                    if "linkedin.com" in str(v).lower():
                        return str(v).strip()
        except Exception:
            pass

    return ""


# ── API calls ──────────────────────────────────────────────────────────────────

async def fetch_leads_csv(client: httpx.AsyncClient, campaign_id: int) -> list[dict]:
    """Fetch all leads via CSV export endpoint."""
    url = f"{BASE_URL}/campaigns/{campaign_id}/leads-export"
    params = {"api_key": API_KEY}

    resp = await client.get(url, params=params, timeout=60)
    if resp.status_code == 429:
        print(f"  Rate limited, waiting 30s...")
        await asyncio.sleep(30)
        resp = await client.get(url, params=params, timeout=60)

    resp.raise_for_status()

    # Parse CSV
    content = resp.text
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


async def fetch_leads_paginated(client: httpx.AsyncClient, campaign_id: int) -> list[dict]:
    """Fallback: fetch leads via paginated JSON endpoint."""
    leads = []
    offset = 0
    limit = 100

    while True:
        url = f"{BASE_URL}/campaigns/{campaign_id}/leads"
        params = {"api_key": API_KEY, "limit": limit, "offset": offset}
        resp = await client.get(url, params=params, timeout=30)

        if resp.status_code == 429:
            await asyncio.sleep(30)
            continue

        if resp.status_code != 200:
            print(f"  Warning: status {resp.status_code} at offset {offset}")
            break

        data = resp.json()
        if isinstance(data, list):
            batch = data
        elif isinstance(data, dict):
            batch = data.get("data", data.get("leads", []))
        else:
            break

        if not batch:
            break

        leads.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        await asyncio.sleep(0.4)  # rate limit: ~150 req/min

    return leads


# ── Main ───────────────────────────────────────────────────────────────────────

OUTPUT_FIELDS = [
    "campaign_id", "campaign_name",
    "email", "first_name", "last_name", "full_name",
    "title", "company_name", "location",
    "linkedin_url",
    "email_status", "reply_count", "open_count",
    "score_title", "score_geo", "score_engagement", "score_total",
    "priority_tier",  # A / B / C
]


def tier(score: int) -> str:
    if score >= 15:
        return "A"
    elif score >= 8:
        return "B"
    return "C"


async def process_campaign(client, cid: int, cname: str) -> list[dict]:
    print(f"\n[{cid}] {cname}")

    try:
        rows = await fetch_leads_csv(client, cid)
        print(f"  CSV export: {len(rows)} total leads")
    except Exception as e:
        print(f"  CSV failed ({e}), trying paginated...")
        try:
            rows = await fetch_leads_paginated(client, cid)
            print(f"  Paginated: {len(rows)} total leads")
        except Exception as e2:
            print(f"  Both failed: {e2}")
            return []

    results = []
    no_linkedin = 0

    for row in rows:
        # Normalise keys (CSV headers vary)
        row = {k.lower().strip().replace(" ", "_"): v for k, v in row.items()}

        status = (row.get("status") or row.get("email_status") or "").upper().strip()

        # Filter: only non-replied
        if status in ("REPLIED", "UNSUBSCRIBED", "BOUNCED", "COMPLETED"):
            continue

        # Must have LinkedIn
        li_url = extract_linkedin(row)
        if not li_url:
            no_linkedin += 1
            continue

        first  = (row.get("first_name") or "").strip()
        last   = (row.get("last_name")  or "").strip()
        title  = (row.get("title") or row.get("lead_category") or "").strip()
        company = (row.get("company_name") or row.get("company") or "").strip()
        location = (row.get("location") or row.get("city") or "").strip()

        s_title = score_title(title)
        s_geo   = score_geo(location)
        s_eng   = score_engagement(status)
        s_total = s_title + s_geo + s_eng

        results.append({
            "campaign_id":        cid,
            "campaign_name":      cname,
            "email":              row.get("email", "").strip(),
            "first_name":         first,
            "last_name":          last,
            "full_name":          f"{first} {last}".strip(),
            "title":              title,
            "company_name":       company,
            "location":           location,
            "linkedin_url":       li_url,
            "email_status":       status,
            "reply_count":        row.get("reply_count", 0),
            "open_count":         row.get("open_count", 0),
            "score_title":        s_title,
            "score_geo":          s_geo,
            "score_engagement":   s_eng,
            "score_total":        s_total,
            "priority_tier":      tier(s_total),
        })

    results.sort(key=lambda x: -x["score_total"])

    print(f"  → {len(results)} leads with LinkedIn (skipped {no_linkedin} without)")
    print(f"    Tier A: {sum(1 for r in results if r['priority_tier']=='A')} | "
          f"B: {sum(1 for r in results if r['priority_tier']=='B')} | "
          f"C: {sum(1 for r in results if r['priority_tier']=='C')}")

    # Save per-campaign CSV
    out_file = OUT_DIR / f"{cname}_leads.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"  Saved: {out_file}")

    return results


async def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set. Run: set -a && source .env && set +a")
        return

    print(f"SmartLead Lead Export — {TODAY}")
    print(f"Output dir: {OUT_DIR}\n")

    all_leads = []

    async with httpx.AsyncClient() as client:
        for cid, cname in CAMPAIGNS.items():
            leads = await process_campaign(client, cid, cname)
            all_leads.extend(leads)
            await asyncio.sleep(1)  # be kind to the API

    # Sort combined list
    all_leads.sort(key=lambda x: (-x["score_total"], x["campaign_name"]))

    # Save combined CSV
    combined_file = OUT_DIR / "ALL_CAMPAIGNS_scored.csv"
    with open(combined_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(all_leads)

    # Summary
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(all_leads)} leads across {len(CAMPAIGNS)} campaigns")
    print(f"Tier A: {sum(1 for r in all_leads if r['priority_tier']=='A')}")
    print(f"Tier B: {sum(1 for r in all_leads if r['priority_tier']=='B')}")
    print(f"Tier C: {sum(1 for r in all_leads if r['priority_tier']=='C')}")
    print(f"\nCombined file: {combined_file}")

    # Campaign breakdown
    print(f"\nBreakdown by campaign:")
    for cid, cname in CAMPAIGNS.items():
        c_leads = [r for r in all_leads if r["campaign_id"] == cid]
        print(f"  {cname}: {len(c_leads)} leads")


if __name__ == "__main__":
    asyncio.run(main())
