#!/usr/bin/env python3
"""Fix Step 1 signature in IMAGENCY ALL GEO (#3096746): replace hardcoded proof with {{social_proof}}."""

import requests, os, re

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = 3096746

r = requests.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY})
r.raise_for_status()
steps = r.json()
print(f"Got {len(steps)} steps")

updated = []
for i, step in enumerate(steps):
    seq_num = step.get("seq_number", i + 1)
    day = step.get("seq_delay_details", {}).get("delay_in_days", step.get("delayInDays", 0))
    subj = step.get("seq_variants", [{}])[0].get("subject", "") if step.get("seq_variants") else step.get("subject", "")
    body = step.get("seq_variants", [{}])[0].get("email_body", "") if step.get("seq_variants") else step.get("email_body", "")

    if i == 0 and "Trusted by " in body:
        # Replace hardcoded proof (anything after "Trusted by " to end of string)
        body = re.sub(r"Trusted by .+$", "Trusted by {{social_proof}}", body, flags=re.DOTALL)
        print(f"  Step 1: signature fixed -> ...{body[-60:]}")

    updated.append({
        "seq_number": seq_num,
        "subject": subj,
        "email_body": body,
        "seq_delay_details": {"delay_in_days": day}
    })

r2 = requests.post(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY}, json={"sequences": updated})
print(f"Status: {r2.status_code}")
print(r2.json())
