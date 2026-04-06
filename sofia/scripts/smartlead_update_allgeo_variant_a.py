#!/usr/bin/env python3
"""
Update ALL GEO Variant A — Steps 1 & 2
========================================
Step 1 [A]: proven Global subject + "That's a trap" body
Step 2 [A]: "easier to show than explain / 10 min / no hard feelings"

Run: ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_update_allgeo_variant_a.py"
"""

import os
import json
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
CAMPAIGN_ID = 3096746

# Variant IDs from sequences fetch
STEP1_VARIANT_A_ID = 5297310
STEP2_VARIANT_A_ID = 5297312

# Sequence step IDs
STEP1_SEQ_ID = 7004573
STEP2_SEQ_ID = 7004574

NEW_STEP1_A = {
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
}

NEW_STEP2_A = {
    "subject": "",
    "email_body": (
        "Hi {{first_name}}, easier to show than explain.<br><br>"
        "I can build a sample report for {{company_name}} - your logo, your colors, real creator data.<br>"
        "Takes me 10 minutes.<br>"
        "If it's useful, great. If not - no hard feelings. Want me to put one together?<br><br>"
        "Bhaskar"
    ),
}


def api_post(path, payload):
    resp = httpx.post(
        f"{BASE_URL}{path}",
        params={"api_key": API_KEY},
        json=payload,
        timeout=30,
    )
    return resp.status_code, resp.text


def api_put(path, payload):
    resp = httpx.put(
        f"{BASE_URL}{path}",
        params={"api_key": API_KEY},
        json=payload,
        timeout=30,
    )
    return resp.status_code, resp.text


def api_patch(path, payload):
    resp = httpx.patch(
        f"{BASE_URL}{path}",
        params={"api_key": API_KEY},
        json=payload,
        timeout=30,
    )
    return resp.status_code, resp.text


def try_update_variant(variant_id, data, label):
    print(f"\n--- Updating {label} (variant id={variant_id}) ---")
    print(f"  Subject: {data['subject'][:60] or '(thread)'}")

    # Try POST to variant update endpoint
    for method_name, method in [("POST", api_post), ("PUT", api_put), ("PATCH", api_patch)]:
        status, body = method(f"/campaigns/{CAMPAIGN_ID}/sequences/variants/{variant_id}", data)
        print(f"  {method_name} /variants/{variant_id} -> {status}: {body[:200]}")
        if status in (200, 201):
            return True

    # Try updating via sequence step
    for method_name, method in [("POST", api_post), ("PUT", api_put)]:
        seq_id = STEP1_SEQ_ID if "Step 1" in label else STEP2_SEQ_ID
        payload = {**data, "variant_label": "A", "variant_id": variant_id}
        status, body = method(f"/campaigns/{CAMPAIGN_ID}/sequences/{seq_id}", payload)
        print(f"  {method_name} /sequences/{seq_id} -> {status}: {body[:200]}")
        if status in (200, 201):
            return True

    return False


STEP2_B_BODY = (
    "<div>Hi {{first_name}}, easier to show than explain.</div><div><br></div>"
    "<div>I can build a sample report for {{company_name}} - your logo, your colors, real creator data. </div>"
    "<div>Takes me 10 minutes.</div>"
    "<div>If it's useful, great. If not - no hard feelings. Want me to put one together?</div>"
    "<div><br></div><div>Bhaskar</div><div><br></div>"
)

STEP1_B_BODY = (
    "<div>Hi {{first_name}},</div><div><br></div>"
    "<div>What happens when a {{company_name}} client Googles \"HypeAuditor pricing\" "
    "and realizes they can buy it themselves for $300/month?</div><div><br></div>"
    "<div>Smart agencies solved this - they white-label our creator data under their own brand. "
    "Client never sees the source.</div><div><br></div>"
    "<div>Worth exploring?</div><div><br></div>"
    "<div>Kind regards,</div><div>Bhaskar Vishnu from OnSocial</div>"
    "<div>Trusted by {{social_proof}}</div><div><br></div>"
)

