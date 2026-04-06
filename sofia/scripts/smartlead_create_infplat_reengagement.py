#!/usr/bin/env python3
"""Create c-OnSocial_Re-engagement_INFPLAT campaign with sequences + email accounts."""

import httpx, os, sys, json

KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE = "https://server.smartlead.ai/api/v1"
if not KEY:
    print("ERROR: SMARTLEAD_API_KEY not set"); sys.exit(1)


def api(method, path, data=None, params=None):
    p = {"api_key": KEY}
    if params:
        p.update(params)
    if method == "GET":
        r = httpx.get(f"{BASE}{path}", params=p, timeout=30)
    else:
        r = httpx.post(f"{BASE}{path}", params=p, json=data, timeout=30)
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    return r.json()


# ── Get email accounts from IMAGENCY re-engagement ──
print("Checking IMAGENCY re-engagement email accounts...")
accounts = api("GET", "/campaigns/3121190/email-accounts")
if isinstance(accounts, list):
    account_ids = [a.get("id") for a in accounts]
elif isinstance(accounts, dict):
    accs = accounts.get("data", accounts.get("email_accounts", []))
    account_ids = [a.get("id", a.get("email_account_id")) for a in accs]
else:
    account_ids = []
print(f"  Found {len(account_ids)} accounts")

# ── Create campaign ──
print("\nCreating c-OnSocial_Re-engagement_INFPLAT...")
resp = api("POST", "/campaigns/create", {"name": "c-OnSocial_Re-engagement_INFPLAT"})
cid = resp["id"]
print(f"  Campaign ID: {cid}")

# ── Sequences: INFPLAT re-engagement angle ──
sequences = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "{{first_name}} - still building creator data in-house?",
        "email_body": (
            "<p>Hey {{first_name}},</p>"
            "<p>Reaching back out - curious if anything changed on the data side at {{company_name}}.</p>"
            "<p>Since we last connected, Lefty moved their entire creator data layer to our API "
            "and freed 2 engineering roles that were just maintaining scrapers. "
            "Kolsquare expanded from 3 to 5 social networks in a week instead of a quarter.</p>"
            "<p>If your team is still spending cycles on data infrastructure instead of product - "
            "worth a 15-min look at what changed.</p>"
            "<p>Bhaskar Vishnu from OnSocial<br>"
            "Trusted by Modash, Captiv8, Lefty and Kolsquare</p>"
        ),
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "",
        "email_body": (
            '<p style="font-weight: 400; margin-block: 1em">Hey {{first_name}},</p>'
            '<p style="font-weight: 400; margin-block: 1em">'
            "One data point that keeps coming up with platforms like yours:<br>"
            "- Building creator data in-house = 4-6 months before you cover more than Instagram<br>"
            "- Our API = IG, TikTok, YouTube from day one, 450M+ profiles, city-level demographics<br>"
            "- Updates every 24-48h - no engineering maintenance on your side</p>"
            '<p style="font-weight: 400; margin-block: 1em">'
            "Drop any creator handle in reply - I will run it through our API and send the raw output. No call needed.</p>"
            '<p style="font-weight: 400; margin-block: 1em">'
            "Bhaskar Vishnu from OnSocial<br>"
            "Trusted by Modash, Captiv8, Lefty and Kolsquare</p>"
        ),
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "",
        "email_body": (
            '<p style="font-weight: 400; margin-block: 1em">'
            "Would it be easier to connect on LinkedIn?</p>"
            '<p style="font-weight: 400; margin-block: 1em">'
            "If creator data is not on the roadmap right now - no worries. "
            "But if I am reaching the wrong person, who handles data infrastructure at {{company_name}}? "
            "Usually CTO or Head of Product.</p>"
            '<p style="font-weight: 400; margin-block: 1em">'
            "Bhaskar Vishnu from OnSocial</p>"
            '<p style="font-weight: 400; margin-block: 1em">'
            "Sent from my iPhone</p>"
        ),
    },
]

print("\nAdding 3 sequences...")
resp = api("POST", f"/campaigns/{cid}/sequences", {"sequences": sequences})
print(f"  Result: {resp}")

# ── Set email accounts ──
print(f"\nSetting {len(account_ids)} email accounts...")
resp = api("POST", f"/campaigns/{cid}/email-accounts", {"email_account_ids": account_ids})
ok = resp.get("ok", False)
count = len(resp.get("result", []))
print(f"  ok={ok}, attached={count}")

print(f"\n{'='*50}")
print(f"DONE: c-OnSocial_Re-engagement_INFPLAT (id={cid})")
print(f"Sequences: 3")
print(f"Email accounts: {count}")
print(f"NOT activated - activate manually in SmartLead UI")
print(f"{'='*50}")
