#!/usr/bin/env python3
"""
Update 5 remaining OnSocial campaigns:
- Keep Steps 1-2 as-is
- Replace Step 3 with new merged text
- Remove Steps 4-5
"""
import httpx, json, os, time

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY  = os.environ.get("SMARTLEAD_API_KEY", "")

# IMAGENCY template (agencies)
IMAGENCY_STEP3 = (
    "{{first_name}} - still here.<br><br>"
    "Two options: free trial if you want to test it solo, or 15 min with me "
    "- I'll show how your team gets audience breakdowns, fraud scores, and "
    "your own branded reports on any creator. 450M+ profiles, ultra-fresh data, "
    "best price on the market.<br><br>"
    "Bhaskar<br>Sent from my iPhone"
)

# INFPLAT template (platforms)
INFPLAT_STEP3 = (
    "{{first_name}} - still here.<br><br>"
    "Two options: free trial if you want to test it solo, or 15 min with me "
    "- I'll show how your product gets audience breakdowns, fraud scores, and "
    "full creator analytics via one API. 450M+ profiles, ultra-fresh data, "
    "best price on the market.<br><br>"
    "Bhaskar<br>Sent from my iPhone"
)

# Campaign ID -> (name, template)
CAMPAIGNS = {
    # Already done: 3050462 IM-FIRST AGENCIES #C
    # Already done: 3096746 IM-FIRST AGENCIES ALL GEO #C
    3063527: ("IM-FIRST AGENCIES INDIA #C",          IMAGENCY_STEP3),
    3059650: ("INDIA #C",                            INFPLAT_STEP3),
    3096747: ("INFLUENCER PLATFORMS ALL GEO #C",     INFPLAT_STEP3),
    3059277: ("LATAM #C",                            IMAGENCY_STEP3),
}


def api_get(path):
    for attempt in range(5):
        r = httpx.get(f"{BASE_URL}{path}", params={"api_key": API_KEY}, timeout=30)
        if r.status_code == 429:
            t = 5 * (attempt + 1)
            print(f"  [429 -> wait {t}s]", end=" ", flush=True)
            time.sleep(t)
            continue
        r.raise_for_status()
        return r.json()
    return None


def api_post(path, body):
    for attempt in range(5):
        r = httpx.post(f"{BASE_URL}{path}", params={"api_key": API_KEY}, json=body, timeout=30)
        if r.status_code == 429:
            t = 5 * (attempt + 1)
            print(f"  [429 -> wait {t}s]", end=" ", flush=True)
            time.sleep(t)
            continue
        r.raise_for_status()
        return r.json()
    return None


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set"); return

    for cid, (cname, step3_body) in CAMPAIGNS.items():
        print(f"\n{'='*60}")
        print(f"  {cname} (id={cid})")
        print(f"{'='*60}")

        # 1. Get current sequences
        seqs = api_get(f"/campaigns/{cid}/sequences")
        print(f"  Current steps: {[s.get('seq_number') for s in seqs]}")

        # 2. Keep steps 1-2 exactly as-is
        steps_12 = [s for s in seqs if s.get("seq_number") in (1, 2)]
        if len(steps_12) < 2:
            print(f"  WARNING: only {len(steps_12)} steps found for 1-2, skipping!")
            continue

        new_sequences = []
        for s in sorted(steps_12, key=lambda x: x["seq_number"]):
            sn = s["seq_number"]
            # Use sequence_variants if present, otherwise top-level
            variants = s.get("sequence_variants") or []
            if variants:
                subj = variants[0].get("subject", "")
                body = variants[0].get("email_body", "")
            else:
                subj = s.get("subject", "")
                body = s.get("email_body", "")

            delay_raw = s.get("seq_delay_details", {})
            delay_days = delay_raw.get("delay_in_days") or delay_raw.get("delayInDays") or 0

            new_sequences.append({
                "seq_number": sn,
                "seq_delay_details": {"delay_in_days": delay_days},
                "subject": subj,
                "email_body": body,
            })
            print(f"  Step {sn}: kept (delay={delay_days}d, body={len(body)} chars)")

        # 3. Add new step 3
        new_sequences.append({
            "seq_number": 3,
            "seq_delay_details": {"delay_in_days": 3},
            "subject": "",
            "email_body": step3_body,
        })
        print(f"  Step 3: NEW merged text ({len(step3_body)} chars)")

        # 4. POST full sequence (replaces all)
        result = api_post(f"/campaigns/{cid}/sequences", {"sequences": new_sequences})
        print(f"  Result: {result}")

        # 5. Verify
        time.sleep(0.5)
        check = api_get(f"/campaigns/{cid}/sequences")
        print(f"  Verify: {[s.get('seq_number') for s in check]} steps")
        for s in check:
            body = s.get("email_body", "")[:60]
            print(f"    Step {s.get('seq_number')}: {body}")

        time.sleep(0.3)

    print("\n\nDone! All 5 campaigns updated.")


if __name__ == "__main__":
    main()
