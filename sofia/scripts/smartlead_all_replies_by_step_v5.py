#!/usr/bin/env python3
"""
SmartLead — Replies by Sequence Step v5 (Fast)
================================================
1. Fetch all inbox replies → filter OOO/DNC/Russian → get campaign_ids
2. For each campaign: sequence-analytics (1 request) → reply_count per step
3. Output: top steps across all projects

Fast: ~2 requests per campaign, no statistics pagination.
"""

import os, json, time
from collections import defaultdict
from datetime import datetime, timezone
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY  = os.environ.get("SMARTLEAD_API_KEY", "")

EXCLUDE_CAMP = ["russian"]  # keyword filter on campaign name (lowercase)

OOO_SUBJ = [
    "out of office", "automatic reply", "auto-reply", "autoreply",
    "on vacation", "on leave", "away from", "currently unavailable",
]


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


def api_post(path, body=None):
    q = {"api_key": API_KEY}
    for attempt in range(5):
        try:
            r = httpx.post(f"{BASE_URL}{path}", params=q, json=body or {}, timeout=30)
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


# ── Step 1: Categories ────────────────────────────────────────────────────────

def load_categories():
    data = api_get("/leads/fetch-categories") or []
    cat_map = {c["id"]: c for c in data}
    ooo_ids = {i for i, c in cat_map.items() if "out of office" in c.get("name","").lower()}
    dnc_ids = {i for i, c in cat_map.items() if "do not contact" in c.get("name","").lower()}
    print(f"  Categories: {len(cat_map)} | OOO ids: {ooo_ids} | DNC ids: {dnc_ids}")
    return cat_map, ooo_ids, dnc_ids


# ── Step 2: Inbox replies ─────────────────────────────────────────────────────

def fetch_inbox_replies(ooo_ids, dnc_ids):
    """Paginate master inbox, return {campaign_id: count} after filtering."""
    camp_counts = defaultdict(int)
    camp_names  = {}
    total = ooo = dnc = excluded_camp = 0
    offset = 0

    while True:
        data = api_post("/master-inbox/inbox-replies", {"offset": offset, "limit": 20})
        if not data:
            break
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            break

        total += len(rows)

        for r in rows:
            cat_id = r.get("lead_category_id")

            if cat_id in ooo_ids:
                ooo += 1
                continue
            if cat_id in dnc_ids:
                dnc += 1
                continue

            cid   = r.get("campaign_id") or r.get("email_campaign_id")
            cname = r.get("email_campaign_name") or r.get("campaign_name") or f"#{cid}"

            if any(kw in (cname or "").lower() for kw in EXCLUDE_CAMP):
                excluded_camp += 1
                continue

            camp_counts[cid] += 1
            camp_names[cid]   = cname

        print(f"\r  Inbox: {total} fetched | {sum(camp_counts.values())} real replies...", end="", flush=True)

        if len(rows) < 20:
            break
        offset += 20
        time.sleep(0.4)

    print()
    print(f"  Total in inbox: {total} | OOO: {ooo} | DNC: {dnc} | Excluded camp: {excluded_camp}")
    print(f"  Real replies: {sum(camp_counts.values())} across {len(camp_counts)} campaigns")
    return camp_counts, camp_names


# ── Step 3: Sequence analytics per campaign ───────────────────────────────────

