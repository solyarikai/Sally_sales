#!/usr/bin/env python3
"""
Update IMAGENCY ALL GEO (#3096746) Variant A sequences.
Content: verbatim Global (3050462), signature → {{social_proof}}, typo fixed.
Delays: 0, 3, 3, 4, 5
"""
import requests, os

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = 3096746

SEQUENCES = [
    {
        "seq_number": 1,
        "subject": "{{first_name}}, 450M influencer profiles ready for your API",
        "email_body": "Hey {{first_name}},<br><br>When a client asks show me data on this creator - do you show something of yours, or a screenshot from HypeAuditor/Modash?<br><br>That is a trap. Once they figure out your tool - they buy it themselves and start wondering why they need an agency.<br><br>We power creator data for IM-first agencies: 450M+ profiles across Instagram, TikTok, YouTube. Your reports, your branding, your insight - not ours.<br><br>Would you like to see how it works for your current setup?<br><br>Kind regards,<br>Bhaskar Vishnu from OnSocial<br>Trusted by {{social_proof}}",
        "seq_delay_details": {"delay_in_days": 0}
    },
    {
        "seq_number": 2,
        "subject": "",
        "email_body": "Hey {{first_name}},<br><br>Two things agencies we work with care about most:<br><br>- Your reports stay under your brand. Our data plugs in via API - your clients see your logo, your analysis. Not ours.<br><br>We cover what clients actually question: real vs. fake audience, location down to city level, brand affinities, creator overlap across campaigns.<br><br>Modash, Obviously, and Ykone already run on our data for exactly this reason.<br><br>Open to a 15-min walkthrough based on your current setup?<br><br>Kind regards,<br>Bhaskar Vishnu from OnSocial<br>Trusted by {{social_proof}}",
        "seq_delay_details": {"delay_in_days": 3}
    },
    {
        "seq_number": 3,
        "subject": "",
        "email_body": "Hey,<br><br>Quick note on how it works: for any creator, one API call returns: credibility breakdown (real vs. mass followers vs. bots), audience by country, city, age, gender, language, brand affinities, engagement rates, creator overlap. All real-time.<br><br>Your team puts it in your own reports - clients see it as your data, not a third-party tool.<br><br>Worth 15 minutes this week to see it live on a creator you are currently evaluating?<br><br>Kind regards,<br>Bhaskar Vishnu from OnSocial<br>Trusted by {{social_proof}}",
        "seq_delay_details": {"delay_in_days": 3}
    },
    {
        "seq_number": 4,
        "subject": "",
        "email_body": "{{first_name}} - easier on LinkedIn?<br><br>Happy to pull a live breakdown on any creator you are currently evaluating.<br><br>Bhaskar<br>Sent from my iPhone",
        "seq_delay_details": {"delay_in_days": 4}
    },
    {
        "seq_number": 5,
        "subject": "",
        "email_body": "Hey {{first_name}}, last one.<br><br>If building a proprietary data layer is not on the agenda right now - no problem.<br><br>We are at onsocial.io if it ever comes up.<br><br>Bhaskar from OnSocial",
        "seq_delay_details": {"delay_in_days": 5}
    },
]

r = requests.post(
    f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences",
    params={"api_key": API_KEY},
    json={"sequences": SEQUENCES}
)
print(f"Status: {r.status_code}")
print(r.json())

# Verify
import time; time.sleep(1)
r2 = requests.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY})
steps = r2.json()
for s in steps:
    day = s.get("seq_delay_details", {}).get("delayInDays") or s.get("seq_delay_details", {}).get("delay_in_days", "?")
    subj = s.get("subject", "")
    body_tail = s.get("email_body", "")[-50:]
    print(f"  Step {s['seq_number']} day={day} subj={subj!r:.40} | ...{body_tail}")
