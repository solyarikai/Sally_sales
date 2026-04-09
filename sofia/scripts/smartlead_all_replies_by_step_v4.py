#!/usr/bin/env python3
"""
SmartLead — ALL Replies by Sequence Step v4 (Reply-First Approach)
===================================================================
Strategy (fast):
  1. Fetch lead categories (1 request)
  2. Paginate master-inbox/inbox-replies to get ALL replied leads (limit 20/page)
  3. Collect unique campaign_ids from replies
  4. Only for those campaigns: fetch sequences + full statistics
  5. Map replies to steps, filter OOO/DNC

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_all_replies_by_step_v4.py"
"""

import os
import json
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

OOO_SUBJECT_PATTERNS = [
    "out of office", "out of the office", "automatic reply",
    "auto-reply", "autoreply", "i am currently out",
    "on vacation", "on leave", "away from", "abwesenheit",
    "absence", "je suis absent", "fuera de la oficina",
    "currently unavailable",
]


def api_get(path, params=None):
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(4):
        try:
            resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f" [429→{wait}s]", end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3)
    return None


def api_post(path, body=None, query=None):
    q = query or {}
    q["api_key"] = API_KEY
    for attempt in range(4):
        try:
            resp = httpx.post(f"{BASE_URL}{path}", params=q, json=body or {}, timeout=30)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f" [429→{wait}s]", end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3)
    return None


def fetch_all_inbox_replies():
    """Paginate through ALL master inbox replies."""
    all_replies = []
    offset = 0
    limit = 20  # SmartLead max is 20

    while True:
        body = {"offset": offset, "limit": limit}
        data = api_post("/master-inbox/inbox-replies", body)

        if not data:
            break

        replies = data if isinstance(data, list) else data.get("data", [])
        if not replies:
            break

        all_replies.extend(replies)
        print(f"  Inbox replies fetched: {len(all_replies)}...", flush=True)

        if len(replies) < limit:
            break

        offset += limit
        time.sleep(0.5)

    return all_replies


def fetch_categories():
    """Fetch category ID → name mapping."""
    data = api_get("/leads/fetch-categories")
    if not data or not isinstance(data, list):
        return {}
    return {c["id"]: c for c in data}


def get_sequences(campaign_id):
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
        time.sleep(0.5)
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


