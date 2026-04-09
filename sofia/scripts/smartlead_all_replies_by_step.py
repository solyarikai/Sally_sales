#!/usr/bin/env python3
"""
SmartLead — ALL Replies by Sequence Step (All Projects, All Time)
=================================================================
Pulls ALL campaigns, fetches statistics, maps replies to sequence steps.
Excludes: OOO, Do Not Contact, auto-replies.

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_all_replies_by_step.py"
"""

import os
import json
import time
from collections import defaultdict
from datetime import datetime

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Categories to EXCLUDE (OOO + Do Not Contact + auto-replies)
EXCLUDE_CATEGORIES = {
    "Out of Office",
    "out of office",
    "OOO",
    "ooo",
    "Do Not Contact",
    "do not contact",
    "DNC",
    "dnc",
    "Auto-Reply",
    "auto-reply",
    "Autoreplied",
    "autoreplied",
}

# Normalize: lowercase comparison
EXCLUDE_LOWER = {c.lower() for c in EXCLUDE_CATEGORIES}


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(3):
        try:
            resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  429 rate limit, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            print(f"  Timeout, retry {attempt+1}/3...")
            time.sleep(5)
    return None


def get_all_campaigns():
    data = api_get("/campaigns")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("campaigns", []))
    return []


def get_sequences(campaign_id):
    """Fetch sequence steps with subjects."""
    data = api_get(f"/campaigns/{campaign_id}/sequences")
    if not data:
        return {}
    # Build subject -> step number map
    step_map = {}
    if isinstance(data, list):
        for s in data:
            num = s.get("seq_number", 0)
            # Base subject
            base_subj = s.get("subject", "")
            if base_subj:
                step_map[base_subj.strip().lower()] = num
            # Variants
            for v in s.get("seq_variants", []):
                subj = v.get("subject", "")
                if subj:
                    step_map[subj.strip().lower()] = num
    return step_map


def get_all_statistics(campaign_id):
    all_records = []
    offset = 0
    limit = 500
    while True:
        data = api_get(f"/campaigns/{campaign_id}/statistics", {"offset": offset, "limit": limit})
        if not data:
            break
        if isinstance(data, dict):
            records = data.get("data", [])
            total = int(data.get("total_stats", 0))
        elif isinstance(data, list):
            records = data
            total = len(data)
        else:
            break
        if not records:
            break
        all_records.extend(records)
        if len(all_records) >= total or len(records) < limit:
            break
        offset += limit
        time.sleep(0.5)
    return all_records


def match_step(subject, step_map):
    """Match email subject to sequence step number."""
    if not subject:
        return None, "thread"

    subj_clean = subject.replace("Re: ", "").replace("RE: ", "").replace("re: ", "").strip().lower()

    if not subj_clean:
        return None, "thread"

    # Exact match
    if subj_clean in step_map:
        return step_map[subj_clean], subj_clean

    # Partial match (first 25 chars)
    for known_subj, step_num in step_map.items():
        # Remove template vars for matching
        known_clean = known_subj.replace("{{company_name}}", "").replace("{{first_name}}", "").strip()
        if known_clean and len(known_clean) > 5:
            if known_clean[:25] in subj_clean or subj_clean[:25] in known_clean:
                return step_num, known_subj

    return None, subj_clean


def is_excluded(category):
    """Check if lead_category should be excluded."""
    if not category:
        return False
    return category.strip().lower() in EXCLUDE_LOWER


