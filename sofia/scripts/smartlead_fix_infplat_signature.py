#!/usr/bin/env python3
"""
Fix Step 1 of INFPLAT ALL GEO (#3096747): replace hardcoded signature with {{social_proof}}.
Only Step 1 body changes — all other steps are unchanged.
"""

import requests
import json
import os

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = 3096747

# Step 1 sequence ID (from previous script)
SEQ_ID_STEP1 = 7004560

STEP1_BODY = """Hey {{first_name}},<br><br>Checked {{company_name}} - you're giving clients creator analytics. Quick question: is the data layer yours, or do you pull from a vendor?<br><br>Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API. Building creator data in-house breaks every time TikTok changes something - our endpoint handles that, 450M+ profiles, city-level demographics.<br><br>Can run any creator through the API live - 15 min?<br><br>Kind regards,<br>Bhaskar Vishnu from OnSocial<br>Trusted by {{social_proof}}"""

# First, read current full sequence to get all steps (needed for POST)
r = requests.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY})
r.raise_for_status()
steps = r.json()
print(f"Got {len(steps)} steps")

# Build updated payload — only change Step 1 body
updated = []
for step in steps:
    seq_id = step.get("id") or step.get("seq_id")
    day = step.get("seq_delay_details", {}).get("delay_in_days", step.get("delayInDays", 0))

    subj = step.get("seq_variants", [{}])[0].get("subject", "") if step.get("seq_variants") else step.get("subject", "")
    body = step.get("seq_variants", [{}])[0].get("email_body", "") if step.get("seq_variants") else step.get("email_body", "")

    if seq_id == SEQ_ID_STEP1:
        print(f"Step 1 found (id={seq_id}, day={day}) — updating signature")
        body = STEP1_BODY

    seq_num = step.get("seq_number", len(updated) + 1)
    updated.append({
        "seq_number": seq_num,
        "subject": subj,
        "email_body": body,
        "seq_delay_details": {"delay_in_days": day}
    })

print(f"\nUpdating {len(updated)} steps...")
r2 = requests.post(
    f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences",
    params={"api_key": API_KEY},
    json={"sequences": updated}
)
print(f"Status: {r2.status_code}")
print(r2.json())

# Verify
r3 = requests.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY})
steps_after = r3.json()
v = steps_after[0]
body_after = v.get("seq_variants", [{}])[0].get("email_body", "") if v.get("seq_variants") else v.get("email_body", "")
print(f"\nStep 1 body ends with: ...{body_after[-60:]}")
