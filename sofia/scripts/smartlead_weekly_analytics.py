#!/usr/bin/env python3
"""
SmartLead — Weekly Analytics Report
=====================================
Pulls all campaigns, fetches statistics for the last 7 days.
Shows: sent, opened, replied, bounced, unsubscribed + conversion rates.

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_weekly_analytics.py"
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Last 7 days window
NOW = datetime.now(timezone.utc)
WEEK_AGO = NOW - timedelta(days=7)


def api_get(path, params=None):
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")
    q = params or {}
    q["api_key"] = API_KEY
    resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    if resp.status_code == 429:
        print("  Rate limited, waiting 5s...")
        time.sleep(5)
        resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_all_campaigns():
    """Fetch all campaigns."""
    data = api_get("/campaigns")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data", data.get("campaigns", []))
    return []


def get_all_statistics(campaign_id):
    """Fetch ALL statistics records with pagination."""
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
        if len(records) < limit:
            break
        offset += limit
        time.sleep(0.3)  # rate limit courtesy

    return all_records


def parse_time(time_str):
    """Parse SmartLead timestamp to datetime."""
    if not time_str:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def analyze_campaign(campaign_id, campaign_name):
    """Analyze one campaign's weekly stats."""
    stats = get_all_statistics(campaign_id)

    metrics = {
        "sent": 0,
        "opened": 0,
        "clicked": 0,
        "replied": 0,
        "bounced": 0,
        "unsubscribed": 0,
    }
    replied_leads = []

    for rec in stats:
        sent_time = parse_time(rec.get("sent_time"))

        # Filter: only records sent in the last 7 days
        # But also count replies that came this week regardless of sent time
        reply_time = parse_time(rec.get("reply_time"))
        open_time = parse_time(rec.get("open_time"))

        in_send_window = sent_time and sent_time >= WEEK_AGO
        in_reply_window = reply_time and reply_time >= WEEK_AGO

        if in_send_window:
            metrics["sent"] += 1

            if open_time:
                metrics["opened"] += 1

            if rec.get("click_time"):
                metrics["clicked"] += 1

            if rec.get("is_bounced"):
                metrics["bounced"] += 1

            if rec.get("is_unsubscribed"):
                metrics["unsubscribed"] += 1

        # Replies this week (even if email was sent earlier)
        if in_reply_window:
            metrics["replied"] += 1
            replied_leads.append({
                "email": rec.get("lead_email", ""),
                "name": rec.get("lead_name", ""),
                "subject": rec.get("email_subject", ""),
                "reply_time": str(reply_time),
                "category": rec.get("lead_category", ""),
                "lead_id": rec.get("lead_id"),
                "stats_id": rec.get("stats_id"),
            })

    return metrics, replied_leads


def pct(part, total):
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def main():
    print("=" * 70)
    print(f"  SMARTLEAD WEEKLY ANALYTICS — {WEEK_AGO.strftime('%b %d')} to {NOW.strftime('%b %d, %Y')}")
    print("=" * 70)
    print()

    all_campaigns = get_all_campaigns()
    # Only OnSocial campaigns
    campaigns = [c for c in all_campaigns if "OnSocial" in c.get("name", "") or "onsocial" in c.get("name", "").lower()]
    print(f"Found {len(all_campaigns)} campaigns total, {len(campaigns)} OnSocial campaigns\n")

    totals = defaultdict(int)
    all_replied = []
    campaign_results = []

    for camp in campaigns:
        cid = camp.get("id")
        cname = camp.get("name", f"#{cid}")
        status = camp.get("status", "unknown")

        print(f"  Fetching: {cname} [{status}]...", end=" ", flush=True)

        try:
            metrics, replied = analyze_campaign(cid, cname)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Skip campaigns with zero activity this week
        if metrics["sent"] == 0 and metrics["replied"] == 0:
            print("no activity")
            continue

        print(f"sent={metrics['sent']}, replied={metrics['replied']}")

        campaign_results.append({
            "name": cname,
            "id": cid,
            "status": status,
            "metrics": metrics,
            "replied_leads": replied,
        })

        for k, v in metrics.items():
            totals[k] += v
        all_replied.extend(replied)

        time.sleep(0.3)

    # Sort by sent desc
    campaign_results.sort(key=lambda x: x["metrics"]["sent"], reverse=True)

    # Print results table
    print()
    print("=" * 70)
    print(f"{'Campaign':<45} {'Sent':>6} {'Open':>6} {'Reply':>6} {'R%':>6} {'Bnce':>5}")
    print("-" * 70)

    for cr in campaign_results:
        m = cr["metrics"]
        name = cr["name"][:44]
        status_marker = " [STOPPED]" if cr["status"] in ("STOPPED", "PAUSED") else ""
        print(
            f"{name + status_marker:<45} "
            f"{m['sent']:>6} "
            f"{m['opened']:>6} "
            f"{m['replied']:>6} "
            f"{pct(m['replied'], m['sent']):>6} "
            f"{m['bounced']:>5}"
        )

    # Totals
    print("-" * 70)
    print(
        f"{'TOTAL':<45} "
        f"{totals['sent']:>6} "
        f"{totals['opened']:>6} "
        f"{totals['replied']:>6} "
        f"{pct(totals['replied'], totals['sent']):>6} "
        f"{totals['bounced']:>5}"
    )
    print()

    # Summary
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Sent:         {totals['sent']}")
    print(f"  Opened:       {totals['opened']}  ({pct(totals['opened'], totals['sent'])})")
    print(f"  Clicked:      {totals['clicked']}  ({pct(totals['clicked'], totals['sent'])})")
    print(f"  Replied:      {totals['replied']}  ({pct(totals['replied'], totals['sent'])})")
    print(f"  Bounced:      {totals['bounced']}  ({pct(totals['bounced'], totals['sent'])})")
    print(f"  Unsubscribed: {totals['unsubscribed']}  ({pct(totals['unsubscribed'], totals['sent'])})")
    print()

    # Reply details
    if all_replied:
        print("=" * 70)
        print(f"  REPLIES THIS WEEK ({len(all_replied)} total)")
        print("=" * 70)
        for r in sorted(all_replied, key=lambda x: x["reply_time"], reverse=True):
            cat = r["category"] or "?"
            print(f"  [{cat:>12}]  {r['name']:<30} {r['email']}")
            print(f"               Subject: {r['subject']}")
            print()

    # Save JSON report
    report = {
        "period": f"{WEEK_AGO.isoformat()} to {NOW.isoformat()}",
        "generated": NOW.isoformat(),
        "totals": dict(totals),
        "campaigns": campaign_results,
    }
    out_path = f"sofia/reports/smartlead_weekly_{NOW.strftime('%Y-%m-%d')}.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Report saved: {out_path}")


if __name__ == "__main__":
    main()