def detect_auto_reply(subject, name):
    """Heuristic: detect OOO/auto-reply by subject patterns."""
    if not subject:
        return False
    s = subject.lower()
    ooo_patterns = [
        "out of office", "out of the office", "automatic reply",
        "auto-reply", "autoreply", "i am currently out",
        "on vacation", "on leave", "away from", "abwesenheit",
        "absence", "je suis absent", "fuera de la oficina",
        "currently unavailable", "maternity leave", "paternity leave",
    ]
    return any(p in s for p in ooo_patterns)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("=" * 80)
    print("  SMARTLEAD — ALL REPLIES BY SEQUENCE STEP (All Projects, All Time)")
    print("  Excluding: OOO, Do Not Contact, Auto-Replies")
    print("=" * 80)
    print()

    # 1. Get all campaigns, skip DRAFTED (no data)
    all_campaigns = get_all_campaigns()
    active_campaigns = [c for c in all_campaigns if c.get("status", "").upper() not in ("DRAFTED", "ARCHIVED")]
    print(f"Total campaigns: {len(all_campaigns)}, Active/Completed: {len(active_campaigns)}\n")

    # Data structures
    global_step_replies = defaultdict(int)       # step_num -> reply count
    global_step_details = defaultdict(list)      # step_num -> list of reply records
    campaign_summaries = []
    total_replies = 0
    total_excluded_ooo = 0
    total_excluded_dnc = 0
    total_excluded_auto = 0
    total_records = 0

    for camp in sorted(active_campaigns, key=lambda c: c.get("name", "")):
        cid = camp.get("id")
        cname = camp.get("name", f"#{cid}")
        status = camp.get("status", "unknown")

        print(f"  [{cid}] {cname} [{status}]...", end=" ", flush=True)

        # Get sequences for step mapping
        step_map = get_sequences(cid)
        time.sleep(0.3)

        # Get all statistics
        records = get_all_statistics(cid)
        time.sleep(0.3)

        if not records:
            print("0 records")
            continue

        total_records += len(records)

        # Filter to replies only
        replied = [r for r in records if r.get("reply_time")]

        if not replied:
            print(f"{len(records)} sent, 0 replies")
            continue

        camp_replies = []
        camp_excluded_ooo = 0
        camp_excluded_dnc = 0
        camp_excluded_auto = 0

        for r in replied:
            category = (r.get("lead_category") or "").strip()
            subject = r.get("email_subject", "")

            # Exclude OOO by category
            if category.lower() in ("out of office", "ooo"):
                camp_excluded_ooo += 1
                continue

            # Exclude Do Not Contact
            if category.lower() in ("do not contact", "dnc"):
                camp_excluded_dnc += 1
                continue

            # Exclude auto-replies by subject heuristics
            if detect_auto_reply(subject, r.get("lead_name", "")):
                camp_excluded_auto += 1
                continue

            # Map to step
            step_num, matched_subject = match_step(subject, step_map)

            # If step_num is None but it's a thread reply, try to figure out step
            step_label = f"Step {step_num}" if step_num is not None else "Unknown Step"

            camp_replies.append({
                "campaign_id": cid,
                "campaign": cname,
                "email": r.get("lead_email", ""),
                "name": r.get("lead_name", ""),
                "subject": subject,
                "step_num": step_num,
                "step_label": step_label,
                "matched_subject": matched_subject,
                "sent_time": r.get("sent_time", ""),
                "reply_time": r.get("reply_time", ""),
                "category": category,
            })

            global_step_replies[step_num] += 1
            global_step_details[step_num].append(camp_replies[-1])

        total_replies += len(camp_replies)
        total_excluded_ooo += camp_excluded_ooo
        total_excluded_dnc += camp_excluded_dnc
        total_excluded_auto += camp_excluded_auto

        print(f"{len(records)} sent, {len(replied)} replied, {len(camp_replies)} real "
              f"(excl: {camp_excluded_ooo} OOO, {camp_excluded_dnc} DNC, {camp_excluded_auto} auto)")

        if camp_replies:
            # Per-campaign step breakdown
            camp_by_step = defaultdict(int)
            for r in camp_replies:
                camp_by_step[r["step_num"]] += 1

            campaign_summaries.append({
                "name": cname,
                "id": cid,
                "status": status,
                "total_sent": len(records),
                "total_replied": len(replied),
                "real_replies": len(camp_replies),
                "excluded_ooo": camp_excluded_ooo,
                "excluded_dnc": camp_excluded_dnc,
                "excluded_auto": camp_excluded_auto,
                "by_step": dict(camp_by_step),
                "replies": camp_replies,
            })

    # === GLOBAL ANALYTICS ===
    print("\n")
    print("=" * 80)
    print("  GLOBAL RESULTS")
    print("=" * 80)
    print(f"\n  Total emails sent:        {total_records}")
    print(f"  Total real replies:       {total_replies}")
    print(f"  Excluded OOO:             {total_excluded_ooo}")
    print(f"  Excluded Do Not Contact:  {total_excluded_dnc}")
    print(f"  Excluded Auto-Replies:    {total_excluded_auto}")
    if total_records:
        print(f"  Real Reply Rate:          {total_replies/total_records*100:.2f}%")

    # === TOP STEPS ===
    print("\n")
    print("=" * 80)
    print("  TOP SEQUENCE STEPS BY REPLIES (excluding OOO, DNC, auto)")
    print("=" * 80)
    print(f"\n  {'Step':<20} {'Replies':>8} {'% of Total':>12}")
    print("  " + "-" * 42)

    for step_num, count in sorted(global_step_replies.items(), key=lambda x: -x[1]):
        label = f"Step {step_num}" if step_num is not None else "Unknown Step"
        pct = count / total_replies * 100 if total_replies else 0
        bar = "#" * int(pct / 2)
        print(f"  {label:<20} {count:>8} {pct:>11.1f}%  {bar}")

    # === STEP DETAILS: what subjects triggered replies ===
    print("\n")
    print("=" * 80)
    print("  REPLY SUBJECTS PER STEP")
    print("=" * 80)

    for step_num, replies in sorted(global_step_details.items(), key=lambda x: -len(x[1])):
        label = f"Step {step_num}" if step_num is not None else "Unknown Step"
        print(f"\n  --- {label} ({len(replies)} replies) ---")

        # Group by subject
        by_subject = defaultdict(list)
        for r in replies:
            by_subject[r["subject"][:80] or "(thread/empty)"].append(r)

        for subj, leads in sorted(by_subject.items(), key=lambda x: -len(x[1])):
            print(f"    [{len(leads):2}x] {subj}")

        # Group by campaign
        by_camp = defaultdict(int)
        for r in replies:
            by_camp[r["campaign"]] += 1
        print(f"    Campaigns: {dict(by_camp)}")

    # === CATEGORY BREAKDOWN of real replies ===
    print("\n")
    print("=" * 80)
    print("  CATEGORY BREAKDOWN (real replies only)")
    print("=" * 80)

    cat_counts = defaultdict(int)
    for replies in global_step_details.values():
        for r in replies:
            cat = r["category"] or "Uncategorized"
            cat_counts[cat] += 1

    print(f"\n  {'Category':<30} {'Count':>8} {'%':>8}")
    print("  " + "-" * 48)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = count / total_replies * 100 if total_replies else 0
        print(f"  {cat:<30} {count:>8} {pct:>7.1f}%")

    # === PER-CAMPAIGN BREAKDOWN ===
    print("\n")
    print("=" * 80)
    print("  PER-CAMPAIGN BREAKDOWN")
    print("=" * 80)
    print(f"\n  {'Campaign':<50} {'Sent':>6} {'Real':>6} {'Rate':>6}  Top Step")
    print("  " + "-" * 80)

    for cs in sorted(campaign_summaries, key=lambda x: -x["real_replies"]):
        rate = cs["real_replies"] / cs["total_sent"] * 100 if cs["total_sent"] else 0
        # Find top step
        top_step = max(cs["by_step"].items(), key=lambda x: x[1]) if cs["by_step"] else (None, 0)
        top_label = f"Step {top_step[0]}({top_step[1]})" if top_step[0] is not None else f"?({top_step[1]})"
        name = cs["name"][:49]
        print(f"  {name:<50} {cs['total_sent']:>6} {cs['real_replies']:>6} {rate:>5.1f}%  {top_label}")

    # === SAVE JSON ===
    report = {
        "generated": datetime.utcnow().isoformat(),
        "summary": {
            "total_campaigns_analyzed": len(campaign_summaries),
            "total_emails_sent": total_records,
            "total_real_replies": total_replies,
            "excluded_ooo": total_excluded_ooo,
            "excluded_dnc": total_excluded_dnc,
            "excluded_auto": total_excluded_auto,
            "real_reply_rate": round(total_replies / total_records * 100, 2) if total_records else 0,
        },
        "top_steps": {
            (f"Step {k}" if k is not None else "Unknown"): v
            for k, v in sorted(global_step_replies.items(), key=lambda x: -x[1])
        },
        "category_breakdown": dict(cat_counts),
        "campaigns": campaign_summaries,
    }

    out_path = "sofia/reports/smartlead_all_replies_by_step.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
