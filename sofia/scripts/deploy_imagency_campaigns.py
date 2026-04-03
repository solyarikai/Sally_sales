#!/usr/bin/env python3
"""
Deploy IMAGENCY v5 campaigns to SmartLead:
1. Create 3 campaigns (FOUNDERS, CREATIVE, ACCOUNT_OPS)
2. Save schedule settings
3. Upload sequences (3 emails each)
4. Upload leads from CSVs (with custom1-4 already populated)

IMPORTANT: Does NOT activate campaigns — manual activation only per protocol.
"""

import csv
import json
import os
import time
import sys

import httpx

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
BATCH_SIZE = 100

DATA_DIR = "/tmp/smartlead_ready"

# ── Campaign definitions ──────────────────────────────────────────────────────

CAMPAIGNS = [
    {
        "key": "founders",
        "name": "c-OnSocial_v5_IMAGENCY_FOUNDERS",
        "csv": f"{DATA_DIR}/imagency_founders_smartlead.csv",
        "sequences": [
            {
                "seq_number": 1,
                "delay_days": 0,
                "subject": "{{company_name}} - creator data question",
                "body": (
                    "Hi {{first_name}},<br><br>"
                    "{{custom4}}<br><br>"
                    "When your clients ask for creator analytics - do they see {{company_name}}'s brand or a third-party logo?<br><br>"
                    "Agencies like {{custom2}} white-label our creator data as their own. 450M+ profiles, fraud scoring, audience demographics - under your brand.<br><br>"
                    "Quick 15-min call to see if it fits {{company_name}}?<br><br>"
                    "Best,<br>"
                    "Daniil from OnSocial"
                ),
            },
            {
                "seq_number": 2,
                "delay_days": 4,
                "subject": "Re: {{company_name}} - creator data question",
                "body": (
                    "Hi {{first_name}}, quick follow-up.<br><br>"
                    "When Lefty moved to our API, they freed 2 engineering roles and expanded from 1 platform to 5. No more maintaining scrapers.<br><br>"
                    "For agencies {{custom1}} - this is the difference between building infrastructure and building client relationships.<br><br>"
                    "Happy to mock up a branded report for {{company_name}} - takes 10 minutes on our side.<br><br>"
                    "Quick 15-min call?<br><br>"
                    "Daniil"
                ),
            },
            {
                "seq_number": 3,
                "delay_days": 4,  # delay from prev email, not from start (Day 4+4=Day 8)
                "subject": "Re: {{company_name}} - creator data question",
                "body": (
                    "Hi {{first_name}}, last note from me.<br><br>"
                    "If creator analytics aren't a priority right now - understood. But if I'm reaching the wrong person at {{company_name}}, who handles data or tool decisions?<br><br>"
                    "Either way - wishing you continued growth.<br><br>"
                    "Daniil"
                ),
            },
        ],
    },
    {
        "key": "creative",
        "name": "c-OnSocial_v5_IMAGENCY_CREATIVE",
        "csv": f"{DATA_DIR}/imagency_creative_smartlead.csv",
        "sequences": [
            {
                "seq_number": 1,
                "delay_days": 0,
                "subject": "creator vetting - {{company_name}}",
                "body": (
                    "Hi {{first_name}},<br><br>"
                    "{{custom4}}<br><br>"
                    "How does your team at {{company_name}} vet creators before pitching them to clients? Manual research, or do you have a data layer behind it?<br><br>"
                    "Creative teams at {{custom2}} use our API to check audience demographics, fraud scores, and engagement - before the brief goes out. Means fewer surprises after launch.<br><br>"
                    "Quick 15-min call to see if relevant for {{company_name}}?<br><br>"
                    "Best,<br>"
                    "Daniil from OnSocial"
                ),
            },
            {
                "seq_number": 2,
                "delay_days": 4,
                "subject": "Re: creator vetting - {{company_name}}",
                "body": (
                    "Hi {{first_name}}, quick follow-up.<br><br>"
                    "One pattern we see - creative teams spend 6+ hours researching creators per campaign. With 450M+ profiles indexed across IG, TikTok and YouTube, that drops to minutes.<br><br>"
                    "For teams {{custom1}} - it frees up time for the work that actually wins pitches.<br><br>"
                    "Happy to show you how it works - takes 15 minutes.<br><br>"
                    "Daniil"
                ),
            },
            {
                "seq_number": 3,
                "delay_days": 4,  # delay from prev email, not from start (Day 4+4=Day 8)
                "subject": "Re: creator vetting - {{company_name}}",
                "body": (
                    "Hi {{first_name}}, last note.<br><br>"
                    "If creator data tools aren't in your scope - who at {{company_name}} handles tool or platform decisions? Happy to connect with them instead.<br><br>"
                    "Thanks either way.<br><br>"
                    "Daniil"
                ),
            },
        ],
    },
    {
        "key": "account_ops",
        "name": "c-OnSocial_v5_IMAGENCY_ACCOUNT_OPS",
        "csv": f"{DATA_DIR}/imagency_account_ops_smartlead.csv",
        "sequences": [
            {
                "seq_number": 1,
                "delay_days": 0,
                "subject": "client reporting - {{company_name}}",
                "body": (
                    "Hi {{first_name}},<br><br>"
                    "{{custom4}}<br><br>"
                    "When {{company_name}} sends a client a creator performance report - does it come from your own platform, or are you exporting from someone else's tool?<br><br>"
                    "Account teams at {{custom2}} switched to white-label analytics. Client sees {{company_name}}'s brand, not a third party. Retention went up - clients build workflows around your tool and switching cost increases.<br><br>"
                    "Quick 15-min call to see if it fits?<br><br>"
                    "Best,<br>"
                    "Daniil from OnSocial"
                ),
            },
            {
                "seq_number": 2,
                "delay_days": 4,
                "subject": "Re: client reporting - {{company_name}}",
                "body": (
                    "Hi {{first_name}}, short follow-up.<br><br>"
                    "The #1 reason agencies lose clients to in-house teams: the client realizes they can buy the same tools directly. White-label removes that risk.<br><br>"
                    "We cover 450M+ profiles across IG, TikTok and YouTube - fraud scoring, audience demographics, city-level data. All under your brand.<br><br>"
                    "For account teams {{custom1}} - this changes the conversation from \"what tools do you use\" to \"show me your platform.\"<br><br>"
                    "Quick 15-min call?<br><br>"
                    "Daniil"
                ),
            },
            {
                "seq_number": 3,
                "delay_days": 4,  # delay from prev email, not from start (Day 4+4=Day 8)
                "subject": "Re: client reporting - {{company_name}}",
                "body": (
                    "Hi {{first_name}}, last one from me.<br><br>"
                    "If client analytics aren't a current priority - no worries. But if there's someone else at {{company_name}} who handles tool decisions or client reporting infrastructure, happy to connect with them.<br><br>"
                    "Wishing {{company_name}} continued growth either way.<br><br>"
                    "Daniil"
                ),
            },
        ],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs):
    url = f"{BASE}{path}"
    params = kwargs.pop("params", {})
    params["api_key"] = API_KEY
    r = httpx.request(method, url, params=params, timeout=60.0, **kwargs)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def create_campaign(name: str) -> int:
    data = api("POST", "/campaigns/create", json={"name": name, "client_id": None})
    return data["id"]


def save_schedule(campaign_id: int):
    """Apply same schedule settings as existing OnSocial campaigns."""
    api("POST", f"/campaigns/{campaign_id}/settings",
        json={
            "track_settings": [],
            "stop_lead_settings": "REPLY_TO_AN_EMAIL",
            "send_as_plain_text": False,
            "follow_up_percentage": 100,
            "unsubscribe_text": None,
        })


def upload_sequences(campaign_id: int, sequences: list):
    payload = []
    for seq in sequences:
        payload.append({
            "seq_number": seq["seq_number"],
            "seq_delay_details": {"delay_in_days": seq["delay_days"]},
            "subject": seq["subject"],
            "email_body": seq["body"],
        })
    api("POST", f"/campaigns/{campaign_id}/sequences",
        json={"sequences": payload})


def upload_leads(campaign_id: int, csv_path: str) -> int:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch_rows = rows[i:i + BATCH_SIZE]
        lead_list = []
        for r in batch_rows:
            lead_list.append({
                "email": r["email"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "company_name": r["company_name"],
                "custom_fields": {
                    "custom1": r["custom1"],
                    "custom2": r["custom2"],
                    "custom3": r["custom3"],
                    "custom4": r["custom4"],
                },
            })
        batch_num = i // BATCH_SIZE + 1
        try:
            result = api("POST", f"/campaigns/{campaign_id}/leads",
                         json={"lead_list": lead_list,
                               "settings": {"ignore_global_block_list": False}})
            count = result.get("upload_count", len(lead_list))
            if not isinstance(count, int):
                count = len(lead_list)
            total += count
            print(f"    Batch {batch_num}: {count} uploaded [{total}/{len(rows)}]")
        except RuntimeError as e:
            if "429" in str(e):
                print(f"    Rate limit on batch {batch_num}, waiting 70s...")
                time.sleep(70)
                result = api("POST", f"/campaigns/{campaign_id}/leads",
                             json={"lead_list": lead_list,
                                   "settings": {"ignore_global_block_list": False}})
                count = result.get("upload_count", len(lead_list))
                if not isinstance(count, int):
                    count = len(lead_list)
                total += count
                print(f"    Batch {batch_num} retry: {count} uploaded")
            else:
                print(f"    ERROR batch {batch_num}: {e}")
        time.sleep(0.5)
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    results = []

    for camp in CAMPAIGNS:
        print(f"\n{'='*60}")
        print(f"Campaign: {camp['name']}")
        print(f"{'='*60}")

        # 1. Create campaign
        print("  [1/3] Creating campaign...")
        campaign_id = create_campaign(camp["name"])
        print(f"  Created: id={campaign_id}")

        # 2. Upload sequences
        print("  [2/3] Uploading sequences...")
        upload_sequences(campaign_id, camp["sequences"])
        print(f"  Sequences uploaded: {len(camp['sequences'])} emails")

        # 3. Upload leads
        print(f"  [3/3] Uploading leads from {camp['csv']}...")
        uploaded = upload_leads(campaign_id, camp["csv"])
        print(f"  Leads uploaded: {uploaded}")

        results.append({
            "campaign": camp["name"],
            "id": campaign_id,
            "leads": uploaded,
        })
        time.sleep(1)

    print(f"\n{'='*60}")
    print("DEPLOYMENT COMPLETE")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['campaign']}")
        print(f"    ID: {r['id']}")
        print(f"    Leads: {r['leads']}")
        print(f"    URL: https://app.smartlead.ai/app/email-campaign/{r['id']}/settings/email-sequence")
    print("\nIMPORTANT: Do NOT activate via API — activate manually in SmartLead UI")


if __name__ == "__main__":
    main()