def get_seq_analytics(cid):
    """1 request: reply_count per sequence step."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d 23:59:59")
    data = api_get(f"/campaigns/{cid}/sequence-analytics", {
        "start_date": "2020-01-01 00:00:00",
        "end_date":   now,
    })
    time.sleep(0.3)
    return data if isinstance(data, list) else []


def get_sequences(cid):
    """Map seq_id / seq_number → step label."""
    data = api_get(f"/campaigns/{cid}/sequences")
    time.sleep(0.3)
    seq_num_map = {}   # seq_id → seq_number
    if isinstance(data, list):
        for s in data:
            num  = s.get("seq_number")
            sid  = s.get("id") or s.get("seq_id")
            if sid and num is not None:
                seq_num_map[sid] = num
    return seq_num_map


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set"); return

    print("=" * 70)
    print("  SmartLead — Replies by Sequence Step v5 (Fast)")
    print("  Exclude: OOO, DNC, Russian campaigns")
    print("=" * 70)

    # 1. Categories
    print("\nStep 1: Load categories")
    cat_map, ooo_ids, dnc_ids = load_categories()

    # 2. Inbox replies
    print("\nStep 2: Paginate inbox replies")
    camp_counts, camp_names = fetch_inbox_replies(ooo_ids, dnc_ids)

    if not camp_counts:
        print("No replies found."); return

    # 3. Sequence analytics
    print(f"\nStep 3: Sequence analytics for {len(camp_counts)} campaigns")

    step_replies  = defaultdict(int)   # step_num → total replies
    step_campaigns = defaultdict(set)  # step_num → set of campaign names
    camp_results  = []

    for i, (cid, reply_count) in enumerate(sorted(camp_counts.items(), key=lambda x: -x[1])):
        cname = camp_names.get(cid, f"#{cid}")
        print(f"  [{i+1}/{len(camp_counts)}] {cname[:55]}...", end=" ", flush=True)

        seq_num_map  = get_sequences(cid)
        analytics    = get_seq_analytics(cid)

        if not analytics:
            print(f"{reply_count} replies, no analytics")
            continue

        # analytics: list of {email_campaign_seq_id, sent_count, reply_count, ...}
        camp_by_step = {}
        for row in analytics:
            rc  = int(row.get("reply_count") or 0)
            if rc == 0:
                continue
            sid = row.get("email_campaign_seq_id")
            num = seq_num_map.get(sid) or row.get("seq_number")
            if num is None:
                num = "?"
            camp_by_step[num] = camp_by_step.get(num, 0) + rc
            step_replies[num] += rc
            step_campaigns[num].add(cname)

        total_from_analytics = sum(camp_by_step.values())
        print(f"{reply_count} inbox replies | analytics: {total_from_analytics} | steps: {dict(camp_by_step)}")

        camp_results.append({
            "name":         cname,
            "id":           cid,
            "inbox_replies": reply_count,
            "by_step":      {str(k): v for k, v in camp_by_step.items()},
        })

    # ── Report ────────────────────────────────────────────────────────────────
    total_real = sum(step_replies.values())

    print("\n\n" + "=" * 70)
    print("  TOP SEQUENCE STEPS BY REPLIES")
    print("=" * 70)
    print(f"\n  {'Step':<12} {'Replies':>8} {'%':>8}  Bar")
    print("  " + "-" * 50)

    sorted_steps = sorted(step_replies.items(), key=lambda x: -x[1])
    for step, count in sorted_steps:
        pct = count / total_real * 100 if total_real else 0
        bar = "#" * int(pct / 2)
        print(f"  Step {str(step):<7} {count:>8} {pct:>7.1f}%  {bar}")

    print(f"\n  Total replies mapped: {total_real}")

    print("\n\n" + "=" * 70)
    print("  TOP 20 CAMPAIGNS")
    print("=" * 70)
    print(f"\n  {'Campaign':<50} {'Inbox':>6}  Top Step")
    print("  " + "-" * 65)
    for cs in sorted(camp_results, key=lambda x: -x["inbox_replies"])[:20]:
        bs = cs["by_step"]
        top = max(bs.items(), key=lambda x: x[1]) if bs else ("?", 0)
        print(f"  {cs['name'][:49]:<50} {cs['inbox_replies']:>6}  Step {top[0]}({top[1]})")

    # Save
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_inbox_replies_after_filter": sum(camp_counts.values()),
        "total_mapped_replies": total_real,
        "top_steps": [
            {"step": s, "replies": c, "pct": round(c/total_real*100, 1) if total_real else 0}
            for s, c in sorted_steps
        ],
        "campaigns": camp_results,
    }
    out = "sofia/reports/smartlead_replies_by_step_v5.json"
    os.makedirs("sofia/reports", exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
