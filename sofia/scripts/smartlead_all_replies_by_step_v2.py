#!/usr/bin/env python3
"""
SmartLead — ALL Replies by Sequence Step v2 (Optimized)
========================================================
Two-pass approach:
  Pass 1: Quick scan — get sequence-analytics for all campaigns (1 request each)
  Pass 2: Deep dive — fetch individual statistics only for campaigns with replies

Excludes: OOO, Do Not Contact, Auto-Replies

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_all_replies_by_step_v2.py"
"""

import os
import json
import time
from collections import defaultdict
from datetime import datetime

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

EXCLUDE_CATS_LOWER = {
    "out of office", "ooo",
    "do not contact", "dnc",
    "auto-reply", "autoreplied",
}

OOO_PATTERNS = [
    "out of office", "out of the office", "automatic reply",
    "auto-reply", "autoreply", "i am currently out",
    "on vacation", "on leave", "away from", "abwesenheit",
    "absence", "je suis absent", "fuera de la oficina",
    "currently unavailable", "maternity leave", "paternity leave",
]


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(4):
        try:
            resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"    [429 → wait {wait}s]", end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3)
    return None


def get_all_campaigns():
    data = api_get("/campaigns")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("campaigns", []))
    return []


def get_sequences(campaign_id):
    """Fetch sequence steps → subject → step_number map."""
    data = api_get(f"/campaigns/{campaign_id}/sequences")
    if not data or not isinstance(data, list):
        return {}
    step_map = {}
    for s in data:
        num = s.get("seq_number", 0)
        base_subj = s.get("subject", "")
        if base_subj:
            step_map[base_subj.strip().lower()] = num
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
        time.sleep(0.3)
    return all_records


def match_step(subject, step_map):
    if not subject:
        return None
    subj_clean = subject.lower()
    for prefix in ("re: ", "re:", "fwd: ", "fw: "):
        while subj_clean.startswith(prefix):
            subj_clean = subj_clean[len(prefix):].strip()
    if not subj_clean:
        return None
    if subj_clean in step_map:
        return step_map[subj_clean]
    for known_subj, step_num in step_map.items():
        known_clean = known_subj.replace("{{company_name}}", "").replace("{{first_name}}", "").replace("{{last_name}}", "").strip()
        if known_clean and len(known_clean) > 5:
            if known_clean[:25] in subj_clean or subj_clean[:25] in known_clean:
                return step_num
    return None


def is_excluded(category):
    if not category:
        return False
    return category.strip().lower() in EXCLUDE_CATS_LOWER


