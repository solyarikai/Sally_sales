#!/usr/bin/env python3
"""
Pull reply analytics for all IMAGENCY campaigns to determine Variant A winner.
Campaigns: Global #3050462, Europe #3064335, India #3063527, US/LATAM #3071851
"""
import requests, os, json, time

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"

CAMPAIGNS = [
    {"id": 3050462, "name": "Global"},
    {"id": 3064335, "name": "Europe"},
    {"id": 3063527, "name": "India"},
    {"id": 3071851, "name": "US/LATAM"},
]

def get_all_stats(campaign_id):
    stats = []
    offset = 0
    limit = 500
    while True:
        time.sleep(1)
        r = requests.get(
            f"{BASE}/campaigns/{campaign_id}/statistics",
            params={"api_key": API_KEY, "offset": offset, "limit": limit}
        )
        if r.status_code == 429:
            print(f"  429 - sleeping 10s...")
            time.sleep(10)
            continue
        data = r.json()
        batch = data if isinstance(data, list) else data.get("data", [])
        if not batch:
            break
        stats.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return stats

def get_sequences(campaign_id):
    r = requests.get(f"{BASE}/campaigns/{campaign_id}/sequences", params={"api_key": API_KEY})
    return r.json()

results = {}

for camp in CAMPAIGNS:
    cid = camp["id"]
    name = camp["name"]
    print(f"\n=== {name} ({cid}) ===")

    # Get sequence subjects
    seqs = get_sequences(cid)
    step_subjects = {}
    for s in seqs:
        num = s.get("seq_number", 0)
        variants = s.get("seq_variants", [])
        for v in variants:
            subj = v.get("subject", "")
            if subj:
                step_subjects[subj] = f"Step {num}"
        # also base subject
        base_subj = s.get("subject", "")
        if base_subj:
            step_subjects[base_subj] = f"Step {num}"
    print(f"  Subjects map: {step_subjects}")

    # Get stats
    stats = get_all_stats(cid)
    total = len(stats)
    replies = [x for x in stats if x.get("reply_time")]
    print(f"  Total: {total}, Replies: {len(replies)}")

    by_step = {}
    for r in replies:
        subj = r.get("email_subject", "")
        # Match step by subject prefix
        step = "UNKNOWN"
        for known_subj, s_label in step_subjects.items():
            # strip {{company_name}} placeholder for matching
            known_clean = known_subj.replace("{{company_name}}", "").replace("Re: ", "").strip().lower()
            subj_clean = subj.replace("Re: ", "").strip().lower()
            if known_clean and known_clean[:20] in subj_clean:
                step = s_label
                break
        # fallback: check if subject is empty or "Re:" = thread (steps 2-5)
        if step == "UNKNOWN":
            if not subj or subj.lower().startswith("re:"):
                step = "Step 2-5 (thread)"
            else:
                # Step 1 variant detection
                if "creator analytics" in subj.lower():
                    step = "Step 1A"
                elif "quick thought" in subj.lower():
                    step = "Step 1B"
                else:
                    step = f"Step 1? ({subj[:40]})"

        by_step[step] = by_step.get(step, 0) + 1

    results[name] = {"id": cid, "total": total, "replies": len(replies), "by_step": by_step}
    print(f"  By step: {by_step}")

# Summary
print("\n\n=== SUMMARY ===")
print(f"{'Campaign':<15} {'Sent':>6} {'Replies':>8} {'Rate':>7}  By Step")
for name, d in results.items():
    rate = d["replies"] / d["total"] * 100 if d["total"] else 0
    print(f"{name:<15} {d['total']:>6} {d['replies']:>8} {rate:>6.2f}%  {d['by_step']}")

# Save
out_path = "sofia/projects/OnSocial/hub/imagency_replies_by_step.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to {out_path}")
