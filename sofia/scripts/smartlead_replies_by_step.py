#!/usr/bin/env python3
"""
SmartLead — Replies by Step
============================
Собирает все ответы по IM-FIRST AGENCIES кампаниям.
Показывает: на какой шаг / subject ответили лиды.

Run: ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_replies_by_step.py"
"""

import os
import json
import httpx
from collections import defaultdict

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

CAMPAIGNS = {
    "Global":   3050462,
    "India":    3063527,
    "Europe":   3064335,
    "Americas": 3071851,
    "ALL GEO":  3096746,
}


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_all_statistics(campaign_id):
    """Fetch ALL statistics records with pagination."""
    all_records = []
    offset = 0
    limit = 500

    while True:
        data = api_get(f"/campaigns/{campaign_id}/statistics", {"offset": offset, "limit": limit})

        if not data or "data" not in data:
            break

        records = data["data"]
        if not records:
            break

        all_records.extend(records)
        total = int(data.get("total_stats", len(records)))

        print(f"  fetched {len(all_records)}/{total}...", end="\r")

        if len(all_records) >= total or len(records) < limit:
            break

        offset += limit

    print()
    return all_records


def analyze_replies(records):
    """Extract records where reply_time is set."""
    replied = [r for r in records if r.get("reply_time")]
    return replied


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("\n=== OnSocial IM-FIRST AGENCIES — Replies by Step ===\n")

    all_replies = []

    for name, cid in CAMPAIGNS.items():
        print(f"\n[{name}] campaign_id={cid}")
        records = get_all_statistics(cid)
        replied = analyze_replies(records)
        print(f"  Total records: {len(records)}")
        print(f"  Replied: {len(replied)}")

        for r in replied:
            all_replies.append({
                "campaign": name,
                "email": r.get("lead_email", ""),
                "name": r.get("lead_name", ""),
                "subject": r.get("email_subject", ""),
                "sent_time": r.get("sent_time", ""),
                "reply_time": r.get("reply_time", ""),
            })

    # Sort by campaign + subject
    all_replies.sort(key=lambda x: (x["campaign"], x["subject"]))

    # Summary: replies by subject per campaign
    print("\n\n=== REPLIES BY SUBJECT (STEP/VARIANT) ===\n")

    by_campaign = defaultdict(lambda: defaultdict(list))
    for r in all_replies:
        by_campaign[r["campaign"]][r["subject"]].append(r)

    for campaign in ["Global", "India", "Europe", "Americas", "ALL GEO"]:
        subjects = by_campaign.get(campaign)
        if not subjects:
            print(f"{campaign}: 0 replies\n")
            continue

        total = sum(len(v) for v in subjects.values())
        print(f"{campaign} — {total} replies:")
        for subject, leads in sorted(subjects.items(), key=lambda x: -len(x[1])):
            subj_display = subject[:80] if subject else "(empty)"
            print(f"  [{len(leads):2}x]  {subj_display}")
            for lead in leads:
                print(f"         {lead['email']}  replied: {lead['reply_time'][:10] if lead['reply_time'] else '?'}")
        print()

    # Save JSON
    output = {
        "total_replies": len(all_replies),
        "by_campaign": {
            camp: {
                subj: [{"email": r["email"], "name": r["name"], "reply_time": r["reply_time"]}
                       for r in leads]
                for subj, leads in subjects.items()
            }
            for camp, subjects in by_campaign.items()
        },
        "raw": all_replies,
    }

    out_path = "sofia/projects/OnSocial/hub/im_agencies_replies_by_step.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved: {out_path}")
    print(f"\nTotal replies across all campaigns: {len(all_replies)}")


if __name__ == "__main__":
    main()
