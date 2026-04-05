"""
Smartlead company-level duplicate checker.
Finds companies that have contacts in more than one campaign (even with different emails).

Usage:
    SMARTLEAD_API_KEY=your_key python check_duplicates_by_company.py --filter onsocial
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


def normalize_company(name: str) -> str:
    if not name:
        return ""
    return name.lower().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("SMARTLEAD_API_KEY", ""))
    parser.add_argument("--filter", default=None)
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set SMARTLEAD_API_KEY env var or pass --api-key")
        sys.exit(1)

    print("Fetching campaigns...")
    campaigns = fetch_all_campaigns(args.api_key, args.filter)
    print(f"Found {len(campaigns)} campaigns\n")

    # company_name -> list of {campaign, email, status, first_name, last_name}
    company_map: dict[str, list[dict]] = defaultdict(list)

    for i, camp in enumerate(campaigns, 1):
        cid = camp["id"]
        cname = camp.get("name", f"campaign_{cid}")
        print(f"[{i}/{len(campaigns)}] {cname} (id={cid})...", end=" ", flush=True)

        try:
            leads = fetch_all_leads(cid, args.api_key)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        print(f"{len(leads)} leads")

        for entry in leads:
            lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
            company_raw = lead.get("company_name", "").strip()
            if not company_raw:
                continue
            company_key = normalize_company(company_raw)
            company_map[company_key].append({
                "company_display": company_raw,
                "campaign_id": cid,
                "campaign_name": cname,
                "email": lead.get("email", ""),
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "status": entry.get("status", "N/A"),
            })

    # Find companies in more than one campaign
    duplicates = {
        company: entries
        for company, entries in company_map.items()
        if len(set(e["campaign_id"] for e in entries)) > 1
    }

    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТ: {len(duplicates)} компаний встречаются в нескольких кампаниях")
    print(f"Всего уникальных компаний: {len(company_map)}")
    print(f"{'='*60}\n")

    if not duplicates:
        print("Дублей по компаниям не найдено.")
        return

    # Sort by number of campaigns desc
    sorted_dups = sorted(duplicates.items(), key=lambda x: len(set(e["campaign_id"] for e in x[1])), reverse=True)

    for company_key, entries in sorted_dups:
        campaign_ids = set(e["campaign_id"] for e in entries)
        display_name = entries[0]["company_display"]

        print(f"КОМПАНИЯ: {display_name}  ({len(campaign_ids)} кампании, {len(entries)} контактов)")
        # Group by campaign
        by_campaign: dict[int, list] = defaultdict(list)
        for e in entries:
            by_campaign[e["campaign_id"]].append(e)

        for cid, camp_entries in by_campaign.items():
            cname = camp_entries[0]["campaign_name"]
            print(f"  [{cname}]")
            for e in camp_entries:
                name = f"{e['first_name']} {e['last_name']}".strip()
                print(f"    - {e['email']}  {name}  [{e['status']}]")
        print()

    # Summary
    print(f"{'='*60}")
    print(f"ТОП компании с наибольшим числом кампаний:")
    print(f"{'='*60}")
    for company_key, entries in sorted_dups[:30]:
        display = entries[0]["company_display"]
        n_camps = len(set(e["campaign_id"] for e in entries))
        n_contacts = len(entries)
        print(f"  {n_camps} кампании / {n_contacts} контактов — {display}")


if __name__ == "__main__":
    main()