def is_auto_reply_subject(subject):
    if not subject:
        return False
    s = subject.lower()
    return any(p in s for p in OOO_SUBJECT_PATTERNS)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("=" * 80)
    print("  SMARTLEAD — ALL REPLIES BY SEQUENCE STEP v4 (Reply-First)")
    print("  Excluding: OOO, Do Not Contact, Auto-Replies")
    print("=" * 80)
    print()

    # Step 1: Fetch categories
    print("Step 1: Fetching lead categories...")
    cat_map = fetch_categories()
    print(f"  {len(cat_map)} categories loaded")

    # Build exclude set by category ID
    exclude_cat_ids = set()
    ooo_cat_ids = set()
    dnc_cat_ids = set()
    for cid, cat in cat_map.items():
        name_lower = cat.get("name", "").lower()
        if "out of office" in name_lower or name_lower == "ooo":
            exclude_cat_ids.add(cid)
            ooo_cat_ids.add(cid)
        elif "do not contact" in name_lower or name_lower == "dnc":
            exclude_cat_ids.add(cid)
            dnc_cat_ids.add(cid)

    print(f"  OOO category IDs: {ooo_cat_ids}")
    print(f"  DNC category IDs: {dnc_cat_ids}")

    # Step 2: Fetch all inbox replies
    print("\nStep 2: Fetching all inbox replies...")
    inbox_replies = fetch_all_inbox_replies()
    print(f"  Total inbox replies: {len(inbox_replies)}")

    # Campaigns to EXCLUDE by name keywords (case-insensitive)
    EXCLUDE_CAMPAIGN_KEYWORDS = ["russian", " russ ", " rus ", "(rus)", "(russ)", "_rus_", "_russ_", "рус", "ру "]

    def is_excluded_campaign(name):
        n = (name or "").lower()
        return any(kw in n for kw in EXCLUDE_CAMPAIGN_KEYWORDS)

    # Group by campaign, filter categories
    campaigns_from_inbox = defaultdict(list)
    total_ooo = 0
    total_dnc = 0
    total_excluded_camp = 0

    for r in inbox_replies:
        cat_id = r.get("lead_category_id")
        if cat_id in ooo_cat_ids:
            total_ooo += 1
            continue
        if cat_id in dnc_cat_ids:
            total_dnc += 1
            continue

        campaign_id = r.get("campaign_id") or r.get("email_campaign_id")
        campaign_name = r.get("email_campaign_name", r.get("campaign_name", f"#{campaign_id}"))

        # Skip excluded campaigns
        if is_excluded_campaign(campaign_name):
            total_excluded_camp += 1
            continue

        campaigns_from_inbox[campaign_id].append({
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "email": r.get("lead_email", r.get("lead", {}).get("email", "")),
            "first_name": r.get("lead_first_name", r.get("lead", {}).get("first_name", "")),
            "last_name": r.get("lead_last_name", r.get("lead", {}).get("last_name", "")),
            "category_id": cat_id,
            "category_name": cat_map.get(cat_id, {}).get("name", "Unknown") if cat_id else "Uncategorized",
            "reply_time": r.get("last_reply_time", r.get("reply_time", "")),
        })

    real_reply_count = sum(len(v) for v in campaigns_from_inbox.values())
    print(f"\n  After filtering: {real_reply_count} real replies across {len(campaigns_from_inbox)} campaigns")
    print(f"  Excluded: {total_ooo} OOO, {total_dnc} DNC, {total_excluded_camp} wrong project (Inxy/Russian)")

    # Step 3: For each campaign with replies, get sequences + statistics to map steps
    print(f"\nStep 3: Fetching sequences + statistics for {len(campaigns_from_inbox)} campaigns...")

    global_step_replies = defaultdict(int)
    global_step_details = defaultdict(list)
    total_auto_filtered = 0
    total_sent = 0
    campaign_results = []

    for ci, (camp_id, inbox_leads) in enumerate(sorted(campaigns_from_inbox.items(), key=lambda x: -len(x[1]))):
        camp_name = inbox_leads[0]["campaign_name"] if inbox_leads else f"#{camp_id}"
        print(f"  [{ci+1}/{len(campaigns_from_inbox)}] {camp_name[:55]}...", end=" ", flush=True)

        # Get sequence step map
        step_map = get_sequences(camp_id)
        time.sleep(0.3)

        # Get detailed statistics (to get email_subject for step mapping)
        records = get_all_statistics(camp_id)
        time.sleep(0.3)

        if not records:
            print(f"{len(inbox_leads)} inbox replies, no stats")
            continue

        total_sent += len(records)

        # Build email -> record lookup
        email_stats = {}
        for rec in records:
            if rec.get("reply_time"):
                email = rec.get("lead_email", "")
                email_stats[email] = rec

        camp_step_counts = defaultdict(int)
        camp_auto = 0
        camp_replies = []

        for lead in inbox_leads:
            email = lead["email"]
            stat = email_stats.get(email)

            if stat:
                subject = stat.get("email_subject", "")
                category = stat.get("lead_category") or ""

                # Double-check category from stats
                cat_lower = category.lower()
                if cat_lower in ("out of office", "ooo"):
                    continue
                if cat_lower in ("do not contact", "dnc"):
                    continue

                if is_auto_reply_subject(subject):
                    camp_auto += 1
                    total_auto_filtered += 1
                    continue

                step_num = match_step(subject, step_map)
            else:
                # No stats record found - use inbox data
                subject = ""
                step_num = None

            reply_rec = {
                "campaign_id": camp_id,
                "campaign": camp_name,
                "email": email,
                "name": f"{lead['first_name']} {lead['last_name']}".strip(),
                "subject": subject,
                "step_num": step_num,
                "sent_time": stat.get("sent_time", "") if stat else "",
                "reply_time": lead["reply_time"],
                "category": lead["category_name"],
            }

            camp_replies.append(reply_rec)
            global_step_replies[step_num] += 1
            global_step_details[step_num].append(reply_rec)
            camp_step_counts[step_num] += 1

        print(f"{len(records)} sent, {len(camp_replies)} real, {camp_auto} auto-filtered")

        if camp_replies:
            campaign_results.append({
                "name": camp_name,
                "id": camp_id,
                "total_sent": len(records),
                "real_replies": len(camp_replies),
                "auto_filtered": camp_auto,
                "by_step": {str(k): v for k, v in camp_step_counts.items()},
            })

    # === FINAL REPORT ===
    total_real = sum(len(v) for v in global_step_details.values())

    print("\n\n")
    print("=" * 80)
    print("  GLOBAL RESULTS")
    print("=" * 80)
    print(f"\n  Total inbox replies scanned:  {len(inbox_replies)}")
    print(f"  Excluded OOO:                 {total_ooo}")
    print(f"  Excluded Do Not Contact:      {total_dnc}")
    print(f"  Excluded Auto-Replies:        {total_auto_filtered}")
    print(f"  Real replies analyzed:        {total_real}")
    print(f"  Unique campaigns:             {len(campaigns_from_inbox)}")
    print(f"  Total emails sent:            {total_sent}")
    if total_sent:
        print(f"  Real Reply Rate:              {total_real/total_sent*100:.2f}%")

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
        pct = count / total_real * 100 if total_real else 0
        bar = "#" * int(pct / 2)
        print(f"  {label:<20} {count:>8} {pct:>11.1f}%  {bar}")

    # STEP DETAILS
    print("\n")
    print("=" * 80)
    print("  REPLY SUBJECTS PER STEP (top 10)")
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
        pct = count / total_real * 100 if total_real else 0
        print(f"  {cat:<35} {count:>8} {pct:>7.1f}%")

    # TOP CAMPAIGNS
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
        print(f"  {cs['name'][:54]:<55} {cs['total_sent']:>6} {cs['real_replies']:>6} {rate:>5.1f}%  {top_label}")

    # SAVE JSON
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_inbox_replies": len(inbox_replies),
            "excluded_ooo": total_ooo,
            "excluded_dnc": total_dnc,
            "excluded_auto": total_auto_filtered,
            "real_replies": total_real,
            "unique_campaigns": len(campaigns_from_inbox),
            "total_emails_sent": total_sent,
            "real_reply_rate_pct": round(total_real / total_sent * 100, 2) if total_sent else 0,
        },
        "top_steps": [
            {
                "step": step_num,
                "label": f"Step {step_num}" if step_num is not None else "Unknown",
                "replies": count,
                "pct": round(count / total_real * 100, 1) if total_real else 0,
            }
            for step_num, count in sorted_steps
        ],
        "category_breakdown": dict(cat_counts),
        "campaigns": campaign_results,
        "all_replies": [r for replies in global_step_details.values() for r in replies],
    }

    out_path = "sofia/reports/smartlead_all_replies_by_step.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n\nReport saved: {out_path}")
    print(f"Total real replies in JSON: {len(report['all_replies'])}")


if __name__ == "__main__":
    main()
