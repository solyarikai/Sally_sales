#!/usr/bin/env python3
import httpx, json, os

API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = 3096746

payload = {
    "sequences": [
        {
            "id": 7004573,
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "subject": "{{first_name}}, 450M influencer profiles ready for your API",
            "email_body": (
                "Hey {{first_name}},<br><br>"
                "When a client asks \"show me data on this creator\" - do you show something of yours, "
                "or a screenshot from HypeAuditor/Modash?<br><br>"
                "That is a trap. Once they figure out your tool - they buy it themselves and "
                "start wondering why they need an agency.<br><br>"
                "We power creator data for IM-first agencies: 450M+ profiles across Instagram, "
                "TikTok, YouTube. Your reports, your branding, your insight - not ours.<br><br>"
                "Would you like to see how it works for your current setup?<br><br>"
                "Kind regards,<br>"
                "Bhaskar Vishnu from OnSocial<br>"
                "Trusted by Viral Nation, Whalar and Billion Dollar Boy"
            ),
        },
        {
            "id": 7004574,
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": (
                "Hi {{first_name}}, easier to show than explain.<br><br>"
                "I can build a sample report for {{company_name}} - your logo, your colors, real creator data.<br>"
                "Takes me 10 minutes.<br>"
                "If it's useful, great. If not - no hard feelings. Want me to put one together?<br><br>"
                "Bhaskar"
            ),
        },
        {
            "id": 7004575,
            "seq_number": 3,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "Re: creator analytics - {{company_name}}",
            "email_body": (
                "Hi {{first_name}},<br><br>"
                "One pattern we see: agencies that give clients access to branded analytics have 40% higher retention. "
                "The client builds workflows around YOUR tool - switching cost goes up.<br><br>"
                "Happy to show you how they set it up.<br><br>"
                "Bhaskar"
            ),
        },
        {
            "id": 7004576,
            "seq_number": 4,
            "seq_delay_details": {"delay_in_days": 4},
            "subject": "Re: creator analytics - {{company_name}}",
            "email_body": (
                "Hi {{first_name}},<br><br>"
                "Some agencies try building their own analytics dashboard. Typical timeline: 3-4 months of dev work, "
                "covers one platform (usually just Instagram), and needs constant maintenance.<br><br>"
                "Our white-label covers IG, TikTok, and YouTube - 450M+ profiles, fraud scoring, audience demographics. "
                "Zero dev work on your side.<br><br>"
                "If worth comparing - happy to walk you through it. 15 min.<br><br>"
                "Bhaskar"
            ),
        },
        {
            "id": 7004577,
            "seq_number": 5,
            "seq_delay_details": {"delay_in_days": 5},
            "subject": "Re: creator analytics - {{company_name}}",
            "email_body": (
                "Hi {{first_name}}, last one from me.<br><br>"
                "If white-label analytics aren't a priority right now - no worries. "
                "But if I'm reaching the wrong person, who handles tool decisions at {{company_name}}?<br><br>"
                "Either way - wishing {{company_name}} continued growth.<br><br>"
                "Bhaskar from OnSocial"
            ),
        },
    ]
}

resp = httpx.post(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY}, json=payload, timeout=30)
print(f"Status: {resp.status_code}")
print(resp.text[:600])

# Verify
print("\n--- Verifying ---")
r = httpx.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/sequences", params={"api_key": API_KEY}, timeout=30)
steps = r.json()
for step in steps:
    snum = step.get("seq_number")
    variants = step.get("sequence_variants") or []
    base_subj = step.get("subject", "")
    base_body = step.get("email_body", "")[:60]
    if variants:
        for v in variants:
            print(f"Step {snum} [{v.get('variant_label')}] subject: {v.get('subject','')[:60]}")
            print(f"           body: {v.get('email_body','')[:60]}...")
    else:
        print(f"Step {snum} [base] subject: {base_subj[:60]}")
        print(f"           body: {base_body}...")
