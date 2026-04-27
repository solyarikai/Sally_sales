#!/usr/bin/env python3
"""
Test the hypothesis: some OnSocial mailboxes (bhaskar pool) underperform on
Microsoft / Outlook recipients vs Gmail recipients.

For 10 active OnSocial campaigns, this script:
  1. Pulls all leads (paged).
  2. Resolves MX for each unique recipient domain -> labels esp = outlook|gmail|other.
  3. Pulls message-history per lead -> events (SENT/REPLY) tagged with email_account_id,
     open_count, click_count.
  4. Aggregates per-mailbox metrics, sliced by recipient ESP:
        sent / opened / replied / open_rate / reply_rate.
  5. Writes a TSV report and prints a console summary.

Run on Hetzner (where SMARTLEAD_API_KEY lives).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any

import aiohttp
import dns.asyncresolver
import dns.resolver

API = "https://server.smartlead.ai/api/v1"
KEY = os.environ.get("SMARTLEAD_API_KEY")
if not KEY:
    sys.exit("SMARTLEAD_API_KEY not set")

ONSOCIAL_CAMPAIGNS = [
    3188673,
    3188672,
    3188671,
    3188670,
    3188669,
    3169118,
    3169092,
    3124575,
    3096747,
    3096746,
]

# 17 bhaskar mailboxes — pool used by all 10 OnSocial campaigns.
# Map: from_email -> id (we match events by `from` field since the API's
# message-history payload doesn't expose email_account_id).
BHASKAR_POOL = {
    "bhaskar.v@onsocial-analytics.com": 17459681,
    "bhaskar@onsocial-platform.com": 17459602,
    "bhaskar@onsocial-network.com": 17459561,
    "bhaskar@onsocial-metrics.com": 17459504,
    "bhaskar@onsocial-insights.com": 17459362,
    "bhaskar@onsocial-influence.com": 17459316,
    "bhaskar@onsocial-data.com": 17459284,
    "bhaskar@onsocial-analytics.com": 17459241,
    "bhaskar.v@onsocial-platform.com": 17459195,
    "bhaskar.v@onsocial-network.com": 17459132,
    "bhaskar.v@onsocial-metrics.com": 17459098,
    "bhaskar.v@onsocial-insights.com": 17459065,
    "bhaskar.v@onsocial-influence.com": 17459006,
    "bhaskar.v@onsocial-data.com": 17458886,
    "bhaskar@onsocialmetrics.com": 15090446,
    "bhaskar.v@onsocialplatform.com": 15090416,
    "bhaskar.v@onsocialmetrics.com": 15090400,
}
BHASKAR_IDS = set(BHASKAR_POOL.values())

CONCURRENCY = 12
RETRY = 3
TIMEOUT = aiohttp.ClientTimeout(total=60)


# ──────────────────────────── HTTP ────────────────────────────────


async def get_json(
    session: aiohttp.ClientSession, url: str, params: dict | None = None
) -> Any:
    p = {"api_key": KEY}
    if params:
        p.update(params)
    last_err = None
    for attempt in range(RETRY):
        try:
            async with session.get(url, params=p, timeout=TIMEOUT) as r:
                if r.status == 429:
                    await asyncio.sleep(2**attempt)
                    continue
                r.raise_for_status()
                return await r.json()
        except Exception as e:  # noqa
            last_err = e
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last_err}")


# ─────────────────────────── leads ────────────────────────────────


async def fetch_campaign_leads(
    session: aiohttp.ClientSession, campaign_id: int
) -> list[dict]:
    out = []
    offset = 0
    while True:
        data = await get_json(
            session,
            f"{API}/campaigns/{campaign_id}/leads",
            {"offset": offset, "limit": 100},
        )
        # Response shape: {"data":[{"lead":{"id":...,"email":...},"status":...}, ...]} or list
        rows = data.get("data") if isinstance(data, dict) else data
        if not rows:
            break
        for row in rows:
            lead = row.get("lead", row)
            out.append(
                {
                    "campaign_id": campaign_id,
                    "lead_id": lead.get("id"),
                    "email": (lead.get("email") or "").lower(),
                    "status": row.get("status") or lead.get("status"),
                }
            )
        if len(rows) < 100:
            break
        offset += 100
    return out


# ─────────────────────── MX classification ────────────────────────

OUTLOOK_MARKERS = ("outlook.com", "protection.outlook.com", "office365", "exchangelabs")
GOOGLE_MARKERS = ("google.com", "googlemail.com", "aspmx", "psmtp.com")


async def resolve_esp(resolver: dns.asyncresolver.Resolver, domain: str) -> str:
    try:
        ans = await resolver.resolve(domain, "MX", lifetime=5)
        targets = [str(r.exchange).lower().rstrip(".") for r in ans]
        joined = " ".join(targets)
        if any(m in joined for m in OUTLOOK_MARKERS):
            return "outlook"
        if any(m in joined for m in GOOGLE_MARKERS):
            return "gmail"
        return "other"
    except Exception:
        return "unknown"


async def classify_domains(domains: list[str]) -> dict[str, str]:
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
    resolver.timeout = 5
    resolver.lifetime = 5
    sem = asyncio.Semaphore(40)

    out: dict[str, str] = {}

    async def worker(d: str):
        async with sem:
            out[d] = await resolve_esp(resolver, d)

    await asyncio.gather(*(worker(d) for d in domains))
    return out


# ─────────────────────── message history ──────────────────────────


async def fetch_message_history(
    session: aiohttp.ClientSession, campaign_id: int, lead_id: int
) -> list[dict]:
    data = await get_json(
        session,
        f"{API}/campaigns/{campaign_id}/leads/{lead_id}/message-history",
    )
    # Response shape: {"history":[{...}]} or list
    if isinstance(data, dict):
        return data.get("history") or data.get("data") or []
    return data or []


# ─────────────────────── pipeline ─────────────────────────────────


async def main(sample_per_campaign: int | None) -> None:
    started = time.time()
    print("[1/4] Fetch leads from 10 OnSocial campaigns...", flush=True)
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def with_sem(coro):
            async with sem:
                return await coro

        leads_per = await asyncio.gather(
            *(
                with_sem(fetch_campaign_leads(session, cid))
                for cid in ONSOCIAL_CAMPAIGNS
            )
        )

    leads: list[dict] = [
        l for sub in leads_per for l in sub if l.get("lead_id") and l.get("email")
    ]
    by_camp = defaultdict(list)
    for l in leads:
        by_camp[l["campaign_id"]].append(l)
    print(f"     -> {len(leads)} leads across {len(by_camp)} campaigns", flush=True)
    for cid in ONSOCIAL_CAMPAIGNS:
        print(f"        {cid}: {len(by_camp[cid])} leads")

    if sample_per_campaign:
        import random

        random.seed(42)
        sampled = []
        for cid, rows in by_camp.items():
            sampled.extend(random.sample(rows, min(sample_per_campaign, len(rows))))
        leads = sampled
        print(
            f"     -> sampled {len(leads)} leads ({sample_per_campaign}/campaign)",
            flush=True,
        )

    print("[2/4] MX classify recipient domains...", flush=True)
    domains = sorted({l["email"].split("@", 1)[-1] for l in leads if "@" in l["email"]})
    esp_by_domain = await classify_domains(domains)
    counts = defaultdict(int)
    for v in esp_by_domain.values():
        counts[v] += 1
    print(f"     -> {len(domains)} domains: {dict(counts)}", flush=True)

    print(f"[3/4] Pull message-history for {len(leads)} leads...", flush=True)
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch(l: dict):
            async with sem:
                try:
                    history = await fetch_message_history(
                        session, l["campaign_id"], l["lead_id"]
                    )
                except Exception as e:  # noqa
                    return l, []
                return l, history

        results = []
        done = 0
        for fut in asyncio.as_completed([fetch(l) for l in leads]):
            results.append(await fut)
            done += 1
            if done % 200 == 0:
                print(f"     {done}/{len(leads)}", flush=True)

    print("[4/4] Aggregate matrix...", flush=True)
    # cell key: (mailbox_id, recipient_esp) -> dict counts
    cell: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"sent": 0, "opened": 0, "replied": 0, "leads_bounced": 0}
    )
    bounce_status = {"BOUNCED", "BOUNCE", "INVALID"}
    reply_status = {"REPLIED"}

    for lead, history in results:
        domain = lead["email"].split("@", 1)[-1] if "@" in lead["email"] else ""
        esp = esp_by_domain.get(domain, "unknown")
        for evt in history:
            etype = (evt.get("type") or evt.get("email_seq_type") or "").upper()
            mailbox = (
                evt.get("email_account_id")
                or evt.get("mailbox_id")
                or evt.get("from_id")
            )
            if not mailbox:
                continue
            if mailbox not in BHASKAR_IDS:
                # We only care about bhaskar pool for this hypothesis test.
                # Petr sender events still tracked under "_other_pool" if you want.
                key = (mailbox, esp)
            else:
                key = (mailbox, esp)
            if etype == "SENT":
                cell[key]["sent"] += 1
                if (evt.get("open_count") or 0) > 0 or evt.get("opened_time"):
                    cell[key]["opened"] += 1
            elif etype == "REPLY" or etype == "REPLIED":
                cell[key]["replied"] += 1
        # lead-level bounce
        if (lead.get("status") or "").upper() in bounce_status:
            # attribute to last sender
            last_mb = next(
                (
                    e.get("email_account_id") or e.get("mailbox_id")
                    for e in reversed(history)
                    if (e.get("type") or "").upper() == "SENT"
                ),
                None,
            )
            if last_mb:
                cell[(last_mb, esp)]["leads_bounced"] += 1

    # Build mailbox label map
    mailbox_label = {mb: f"id:{mb}" for mb in BHASKAR_IDS}

    # Output: TSV per (mailbox, esp)
    out_rows = []
    for (mb, esp), c in cell.items():
        sent = c["sent"]
        oprate = (c["opened"] / sent) if sent else 0.0
        rrate = (c["replied"] / sent) if sent else 0.0
        out_rows.append(
            {
                "mailbox_id": mb,
                "recipient_esp": esp,
                "sent": sent,
                "opened": c["opened"],
                "replied": c["replied"],
                "leads_bounced": c["leads_bounced"],
                "open_rate": round(oprate, 4),
                "reply_rate": round(rrate, 4),
                "in_bhaskar_pool": mb in BHASKAR_IDS,
            }
        )
    out_rows.sort(
        key=lambda r: (-int(r["in_bhaskar_pool"]), r["mailbox_id"], r["recipient_esp"])
    )

    out_path = "/tmp/onsocial_outlook_hypothesis.tsv"
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)

    json_path = "/tmp/onsocial_outlook_hypothesis.json"
    with open(json_path, "w") as f:
        json.dump(
            {
                "leads_total": len(leads),
                "domains_total": len(domains),
                "esp_domain_counts": dict(counts),
                "rows": out_rows,
            },
            f,
            indent=2,
        )

    # Console summary: bhaskar mailboxes ranked by Outlook open_rate
    print("\n=== Bhaskar mailboxes -- ranked by Outlook open_rate (asc) ===")
    bh = [
        r for r in out_rows if r["in_bhaskar_pool"] and r["recipient_esp"] == "outlook"
    ]
    bh.sort(key=lambda r: (r["open_rate"], -r["sent"]))
    print(f"{'mailbox_id':>12}  {'sent':>5} {'opened':>6}  {'open%':>6}  {'reply%':>6}")
    for r in bh:
        print(
            f"{r['mailbox_id']:>12}  {r['sent']:>5} {r['opened']:>6}  "
            f"{r['open_rate'] * 100:>5.1f}%  {r['reply_rate'] * 100:>5.1f}%"
        )

    print("\n=== Bhaskar mailboxes -- Gmail baseline ===")
    bg = [r for r in out_rows if r["in_bhaskar_pool"] and r["recipient_esp"] == "gmail"]
    bg.sort(key=lambda r: (r["open_rate"], -r["sent"]))
    print(f"{'mailbox_id':>12}  {'sent':>5} {'opened':>6}  {'open%':>6}  {'reply%':>6}")
    for r in bg:
        print(
            f"{r['mailbox_id']:>12}  {r['sent']:>5} {r['opened']:>6}  "
            f"{r['open_rate'] * 100:>5.1f}%  {r['reply_rate'] * 100:>5.1f}%"
        )

    print(f"\nElapsed: {time.time() - started:.1f}s")
    print(f"TSV: {out_path}\nJSON: {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Random sample N leads per campaign (default = all leads)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.sample))
