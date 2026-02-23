"""
Create 3 REAL SmartLead campaigns that send actual emails to pn@getsally.io.
Each campaign uses a different sender account and has a unique email sequence.
Each run creates fresh campaigns with a timestamp suffix so they're unique.

Usage: cd backend && python3 create_real_campaigns.py
"""
import httpx
import json
import time
import sys
from datetime import datetime

API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
BASE = "https://server.smartlead.ai/api/v1"
LEAD_EMAIL = "pn@getsally.io"
LEAD_FIRST = "Petr"
LEAD_LAST = "Nikolaev"
LEAD_COMPANY = "GetSally"

# Timestamp suffix for unique campaign names each run
TS = datetime.now().strftime("%m%d_%H%M")

# 3 sender accounts (different domains for variety)
SENDER_ACCOUNTS = [
    15020706,  # danila@flowsally.com
    15020777,  # danila@cloudsallyai.com
    15020797,  # danila@team-sallyai.com
]

CAMPAIGNS = [
    {
        "name": f"E2E_Test_GetSally_{TS}",
        "sender_id": SENDER_ACCOUNTS[0],
        "subject": "Partnership Opportunity with GetSally",
        "body": """<p>Hi {{first_name}},</p>
<p>I noticed GetSally is growing fast in the sales automation space. We help companies like yours scale outreach by 3x with AI-powered lead generation.</p>
<p>Would love to chat about a potential partnership. Got 15 minutes this week?</p>
<p>Best,<br/>Danila</p>""",
    },
    {
        "name": f"E2E_Test_Outreach_{TS}",
        "sender_id": SENDER_ACCOUNTS[1],
        "subject": "Quick question about your outreach stack",
        "body": """<p>Hi {{first_name}},</p>
<p>Are you tired of manually managing outreach sequences? Our platform automates email campaigns, follow-ups, and lead scoring.</p>
<p>We recently helped a SaaS company similar to yours save 10+ hours a week on outreach. Curious if you'd be open to seeing a quick demo?</p>
<p>Cheers,<br/>Danila</p>""",
    },
    {
        "name": f"E2E_Test_Partnership_{TS}",
        "sender_id": SENDER_ACCOUNTS[2],
        "subject": "Let's connect about lead generation",
        "body": """<p>Hi {{first_name}},</p>
<p>I've been following GetSally's growth — impressive traction! We specialize in lead generation tools for SaaS companies.</p>
<p>I think we could help you 2x your outbound pipeline. Got time for a quick chat this week?</p>
<p>Best,<br/>Danila</p>""",
    },
]


def api(method, endpoint, **kwargs):
    """Make SmartLead API request."""
    url = f"{BASE}/{endpoint}"
    params = kwargs.pop("params", {})
    params["api_key"] = API_KEY
    resp = httpx.request(method, url, params=params, timeout=30, **kwargs)
    if resp.status_code not in (200, 201):
        print(f"  ERROR {resp.status_code}: {resp.text[:300]}")
        return None
    return resp.json()


def create_campaign(config):
    name = config["name"]
    print(f"\n{'='*60}")
    print(f"Creating campaign: {name}")
    print(f"{'='*60}")

    # 1. Create campaign
    data = api("POST", "campaigns/create", json={"name": name})
    if not data or "id" not in data:
        print(f"  FAILED to create campaign {name}")
        return None
    campaign_id = data["id"]
    print(f"  Created: id={campaign_id}")

    # 2. Set sequences (email content)
    seq_data = api("POST", f"campaigns/{campaign_id}/sequences", json={
        "sequences": [{
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": config["subject"],
            "email_body": config["body"],
        }]
    })
    print(f"  Sequences: {'OK' if seq_data else 'FAILED'}")

    # 3. Assign email account
    acc_data = api("POST", f"campaigns/{campaign_id}/email-accounts", json={
        "email_account_ids": [config["sender_id"]]
    })
    print(f"  Email account: {'OK' if acc_data is not None else 'FAILED'}")

    # 4. Configure settings
    settings_data = api("POST", f"campaigns/{campaign_id}/settings", json={
        "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
        "stop_lead_settings": "REPLY_TO_AN_EMAIL",
        "send_as_plain_text": False,
        "follow_up_percentage": 100,
    })
    print(f"  Settings: {'OK' if settings_data is not None else 'FAILED'}")

    # 5. Set schedule (send immediately, all days)
    sched_data = api("POST", f"campaigns/{campaign_id}/schedule", json={
        "timezone": "Europe/Moscow",
        "days_of_the_week": [0, 1, 2, 3, 4, 5, 6],
        "start_hour": "00:00",
        "end_hour": "23:59",
        "min_time_btw_emails": 3,
        "max_new_leads_per_day": 100,
    })
    print(f"  Schedule: {'OK' if sched_data is not None else 'FAILED'}")

    # 6. Add lead (pn@getsally.io)
    lead_data = api("POST", f"campaigns/{campaign_id}/leads", json={
        "lead_list": [{
            "email": LEAD_EMAIL,
            "first_name": LEAD_FIRST,
            "last_name": LEAD_LAST,
            "company_name": LEAD_COMPANY,
        }]
    })
    if lead_data:
        print(f"  Lead added: {LEAD_EMAIL}")
    else:
        print(f"  Lead add FAILED")

    # 7. Start campaign
    start_data = api("POST", f"campaigns/{campaign_id}/status", json={"status": "START"})
    print(f"  Status → START: {'OK' if start_data is not None else 'FAILED'}")

    return campaign_id


def main():
    print("Creating 3 REAL SmartLead campaigns for pn@getsally.io")
    print(f"API Key: {API_KEY[:12]}...")

    created = []
    for config in CAMPAIGNS:
        cid = create_campaign(config)
        if cid:
            created.append((config["name"], cid))
        time.sleep(3)  # Pause between campaigns to avoid rate limits

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(created)}/{len(CAMPAIGNS)} campaigns created")
    print(f"{'='*60}")
    for name, cid in created:
        print(f"  {name}: https://app.smartlead.ai/app/email-campaign/{cid}/overview")

    if len(created) == 3:
        print(f"\nAll 3 campaigns created and STARTED. Emails will be sent to {LEAD_EMAIL} shortly.")
        print("Check inbox at pn@getsally.io for the test emails.")
        print(f"\nTo update seed_test_replies.py, use these campaign IDs:")
        for name, cid in created:
            print(f'    {{"name": "{name}", "campaign_id": "{cid}"}},')
        print(f"\nAlso add these campaign names to project campaign_filters.")
    else:
        print(f"\nWARNING: Only {len(created)}/3 campaigns created successfully.")


if __name__ == "__main__":
    main()
