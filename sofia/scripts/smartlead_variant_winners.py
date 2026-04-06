#!/usr/bin/env python3
"""
SmartLead — Which A/B Variant Won
===================================
Сопоставляет:
  - A/B варианты из sequences (subject + body per variant)
  - Реальные ответы из statistics (reply_time + subject)

Показывает: какой именно вариант (A или B) принёс ответы.

Run: ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_variant_winners.py"
"""

import os
import json
import httpx
from collections import defaultdict

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

CAMPAIGNS = {
    "Global":   3050462,
    "India":    3063527,
    "Europe":   3064335,
    "Americas": 3071851,
    "ALL GEO":  3096746,
}


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_sequences(campaign_id):
    return api_get(f"/campaigns/{campaign_id}/sequences")


def get_all_statistics(campaign_id):
    all_records = []
    offset = 0
    limit = 500
    while True:
        data = api_get(f"/campaigns/{campaign_id}/statistics", {"offset": offset, "limit": limit})
        if not data or "data" not in data:
            break
        records = data["data"]
        if not records:
            break
        all_records.extend(records)
        total = int(data.get("total_stats", len(records)))
        if len(all_records) >= total or len(records) < limit:
            break
        offset += limit
    return all_records


def extract_variants_from_sequences(sequences_data):
    """
    Returns: {subject_normalized: {variant_label, step_number, subject, body_preview}}
    """
    variants = {}

    steps = sequences_data if isinstance(sequences_data, list) else sequences_data.get("data", [])

    for step in steps:
        step_num = step.get("seq_number", step.get("step_number", "?"))

        # Each step may have sequence_variants (A/B) or just email_body
        seq_variants = step.get("sequence_variants", [])

        if seq_variants:
            for v in seq_variants:
                subject = v.get("subject", "")
                body = v.get("email_body", "")
                label = v.get("variant_label", "A")
                key = subject.lower().strip()
                variants[key] = {
                    "variant_label": label,
                    "step_number": step_num,
                    "subject": subject,
                    "body_preview": body[:200].replace("<br>", " ").replace("\n", " ").strip(),
                }
        else:
            subject = step.get("subject", "")
            body = step.get("email_body", "")
            key = subject.lower().strip()
            variants[key] = {
                "variant_label": "A",
                "step_number": step_num,
                "subject": subject,
                "body_preview": body[:200].replace("<br>", " ").replace("\n", " ").strip(),
            }

    return variants


def normalize_subject(subject):
    """Remove 'RE: ' prefix and personalized first name."""
    s = subject.strip()
    if s.lower().startswith("re: "):
        s = s[4:]
    # Remove leading first name (e.g. "Meredith, 450M..." -> "450M...")
    if ", " in s[:30]:
        parts = s.split(", ", 1)
        if len(parts[0].split()) == 1:  # single word = first name
            s = parts[1]
    # Remove " - <company_name>" suffix for India style "Creator data for X"
    return s.strip()


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("\n=== A/B VARIANT WINNERS — OnSocial IM-FIRST AGENCIES ===\n")

    results = {}

    for name, cid in CAMPAIGNS.items():
        print(f"\n[{name}] campaign_id={cid}")

        # Get sequences structure
        try:
            seq_data = get_sequences(cid)
            variants_map = extract_variants_from_sequences(seq_data)
            print(f"  Sequence steps/variants found: {len(variants_map)}")
            for k, v in variants_map.items():
                print(f"    Step {v['step_number']} [{v['variant_label']}] subject: {v['subject'][:70]}")
        except Exception as e:
            print(f"  ERROR getting sequences: {e}")
            variants_map = {}

        # Get all statistics + filter replied
        print(f"  Fetching statistics...", end="")
        records = get_all_statistics(cid)
        replied = [r for r in records if r.get("reply_time")]
        print(f" {len(records)} records, {len(replied)} replies")

        # Map each reply to a variant
        variant_reply_counts = defaultdict(lambda: {"count": 0, "leads": []})

        for r in replied:
            raw_subject = r.get("email_subject", "")
            normalized = normalize_subject(raw_subject)
            norm_lower = normalized.lower().strip()

            # Try exact match first
            matched = variants_map.get(norm_lower)

            # If no exact match, try partial match
            if not matched:
                for vkey, vdata in variants_map.items():
                    # Strip personalization from variant subject too
                    vkey_norm = normalize_subject(vdata["subject"]).lower().strip()
                    if vkey_norm and (vkey_norm in norm_lower or norm_lower in vkey_norm):
                        matched = vdata
                        break

            if matched:
                key = f"Step {matched['step_number']} [{matched['variant_label']}]"
            else:
                key = f"UNKNOWN — {normalized[:60]}"

            variant_reply_counts[key]["count"] += 1
            variant_reply_counts[key]["leads"].append({
                "email": r.get("lead_email", ""),
                "reply_time": r.get("reply_time", "")[:10] if r.get("reply_time") else "",
                "subject": raw_subject[:70],
            })

        results[name] = {
            "total_records": len(records),
            "total_replies": len(replied),
            "variants_map": {k: v for k, v in variants_map.items()},
            "variant_reply_counts": dict(variant_reply_counts),
        }

    # Print final summary
    print("\n\n" + "="*70)
    print("FINAL: REPLIES BY A/B VARIANT")
    print("="*70)

    for camp_name in ["Global", "India", "Europe", "Americas", "ALL GEO"]:
        data = results.get(camp_name)
        if not data:
            continue

        print(f"\n{camp_name} ({data['total_replies']} replies / {data['total_records']} sent):")

        if not data["variant_reply_counts"]:
            print("  (no replies)")
            continue

        sorted_variants = sorted(
            data["variant_reply_counts"].items(),
            key=lambda x: -x[1]["count"]
        )

        for variant_key, vdata in sorted_variants:
            print(f"\n  {variant_key}: {vdata['count']} replies")
            for lead in vdata["leads"]:
                print(f"    {lead['email']}  [{lead['reply_time']}]")
                print(f"    subject: {lead['subject']}")

    # Save
    out = {camp: {
        "total_records": d["total_records"],
        "total_replies": d["total_replies"],
        "variant_wins": {k: {"count": v["count"], "leads": v["leads"]}
                         for k, v in d["variant_reply_counts"].items()}
    } for camp, d in results.items()}

    with open("sofia/projects/OnSocial/hub/im_agencies_variant_winners.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("\n\nSaved: sofia/projects/OnSocial/hub/im_agencies_variant_winners.json")


if __name__ == "__main__":
    main()
