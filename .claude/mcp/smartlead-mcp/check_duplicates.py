"""
Smartlead cross-campaign duplicate checker.
Finds leads (by email) that appear in more than one campaign.

Usage:
    SMARTLEAD_API_KEY=your_key python check_duplicates.py

    # Or with hardcoded key:
    python check_duplicates.py --api-key your_key

    # Filter by campaign name substring (e.g. only OnSocial):
    python check_duplicates.py --filter onsocial
"""

import os
import sys
import argparse
import httpx
from collections import defaultdict

BASE_URL = "https://server.smartlead.ai/api/v1"


def api_get(path: str, params: dict, api_key: str) -> dict | list:
    p = {"api_key": api_key, **params}
    resp = httpx.get(f"{BASE_URL}{path}", params=p, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all_campaigns(api_key: str, name_filter: str = None) -> list[dict]:
    data = api_get("/campaigns", {}, api_key)
    campaigns = data if isinstance(data, list) else data.get("data", [])
    if name_filter:
        campaigns = [c for c in campaigns if name_filter.lower() in c.get("name", "").lower()]
    return campaigns


def fetch_all_leads(campaign_id: int, api_key: str) -> list[dict]:
    """Paginate through all leads in a campaign."""
    leads = []
    offset = 0
    limit = 100
    while True:
        data = api_get(f"/campaigns/{campaign_id}/leads", {"offset": offset, "limit": limit}, api_key)
        page = data if isinstance(data, list) else data.get("data", [])
        if not page:
            break
        leads.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return leads


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("SMARTLEAD_API_KEY", ""))
    parser.add_argument("--filter", default=None, help="Filter campaigns by name substring")
    parser.add_argument("--status", default=None, help="Only check campaigns with this status (e.g. ACTIVE)")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set SMARTLEAD_API_KEY env var or pass --api-key")
        sys.exit(1)

    print("Fetching campaigns...")
    campaigns = fetch_all_campaigns(args.api_key, args.filter)

    if args.status:
        campaigns = [c for c in campaigns if c.get("status", "").upper() == args.status.upper()]

    print(f"Found {len(campaigns)} campaigns to check\n")

    # email -> list of (campaign_name, campaign_id, lead_status)
    email_map: dict[str, list[dict]] = defaultdict(list)

    for i, camp in enumerate(campaigns, 1):
        cid = camp["id"]
        cname = camp.get("name", f"campaign_{cid}")
        print(f"[{i}/{len(campaigns)}] Fetching leads: {cname} (id={cid})...", end=" ", flush=True)

        try:
            leads = fetch_all_leads(cid, args.api_key)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        print(f"{len(leads)} leads")

        for entry in leads:
            lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
            email = lead.get("email", "").lower().strip()
            if not email:
                continue
            email_map[email].append({
                "campaign_id": cid,
                "campaign_name": cname,
                "lead_status": entry.get("status", "N/A"),
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "company": lead.get("company_name", ""),
            })

    # Find duplicates
    duplicates = {email: entries for email, entries in email_map.items() if len(entries) > 1}

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(duplicates)} duplicate emails found across campaigns")
    print(f"Total unique emails checked: {len(email_map)}")
    print(f"{'='*60}\n")

    if not duplicates:
        print("No duplicates found.")
        return

    # Group by campaign pairs for summary
    pair_counts: dict[str, int] = defaultdict(int)

    for email, entries in sorted(duplicates.items()):
        campaign_names = [e["campaign_name"] for e in entries]
        statuses = [e["lead_status"] for e in entries]
        name = f"{entries[0]['first_name']} {entries[0]['last_name']}".strip()
        company = entries[0]["company"]

        print(f"EMAIL: {email}")
        if name or company:
            print(f"  Lead: {name} @ {company}")
        for e in entries:
            print(f"  → [{e['lead_status']}] {e['campaign_name']} (id={e['campaign_id']})")
        print()

        # Count pairs
        for j in range(len(campaign_names)):
            for k in range(j + 1, len(campaign_names)):
                pair = tuple(sorted([campaign_names[j], campaign_names[k]]))
                pair_counts[pair] += 1

    # Summary by campaign pair
    if pair_counts:
        print(f"{'='*60}")
        print("SUMMARY — Most common duplicate campaign pairs:")
        print(f"{'='*60}")
        for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1])[:20]:
            print(f"  {count:3d} duplicates:  {pair[0]}  ↔  {pair[1]}")


if __name__ == "__main__":
    main()
