#!/usr/bin/env python3
"""
Fetch all active OnSocial campaigns + sequences from Step 3 onwards.
Output: JSON with campaign name, step number, subject, body.
"""

import os, json, time
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY  = os.environ.get("SMARTLEAD_API_KEY", "")

ONSOCIAL_KEYWORDS = ["onsocial", "on social", "os |", "os|"]
EXCLUDE_CAMP = ["russian"]


def api_get(path, params=None):
    q = {"api_key": API_KEY, **(params or {})}
    for attempt in range(5):
        try:
            r = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if r.status_code == 429:
                t = 5 * (attempt + 1)
                print(f"[429→{t}s]", end=" ", flush=True)
                time.sleep(t)
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3)
    return None


def is_onsocial(name):
    n = (name or "").lower()
    return any(kw in n for kw in ONSOCIAL_KEYWORDS)


def is_russian(name):
    n = (name or "").lower()
    return any(kw in n for kw in EXCLUDE_CAMP)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set"); return

    print("=" * 70)
    print("  Fetch OnSocial Active Campaigns — Sequences Step 3+")
    print("=" * 70)

    # 1. Get all campaigns
    print("\nStep 1: Fetching all campaigns...")
    data = api_get("/campaigns")
    if isinstance(data, dict):
        campaigns = data.get("data", data.get("campaigns", []))
    elif isinstance(data, list):
        campaigns = data
    else:
        campaigns = []

    print(f"  Total campaigns: {len(campaigns)}")

    # 2. Filter active OnSocial non-Russian
    active_os = [
        c for c in campaigns
        if c.get("status", "").upper() == "ACTIVE"
        and is_onsocial(c.get("name", ""))
        and not is_russian(c.get("name", ""))
    ]
    print(f"  Active OnSocial (non-Russian): {len(active_os)}")
    for c in active_os:
        print(f"    [{c['id']}] {c['name']}")

    # 3. For each campaign, fetch sequences
    print(f"\nStep 2: Fetching sequences for {len(active_os)} campaigns...")

    results = []

    for i, camp in enumerate(sorted(active_os, key=lambda x: x.get("name", ""))):
        cid   = camp["id"]
        cname = camp["name"]
        print(f"\n  [{i+1}/{len(active_os)}] {cname}")

        seqs = api_get(f"/campaigns/{cid}/sequences")
        time.sleep(0.3)

        if not seqs or not isinstance(seqs, list):
            print("    (no sequences)")
            continue

        steps_3plus = [s for s in seqs if (s.get("seq_number") or 0) >= 3]
        if not steps_3plus:
            print(f"    (only {len(seqs)} steps, none ≥ 3)")
            continue

        camp_steps = []
        for step in sorted(steps_3plus, key=lambda s: s.get("seq_number", 0)):
            seq_num  = step.get("seq_number")
            delay    = step.get("seq_delay_details", {})
            variants = step.get("seq_variants", [])

            # Primary variant (index 0) or the step itself
            if variants:
                subj = variants[0].get("subject", "")
                body = variants[0].get("email_body", "")
            else:
                subj = step.get("subject", "")
                body = step.get("email_body", "")

            print(f"    Step {seq_num}: {subj[:70]}")

            camp_steps.append({
                "seq_number": seq_num,
                "delay":      delay,
                "subject":    subj,
                "body":       body,
                "variants_count": len(variants),
            })

        results.append({
            "id":     cid,
            "name":   cname,
            "status": camp.get("status"),
            "steps":  camp_steps,
        })

    # 4. Save JSON
    out = "sofia/reports/onsocial_sequences_step3plus.json"
    os.makedirs("sofia/reports", exist_ok=True)
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nSaved: {out}")
    print(f"Campaigns with step 3+: {len(results)}")

    # 5. Print summary table
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for camp in results:
        print(f"\n  {camp['name']}")
        for s in camp["steps"]:
            print(f"    Step {s['seq_number']}: {s['subject'][:65]}")


if __name__ == "__main__":
    main()
