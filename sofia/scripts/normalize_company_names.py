#!/usr/bin/env python3
"""Normalize company_name in all c-OnSocial SmartLead campaigns."""

import re
import time
import requests

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
SUFFIXES = [", Inc.", " Inc.", ", LLC", " LLC", ", Ltd.", " Ltd.", ", Corp.", " Corp."]


def normalize_company(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"\s+", " ", name).strip()
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def get_campaigns():
    r = requests.get(
        f"{BASE}/campaigns", params={"api_key": API_KEY, "limit": 100, "offset": 0}
    )
    r.raise_for_status()
    data = r.json()
    campaigns = data if isinstance(data, list) else data.get("data", [])
    return [c for c in campaigns if c.get("name", "").startswith("c-OnSocial")]


def get_all_leads(campaign_id):
    leads = []
    offset = 0
    limit = 100
    while True:
        r = requests.get(
            f"{BASE}/campaigns/{campaign_id}/leads",
            params={"api_key": API_KEY, "offset": offset, "limit": limit},
        )
        r.raise_for_status()
        data = r.json()
        batch = data.get("data", [])
        leads.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return leads


def update_lead(campaign_id, lead_id, company_name):
    r = requests.post(
        f"{BASE}/campaigns/{campaign_id}/leads/{lead_id}",
        params={"api_key": API_KEY},
        json={"company_name": company_name},
    )
    r.raise_for_status()
    return r.json()


def main():
    campaigns = get_campaigns()
    print(f"Found {len(campaigns)} OnSocial campaigns")

    total_updated = 0
    total_skipped = 0

    for camp in campaigns:
        cid = camp["id"]
        cname = camp["name"]
        print(f"\n→ {cname} (id={cid})")

        leads = get_all_leads(cid)
        print(f"  {len(leads)} leads")

        updated = 0
        for entry in leads:
            lead = entry.get("lead", {})
            lid = lead.get("id")
            original = lead.get("company_name") or ""
            normalized = normalize_company(original)

            if normalized != original:
                print(f"  [{lid}] '{original}' → '{normalized}'")
                update_lead(cid, lid, normalized)
                updated += 1
                time.sleep(0.15)

        print(f"  Updated: {updated}, unchanged: {len(leads) - updated}")
        total_updated += updated
        total_skipped += len(leads) - updated

    print(f"\nDone. Total updated: {total_updated}, unchanged: {total_skipped}")


if __name__ == "__main__":
    main()
