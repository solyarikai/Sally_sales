#!/usr/bin/env python3
"""
Update INFLUENCER PLATFORMS ALL GEO — All 5 steps
====================================================
Uses proven Global sequence (1.67% reply rate) as base content.

Run: ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_update_infplat_allgeo.py"
"""

import os
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
CAMPAIGN_ID = 3096747

# Proven Global Step 1 — 1.67% reply rate
STEP1_BODY = (
    "Hey {{first_name}},<br><br>"
    "Checked {{company_name}} - you're giving clients creator analytics. "
    "Quick question: is the data layer yours, or do you pull from a vendor?<br><br>"
    "Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API. "
    "Building creator data in-house breaks every time TikTok changes something - "
    "our endpoint handles that, 450M+ profiles, city-level demographics.<br><br>"
    "Can run any creator through the API live - 15 min?<br><br>"
    "Kind regards,<br>"
    "Bhaskar Vishnu from OnSocial<br>"
    "Trusted by Traackr, Audiense, and Upfluence"
)

# Proven Global Step 2 — "Lefty freed 2 eng roles" + "drop creator handle" CTA
STEP2_BODY = (
    "{{first_name}}, quick add.<br><br>"
    "When Lefty moved to our API, they freed 2 eng roles that were just maintaining data - "
    "and expanded from 3 to 5 social networks in a week.<br><br>"
    "For platforms like {{company_name}} it's not about another data provider. "
    "It's about what your engineers spend time on.<br><br>"
    "Drop any creator handle in reply - I'll run it and send the output. No call needed.<br><br>"
    "Bhaskar"
)

# Step 3 — build timeline data point (ALL GEO version, stronger than old)
STEP3_BODY = (
    "Hi {{first_name}},<br><br>"
    "One data point: platforms that build their own creator data layer spend 4-6 months "
    "before they have coverage beyond Instagram. We cover IG, TikTok, and YouTube from day one - "
    "450M+ profiles.<br><br>"
    "Many platforms started with the same decision. Happy to share what they learned.<br><br>"
    "Bhaskar"
)

# Step 4 — data freshness + coverage angle
STEP4_BODY = (
    "Hi {{first_name}},<br><br>"
    "Two things most creator data vendors won't tell you: their profiles update weekly "
    "(ours update every 24-48h), and their regional coverage has gaps. "
    "We cover IG, TikTok, and YouTube across 50+ countries at city level.<br><br>"
    "If data freshness or regional coverage matters for {{company_name}} - "
    "worth comparing. Happy to walk you through it. 15 min.<br><br>"
    "Bhaskar"
)

# Step 5 — soft exit
STEP5_BODY = (
    "Hi {{first_name}}, last one from me.<br><br>"
    "If creator data isn't on the roadmap - totally fine. "
    "But if I'm reaching the wrong person, who handles data infrastructure at {{company_name}}? "
    "Usually CTO or Head of Product.<br><br>"
    "Either way - good luck with what you're building.<br><br>"
    "Bhaskar"
)

payload = {
    "sequences": [
        {
            "id": 7004560,
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "Creator data API for {{company_name}}",
            "email_body": STEP1_BODY,
        },
        {
            "id": 7004561,
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": STEP2_BODY,
        },
        {
            "id": 7004562,
            "seq_number": 3,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": STEP3_BODY,
        },
        {
            "id": 7004563,
            "seq_number": 4,
            "seq_delay_details": {"delay_in_days": 4},
            "subject": "",
            "email_body": STEP4_BODY,
        },
        {
            "id": 7004564,
            "seq_number": 5,
            "seq_delay_details": {"delay_in_days": 5},
            "subject": "",
            "email_body": STEP5_BODY,
        },
    ]
}


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print(f"=== Updating INFPLAT ALL GEO (campaign {CAMPAIGN_ID}) ===")
    print(f"\nStep 1 subject: {payload['sequences'][0]['subject']}")
    print(f"Step 1 body preview: {STEP1_BODY[:80]}...")

    resp = httpx.post(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/sequences",
        params={"api_key": API_KEY},
        json=payload,
        timeout=30,
    )
    print(f"\nStatus: {resp.status_code}")
    print(resp.text[:400])

    if resp.status_code not in (200, 201):
        print("\nERROR: Update failed")
        return

    # Verify
    print("\n--- Verifying ---")
    r = httpx.get(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/sequences",
        params={"api_key": API_KEY},
        timeout=30,
    )
    steps = r.json()
    for step in steps:
        snum = step.get("seq_number")
        variants = step.get("sequence_variants") or []
        if variants:
            for v in variants:
                print(f"  Step {snum} [{v.get('variant_label')}] subj: {v.get('subject','')[:60]}")
                print(f"             body: {v.get('email_body','')[:60]}...")
        else:
            subj = step.get("subject", "")[:60]
            body = step.get("email_body", "")[:60]
            print(f"  Step {snum} [base] subj: {subj}")
            print(f"             body: {body}...")

    print("\nDone. NOTE: Variant B was removed by API (add back manually in SmartLead UI if needed).")
    print("Variant B suggestion:")
    print("  Subject: 'engineering hours - {{company_name}}'")
    print("  Body: engineering hours angle with hard-coded social proof + named clients")


if __name__ == "__main__":
    main()