def is_auto_reply(subject):
    if not subject:
        return False
    s = subject.lower()
    return any(p in s for p in OOO_PATTERNS)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("=" * 80)
    print("  SMARTLEAD — ALL REPLIES BY SEQUENCE STEP v2")
    print("  Excluding: OOO, Do Not Contact, Auto-Replies")
    print("=" * 80)
    print()

    # 1. Get all campaigns
    all_campaigns = get_all_campaigns()
    active = [c for c in all_campaigns
              if c.get("status", "").upper() not in ("DRAFTED",)]
    print(f"Total: {len(all_campaigns)}, Processing: {len(active)}")

    # PASS 1: Quick scan with sequence-analytics to find campaigns with replies
    print("\n--- PASS 1: Quick scan (sequence-analytics) ---\n")
    campaigns_with_replies = []

    for i, camp in enumerate(sorted(active, key=lambda c: c.get("name", ""))):
        cid = camp.get("id")
        cname = camp.get("name", f"#{cid}")
        status = camp.get("status", "?")

        if (i + 1) % 50 == 0:
            print(f"  Scanned {i+1}/{len(active)}...")

        # Use sequence-analytics (all time: 2020-01-01 to today)
        data = api_get(f"/campaigns/{cid}/sequence-analytics", {
            "start_date": "2020-01-01 00:00:00",
            "end_date": datetime.utcnow().strftime("%Y-%m-%d 23:59:59"),
        })
        time.sleep(0.2)

        if not data:
            continue

        # Check if any step has replies
        total_replies = 0
        step_data = []
        if isinstance(data, list):
            for step in data:
                rc = int(step.get("reply_count", 0))
                total_replies += rc
                if rc > 0:
                    step_data.append(step)

        if total_replies > 0:
            campaigns_with_replies.append({
                "id": cid,
                "name": cname,
                "status": status,
                "total_replies_raw": total_replies,
                "step_data": step_data,
            })
            print(f"  [{cid}] {cname[:50]} — {total_replies} raw replies")

    print(f"\n  Pass 1 done: {len(campaigns_with_replies)} campaigns have replies\n")

    # PASS 2: Deep dive — fetch individual records for reply-having campaigns
    print("--- PASS 2: Deep dive (fetch individual reply records) ---\n")

    global_step_replies = defaultdict(int)
    global_step_details = defaultdict(list)
    total_real_replies = 0
    total_excluded_ooo = 0
    total_excluded_dnc = 0
    total_excluded_auto = 0
    total_sent = 0
    campaign_results = []

    for ci, camp_info in enumerate(campaigns_with_replies):
        cid = camp_info["id"]
        cname = camp_info["name"]

        print(f"  [{ci+1}/{len(campaigns_with_replies)}] {cname[:55]}...", end=" ", flush=True)

        step_map = get_sequences(cid)
        time.sleep(0.2)

        records = get_all_statistics(cid)
        time.sleep(0.3)

        if not records:
            print("no data")
            continue

        total_sent += len(records)
        replied = [r for r in records if r.get("reply_time")]

        camp_replies = []
        camp_ooo = 0
        camp_dnc = 0
        camp_auto = 0

        for r in replied:
            category = (r.get("lead_category") or "").strip()
            subject = r.get("email_subject", "")

            # Exclude OOO
            cat_lower = category.lower()
            if cat_lower in ("out of office", "ooo"):
                camp_ooo += 1
                continue

            # Exclude DNC
            if cat_lower in ("do not contact", "dnc"):
                camp_dnc += 1
                continue

            # Exclude auto-replies by subject
            if is_auto_reply(subject):
                camp_auto += 1
                continue

            step_num = match_step(subject, step_map)
            step_label = f"Step {step_num}" if step_num is not None else "Unknown"

            reply_rec = {
                "campaign_id": cid,
                "campaign": cname,
                "email": r.get("lead_email", ""),
                "name": r.get("lead_name", ""),
                "subject": subject,
                "step_num": step_num,
                "step_label": step_label,
                "sent_time": r.get("sent_time", ""),
                "reply_time": r.get("reply_time", ""),
                "category": category,
            }

            camp_replies.append(reply_rec)
            global_step_replies[step_num] += 1
            global_step_details[step_num].append(reply_rec)

        total_real_replies += len(camp_replies)
        total_excluded_ooo += camp_ooo
        total_excluded_dnc += camp_dnc
        total_excluded_auto += camp_auto

        print(f"{len(records)} sent, {len(replied)} replied, {len(camp_replies)} real "
              f"(excl: {camp_ooo} OOO, {camp_dnc} DNC, {camp_auto} auto)")

        if camp_replies:
            by_step = defaultdict(int)
            for r in camp_replies:
                by_step[r["step_num"]] += 1

            campaign_results.append({
                "name": cname,
                "id": cid,
                "status": camp_info["status"],
                "total_sent": len(records),
                "total_replied": len(replied),
                "real_replies": len(camp_replies),
                "excluded_ooo": camp_ooo,
                "excluded_dnc": camp_dnc,
                "excluded_auto": camp_auto,
                "by_step": {str(k): v for k, v in by_step.items()},
            })

    # === REPORT ===
    print("\n\n")
    print("=" * 80)
    print("  GLOBAL RESULTS")
    print("=" * 80)
    print(f"\n  Campaigns with replies:   {len(campaigns_with_replies)}")
    print(f"  Total emails sent:        {total_sent}")
    print(f"  Total real replies:       {total_real_replies}")
    print(f"  Excluded OOO:             {total_excluded_ooo}")
    print(f"  Excluded Do Not Contact:  {total_excluded_dnc}")
    print(f"  Excluded Auto-Replies:    {total_excluded_auto}")
    if total_sent:
        print(f"  Real Reply Rate:          {total_real_replies/total_sent*100:.2f}%")

    # TOP STEPS
    print("\n")
    print("=" * 80)
    print("  TOP SEQUENCE STEPS BY REAL REPLIES")
    print("=" * 80)
    print(f"\n  {'Step':<20} {'Replies':>8} {'% of Total':>12}")
    print("  " + "-" * 42)

    sorted_steps = sorted(global_step_replies.items(), key=lambda x: -x[1])
    for step_num, count in sorted_steps:
        label = f"Step {step_num}" if step_num is not None else "Unknown Step"
        pct = count / total_real_replies * 100 if total_real_replies else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:<20} {count:>8} {pct:>11.1f}%  {bar}")

    # STEP DETAILS
    print("\n")
    print("=" * 80)
    print("  REPLY SUBJECTS PER STEP (top 10 subjects each)")
    print("=" * 80)

    for step_num, replies in sorted(global_step_details.items(), key=lambda x: -len(x[1])):
        label = f"Step {step_num}" if step_num is not None else "Unknown Step"
        print(f"\n  --- {label} ({len(replies)} replies) ---")

        by_subject = defaultdict(int)
        for r in replies:
            subj = r["subject"][:80] or "(thread/empty)"
            by_subject[subj] += 1

        for subj, cnt in sorted(by_subject.items(), key=lambda x: -x[1])[:10]:
            print(f"    [{cnt:3}x] {subj}")

        by_camp = defaultdict(int)
        for r in replies:
            by_camp[r["campaign"]] += 1
        top_camps = sorted(by_camp.items(), key=lambda x: -x[1])[:5]
        print(f"    Top campaigns: {', '.join(f'{n}({c})' for n, c in top_camps)}")

    # CATEGORY BREAKDOWN
    print("\n")
    print("=" * 80)
    print("  CATEGORY BREAKDOWN (real replies only)")
    print("=" * 80)

    cat_counts = defaultdict(int)
    for replies in global_step_details.values():
        for r in replies:
            cat = r["category"] or "Uncategorized"
            cat_counts[cat] += 1

    print(f"\n  {'Category':<35} {'Count':>8} {'%':>8}")
    print("  " + "-" * 53)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = count / total_real_replies * 100 if total_real_replies else 0
        print(f"  {cat:<35} {count:>8} {pct:>7.1f}%")

    # PER-CAMPAIGN TABLE
    print("\n")
    print("=" * 80)
    print("  TOP 30 CAMPAIGNS BY REAL REPLIES")
    print("=" * 80)
    print(f"\n  {'Campaign':<55} {'Sent':>6} {'Real':>6} {'Rate':>6}  Top Step")
    print("  " + "-" * 85)

    for cs in sorted(campaign_results, key=lambda x: -x["real_replies"])[:30]:
        rate = cs["real_replies"] / cs["total_sent"] * 100 if cs["total_sent"] else 0
        bs = cs["by_step"]
        if bs:
            top_k = max(bs.items(), key=lambda x: x[1])
            top_label = f"Step {top_k[0]}({top_k[1]})"
        else:
            top_label = "-"
        name = cs["name"][:54]
        print(f"  {name:<55} {cs['total_sent']:>6} {cs['real_replies']:>6} {rate:>5.1f}%  {top_label}")

    # SAVE JSON
    report = {
        "generated": datetime.utcnow().isoformat(),
        "summary": {
            "total_campaigns_with_replies": len(campaigns_with_replies),
            "total_campaigns_analyzed": len(campaign_results),
            "total_emails_sent": total_sent,
            "total_real_replies": total_real_replies,
            "excluded_ooo": total_excluded_ooo,
            "excluded_dnc": total_excluded_dnc,
            "excluded_auto": total_excluded_auto,
            "real_reply_rate_pct": round(total_real_replies / total_sent * 100, 2) if total_sent else 0,
        },
        "top_steps": [
            {
                "step": step_num,
                "label": f"Step {step_num}" if step_num is not None else "Unknown",
                "replies": count,
                "pct": round(count / total_real_replies * 100, 1) if total_real_replies else 0,
            }
            for step_num, count in sorted_steps
        ],
        "category_breakdown": dict(cat_counts),
        "campaigns": campaign_results,
        "all_replies": [
            r for replies in global_step_details.values() for r in replies
        ],
    }

    out_path = "sofia/reports/smartlead_all_replies_by_step.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n\nReport saved: {out_path}")
    print(f"Total real replies in JSON: {len(report['all_replies'])}")


if __name__ == "__main__":
    main()