# Steps 3-5: no variants, keep existing content
STEP3_BODY = (
    "Hi {{first_name}},<br><br>"
    "One pattern we see: agencies that give clients access to branded analytics have 40% higher retention. "
    "The client builds workflows around YOUR tool - switching cost goes up.<br><br>"
    "Happy to show you how they set it up.<br><br>"
    "Bhaskar"
)
STEP4_BODY = (
    "Hi {{first_name}},<br><br>"
    "Some agencies try building their own analytics dashboard. Typical timeline: 3-4 months of dev work, "
    "covers one platform (usually just Instagram), and needs constant maintenance.<br><br>"
    "Our white-label covers IG, TikTok, and YouTube - 450M+ profiles, fraud scoring, audience demographics. "
    "Zero dev work on your side.<br><br>"
    "If worth comparing - happy to walk you through it. 15 min.<br><br>"
    "Bhaskar"
)
STEP5_BODY = (
    "Hi {{first_name}}, last one from me.<br><br>"
    "If white-label analytics aren't a priority right now - no worries. "
    "But if I'm reaching the wrong person, who handles tool decisions at {{company_name}}?<br><br>"
    "Either way - wishing {{company_name}} continued growth.<br><br>"
    "Bhaskar from OnSocial"
)


def try_full_sequence_update():
    """Try updating the full sequences array via POST."""
    print("\n--- Trying full sequence update (all 5 steps) ---")

    payload = {
        "sequences": [
            {
                "id": STEP1_SEQ_ID,
                "seq_number": 1,
                "seq_delay_details": {"delay_in_days": 0},
                "subject": "",
                "email_body": "",
                "sequence_variants": [
                    {
                        "id": STEP1_VARIANT_A_ID,
                        "variant_label": "A",
                        "subject": NEW_STEP1_A["subject"],
                        "email_body": NEW_STEP1_A["email_body"],
                    },
                    {
                        "id": 5297311,
                        "variant_label": "B",
                        "subject": "quick thought - {{company_name}}",
                        "email_body": STEP1_B_BODY,
                    },
                ],
            },
            {
                "id": STEP2_SEQ_ID,
                "seq_number": 2,
                "seq_delay_details": {"delay_in_days": 3},
                "subject": "",
                "email_body": "",
                "sequence_variants": [
                    {
                        "id": STEP2_VARIANT_A_ID,
                        "variant_label": "A",
                        "subject": "",
                        "email_body": NEW_STEP2_A["email_body"],
                    },
                    {
                        "id": 5297313,
                        "variant_label": "B",
                        "subject": "",
                        "email_body": STEP2_B_BODY,
                    },
                ],
            },
            {
                "id": 7004575,
                "seq_number": 3,
                "seq_delay_details": {"delay_in_days": 3},
                "subject": "Re: creator analytics - {{company_name}}",
                "email_body": STEP3_BODY,
            },
            {
                "id": 7004576,
                "seq_number": 4,
                "seq_delay_details": {"delay_in_days": 4},
                "subject": "Re: creator analytics - {{company_name}}",
                "email_body": STEP4_BODY,
            },
            {
                "id": 7004577,
                "seq_number": 5,
                "seq_delay_details": {"delay_in_days": 5},
                "subject": "Re: creator analytics - {{company_name}}",
                "email_body": STEP5_BODY,
            },
        ]
    }

    for method_name, method in [("POST", api_post), ("PUT", api_put)]:
        status, body = method(f"/campaigns/{CAMPAIGN_ID}/sequences", payload)
        print(f"  {method_name} /sequences -> {status}: {body[:400]}")
        if status in (200, 201):
            return True

    return False


def verify_update():
    """Fetch sequences and verify the change took effect."""
    print("\n--- Verifying ---")
    resp = httpx.get(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/sequences",
        params={"api_key": API_KEY},
        timeout=30,
    )
    data = resp.json()
    steps = data if isinstance(data, list) else data.get("data", [])

    for step in steps:
        snum = step.get("seq_number")
        variants = step.get("sequence_variants") or []
        for v in variants:
            if v.get("variant_label") == "A":
                subj = v.get("subject", "")
                body_preview = v.get("email_body", "")[:80]
                print(f"  Step {snum} [A] subject: {subj}")
                print(f"            body: {body_preview}...")


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print(f"=== Updating ALL GEO Variant A (campaign {CAMPAIGN_ID}) ===")
    print(f"\nNew Step 1 [A] subject: {NEW_STEP1_A['subject']}")
    print(f"New Step 2 [A] body preview: {NEW_STEP2_A['email_body'][:60]}...")

    success = try_full_sequence_update()

    if not success:
        print("\n  Full update failed, trying individual variant endpoints...")
        try_update_variant(STEP1_VARIANT_A_ID, NEW_STEP1_A, "Step 1 [A]")
        try_update_variant(STEP2_VARIANT_A_ID, NEW_STEP2_A, "Step 2 [A]")

    verify_update()


if __name__ == "__main__":
    main()
