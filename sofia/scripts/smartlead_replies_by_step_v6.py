#!/usr/bin/env python3
"""
SmartLead — Replies by Sequence Step v6
========================================
Single pass: paginate inbox replies, read current_sequence_number directly.
No per-campaign requests needed.

Excludes: OOO (category), DNC (category), Russian campaigns (name filter)
"""

import os, json, time
from collections import defaultdict
from datetime import datetime, timezone
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY  = os.environ.get("SMARTLEAD_API_KEY", "")

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


def load_categories():
    data = api_get("/leads/fetch-categories") or []
    cat_map = {c["id"]: c for c in data}
    ooo_ids = {i for i, c in cat_map.items() if "out of office" in c.get("name", "").lower()}
    dnc_ids = {i for i, c in cat_map.items() if "do not contact" in c.get("name", "").lower()}
    print(f"  Categories: {len(cat_map)} | OOO ids: {ooo_ids} | DNC ids: {dnc_ids}")
    return ooo_ids, dnc_ids


def main():
    if not API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set"); return

    print("=" * 70)
    print("  SmartLead — Replies by Sequence Step v6")
    print("  Exclude: OOO, DNC, Russian campaigns")
    print("=" * 70)

    print("\nStep 1: Load categories")
    ooo_ids, dnc_ids = load_categories()

    print("\nStep 2: Paginate inbox & count by sequence step")

    step_replies   = defaultdict(int)   # step_num → count
    step_campaigns = defaultdict(set)   # step_num → set of campaign names
    total = ooo = dnc = excl_camp = no_step = 0
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

            cname = r.get("email_campaign_name") or r.get("campaign_name") or ""
            if any(kw in cname.lower() for kw in EXCLUDE_CAMP):
                excl_camp += 1
                continue

            step = r.get("current_sequence_number")
            if step is None:
                no_step += 1
                continue

            step_replies[step] += 1
            step_campaigns[step].add(cname)

        real = sum(step_replies.values())
        print(f"\r  {total} fetched | {real} mapped | {ooo} OOO | {dnc} DNC | {excl_camp} Russian | {no_step} no-step",
              end="", flush=True)

        if len(rows) < 20:
            break
        offset += 20
        time.sleep(0.3)

    print()
    total_real = sum(step_replies.values())
    print(f"\n  Done. Total inbox: {total} | Real replies mapped: {total_real}")

    # ── Report ─────────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("  TOP SEQUENCE STEPS BY REPLIES")
    print("=" * 70)
    print(f"\n  {'Step':<12} {'Replies':>8} {'%':>8}  Bar")
    print("  " + "-" * 55)

    sorted_steps = sorted(step_replies.items(), key=lambda x: -x[1])
    for step, count in sorted_steps:
        pct = count / total_real * 100 if total_real else 0
        bar = "#" * int(pct / 2)
        print(f"  Step {str(step):<7} {count:>8} {pct:>7.1f}%  {bar}")

    print(f"\n  Total: {total_real} real replies across {len(step_replies)} steps")
    print(f"  Excluded: {ooo} OOO + {dnc} DNC + {excl_camp} Russian + {no_step} no-step")

    # ── Save ──────────────────────────────────────────────────────────────────
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_inbox": total,
        "total_mapped": total_real,
        "excluded_ooo": ooo,
        "excluded_dnc": dnc,
        "excluded_russian": excl_camp,
        "excluded_no_step": no_step,
        "top_steps": [
            {
                "step": s,
                "replies": c,
                "pct": round(c / total_real * 100, 1) if total_real else 0,
                "campaigns": len(step_campaigns[s]),
            }
            for s, c in sorted_steps
        ],
    }
    out = "sofia/reports/smartlead_replies_by_step_v6.json"
    os.makedirs("sofia/reports", exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
