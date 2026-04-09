#!/usr/bin/env python3
"""
SmartLead — ALL Replies by Sequence Step v3 (Async + Smart)
============================================================
Strategy:
  1. Fetch all campaigns
  2. Async batch: get sequence-analytics for all (aggregate reply_count per step)
  3. Only for top campaigns (>0 replies): fetch detailed stats for OOO/DNC filtering
  4. Combine: step-level analytics + filtered individual replies

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_all_replies_by_step_v3.py"
"""

import os
import json
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Rate limit: max N concurrent requests, with delay between batches
MAX_CONCURRENT = 3
BATCH_DELAY = 1.5  # seconds between batches

EXCLUDE_CATS_LOWER = {
    "out of office", "ooo",
    "do not contact", "dnc",
}

OOO_SUBJECT_PATTERNS = [
    "out of office", "out of the office", "automatic reply",
    "auto-reply", "autoreply", "i am currently out",
    "on vacation", "on leave", "away from", "abwesenheit",
    "absence", "je suis absent", "fuera de la oficina",
    "currently unavailable",
]


async def api_get_async(client, path, params=None):
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(4):
        try:
            resp = await client.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            await asyncio.sleep(3)
    return None


def api_get_sync(path, params=None):
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(4):
        try:
            resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            time.sleep(3)
    return None


async def fetch_seq_analytics(client, sem, campaign):
    """Fetch sequence-analytics for one campaign."""
    cid = campaign["id"]
    async with sem:
        data = await api_get_async(client, f"/campaigns/{cid}/sequence-analytics", {
            "start_date": "2020-01-01 00:00:00",
            "end_date": datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59"),
        })
        await asyncio.sleep(0.3)  # courtesy delay
        return cid, data


async def pass1_scan(campaigns):
    """Pass 1: Get sequence-analytics for all campaigns asynchronously."""
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = {}

    async with httpx.AsyncClient() as client:
        # Process in batches
        batch_size = 20
        for i in range(0, len(campaigns), batch_size):
            batch = campaigns[i:i+batch_size]
            tasks = [fetch_seq_analytics(client, sem, c) for c in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    continue
                cid, data = result
                if data:
                    results[cid] = data

            done = min(i + batch_size, len(campaigns))
            print(f"  Pass 1: {done}/{len(campaigns)} scanned...", flush=True)
            await asyncio.sleep(BATCH_DELAY)

    return results


def get_sequences_sync(campaign_id):
    data = api_get_sync(f"/campaigns/{campaign_id}/sequences")
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


def get_all_statistics_sync(campaign_id):
    all_records = []
    offset = 0
    limit = 500
    while True:
        data = api_get_sync(f"/campaigns/{campaign_id}/statistics", {"offset": offset, "limit": limit})
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


def is_auto_reply(subject):
    if not subject:
        return False
    s = subject.lower()
    return any(p in s for p in OOO_SUBJECT_PATTERNS)


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    print("=" * 80)
    print("  SMARTLEAD — ALL REPLIES BY SEQUENCE STEP v3 (Async)")
    print("  Excluding: OOO, Do Not Contact, Auto-Replies")
    print("=" * 80)
    print()

    # 1. Get all campaigns
    all_campaigns = api_get_sync("/campaigns")
    if isinstance(all_campaigns, dict):
        all_campaigns = all_campaigns.get("data", all_campaigns.get("campaigns", []))

    # Filter: skip DRAFTED
    active = [c for c in all_campaigns if c.get("status", "").upper() != "DRAFTED"]
    print(f"Total: {len(all_campaigns)}, Processing: {len(active)}\n")

    # 2. PASS 1: Async sequence-analytics scan
    print("--- PASS 1: Async sequence-analytics scan ---\n")
    seq_analytics = asyncio.run(pass1_scan(active))

    # Find campaigns with replies
    campaigns_with_replies = []
    agg_step_replies = defaultdict(int)  # step_num (from seq) -> total replies
    agg_step_sent = defaultdict(int)

    camp_lookup = {c["id"]: c for c in active}

    for cid, data in seq_analytics.items():
        if not isinstance(data, list):
            continue
        total_replies = 0
        for step in data:
            rc = int(step.get("reply_count", 0))
            sc = int(step.get("sent_count", 0))
            seq_id = step.get("email_campaign_seq_id")
            seq_num = step.get("seq_number")  # may not be in response
            total_replies += rc

            # Use seq_id as step identifier for now
            if rc > 0:
                agg_step_replies[seq_id] = agg_step_replies.get(seq_id, 0) + rc
                agg_step_sent[seq_id] = agg_step_sent.get(seq_id, 0) + sc

        if total_replies > 0:
            camp = camp_lookup.get(cid, {})
            campaigns_with_replies.append({
                "id": cid,
                "name": camp.get("name", f"#{cid}"),
                "status": camp.get("status", "?"),
                "raw_replies": total_replies,
                "steps": data,
            })

    print(f"\n  {len(campaigns_with_replies)} campaigns have replies\n")

    # 3. PASS 2: Detailed stats for campaigns with replies (sync, one by one)
    print("--- PASS 2: Fetch detailed reply records ---\n")

    # Sort by reply count desc, process top ones first
    campaigns_with_replies.sort(key=lambda x: -x["raw_replies"])

    global_step_replies = defaultdict(int)       # step_num -> count
    global_step_details = defaultdict(list)      # step_num -> records
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

        step_map = get_sequences_sync(cid)
        time.sleep(0.3)

        records = get_all_statistics_sync(cid)
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
            cat_lower = category.lower()

            if cat_lower in ("out of office", "ooo"):
                camp_ooo += 1
                continue
            if cat_lower in ("do not contact", "dnc"):
                camp_dnc += 1
                continue
            if is_auto_reply(subject):
                camp_auto += 1
                continue

            step_num = match_step(subject, step_map)

            reply_rec = {
                "campaign_id": cid,
                "campaign": cname,
                "email": r.get("lead_email", ""),
                "name": r.get("lead_name", ""),
                "subject": subject,
                "step_num": step_num,
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

        print(f"{len(records)} sent, {len(replied)} repl, {len(camp_replies)} real "
              f"(-{camp_ooo} OOO -{camp_dnc} DNC -{camp_auto} auto)")

        if camp_replies:
            by_step = defaultdict(int)
            for r in camp_replies:
                by_step[r["step_num"]] += 1
            campaign_results.append({
                "name": cname, "id": cid,
                "status": camp_info["status"],
                "total_sent": len(records),
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
        bar = "#" * int(pct / 2)
        print(f"  {label:<20} {count:>8} {pct:>11.1f}%  {bar}")

    # STEP DETAILS
    print("\n")
    print("=" * 80)
    print("  REPLY SUBJECTS PER STEP (top 10 subjects)")
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
        pct = count / total_real_replies * 100 if total_real_replies else 0
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
