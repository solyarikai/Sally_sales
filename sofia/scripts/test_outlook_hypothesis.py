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

    raw_path = "/tmp/onsocial_leads_raw.jsonl"
    if os.path.exists(raw_path) and not os.environ.get("FORCE_REFETCH"):
        print(f"[3/4] Reuse cached lead-level data: {raw_path}", flush=True)
        leads_raw: list[dict] = []
        with open(raw_path) as f:
            for line in f:
                leads_raw.append(json.loads(line))
    else:
        print(
            f"[3/4] Pull message-history for {len(leads)} leads (saving raw)...",
            flush=True,
        )
        leads_raw = []
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(CONCURRENCY)

            async def fetch(l: dict):
                async with sem:
                    try:
                        history = await fetch_message_history(
                            session, l["campaign_id"], l["lead_id"]
                        )
                    except Exception:
                        history = []
                    domain = l["email"].split("@", 1)[-1] if "@" in l["email"] else ""
                    sends = [
                        (evt.get("from") or "").strip().lower()
                        for evt in history
                        if (evt.get("type") or "").upper() == "SENT" and evt.get("from")
                    ]
                    return {
                        "campaign_id": l["campaign_id"],
                        "lead_id": l["lead_id"],
                        "email": l["email"],
                        "recipient_domain": domain,
                        "status": (l.get("status") or "").upper(),
                        "n_sends": len(sends),
                        "first_sender": sends[0] if sends else None,
                        "last_sender": sends[-1] if sends else None,
                    }

            done = 0
            for fut in asyncio.as_completed([fetch(l) for l in leads]):
                row = await fut
                leads_raw.append(row)
                done += 1
                if done % 200 == 0:
                    print(f"     {done}/{len(leads)}", flush=True)
        with open(raw_path, "w") as f:
            for row in leads_raw:
                f.write(json.dumps(row) + "\n")
        print(f"     saved {len(leads_raw)} rows -> {raw_path}", flush=True)

    print(
        "[4/4] Aggregate matrix (lead-level, attribute = first_sender)...", flush=True
    )
    bounce_status = {"BOUNCED", "BOUNCE", "INVALID"}
    reply_status = {"REPLIED"}

    cell: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {
            "leads": 0,
            "leads_replied": 0,
            "leads_bounced": 0,
            "leads_completed": 0,
            "leads_inprogress": 0,
            "sends_total": 0,
        }
    )
    for r in leads_raw:
        if not r.get("first_sender"):
            continue
        sender = r["first_sender"]
        esp = esp_by_domain.get(r["recipient_domain"], "unknown")
        key = (sender, esp)
        c = cell[key]
        c["leads"] += 1
        c["sends_total"] += r["n_sends"]
        st = r["status"]
        if st in reply_status:
            c["leads_replied"] += 1
        elif st in bounce_status:
            c["leads_bounced"] += 1
        elif st == "COMPLETED":
            c["leads_completed"] += 1
        elif st in {"INPROGRESS", "IN_PROGRESS"}:
            c["leads_inprogress"] += 1

    # Output: TSV per (mailbox_email, esp)
    out_rows = []
    for (mb_email, esp), c in cell.items():
        sent = c["sent"]
        oprate = (c["opened"] / sent) if sent else 0.0
        rrate = (c["replied"] / sent) if sent else 0.0
        sender_domain = mb_email.split("@", 1)[-1] if "@" in mb_email else mb_email
        out_rows.append(
            {
                "sender_email": mb_email,
                "sender_domain": sender_domain,
                "mailbox_id": BHASKAR_POOL.get(mb_email, ""),
                "recipient_esp": esp,
                "sent": sent,
                "opened": c["opened"],
                "replied": c["replied"],
                "leads_bounced": c["leads_bounced"],
                "open_rate": round(oprate, 4),
                "reply_rate": round(rrate, 4),
                "in_bhaskar_pool": mb_email in BHASKAR_POOL,
            }
        )
    out_rows.sort(
        key=lambda r: (
            -int(r["in_bhaskar_pool"]),
            r["sender_email"],
            r["recipient_esp"],
        )
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

    def _print_table(title: str, rows: list[dict]):
        print(f"\n=== {title} ===")
        print(
            f"{'sender':<42}  {'sent':>5} {'open':>5}  {'open%':>6}  "
            f"{'reply':>5} {'reply%':>6}  {'bnc':>4}"
        )
        for r in rows:
            print(
                f"{r['sender_email']:<42}  "
                f"{r['sent']:>5} {r['opened']:>5}  {r['open_rate'] * 100:>5.1f}%  "
                f"{r['replied']:>5} {r['reply_rate'] * 100:>5.1f}%  "
                f"{r['leads_bounced']:>4}"
            )

    bh_outlook = [
        r for r in out_rows if r["in_bhaskar_pool"] and r["recipient_esp"] == "outlook"
    ]
    bh_outlook.sort(key=lambda r: (r["open_rate"], -r["sent"]))
    _print_table("Bhaskar mailboxes -- Outlook recipients (worst -> best)", bh_outlook)

    bh_gmail = [
        r for r in out_rows if r["in_bhaskar_pool"] and r["recipient_esp"] == "gmail"
    ]
    bh_gmail.sort(key=lambda r: (r["open_rate"], -r["sent"]))
    _print_table("Bhaskar mailboxes -- Gmail baseline (worst -> best)", bh_gmail)

    # Per-domain rollup (3 mailboxes per domain × 2 personas = data point)
    dom = defaultdict(lambda: {"sent": 0, "opened": 0, "replied": 0, "bounced": 0})
    for r in out_rows:
        if not r["in_bhaskar_pool"] or r["recipient_esp"] != "outlook":
            continue
        d = dom[r["sender_domain"]]
        d["sent"] += r["sent"]
        d["opened"] += r["opened"]
        d["replied"] += r["replied"]
        d["bounced"] += r["leads_bounced"]
    dom_rows = []
    for sender_domain, c in dom.items():
        sent = c["sent"]
        dom_rows.append(
            {
                "sender_domain": sender_domain,
                "sent": sent,
                "opened": c["opened"],
                "replied": c["replied"],
                "leads_bounced": c["bounced"],
                "open_rate": round((c["opened"] / sent) if sent else 0.0, 4),
                "reply_rate": round((c["replied"] / sent) if sent else 0.0, 4),
            }
        )
    dom_rows.sort(key=lambda r: (r["open_rate"], -r["sent"]))
    print("\n=== Per-domain rollup -- Outlook recipients (worst -> best) ===")
    print(
        f"{'sender_domain':<28}  {'sent':>5} {'open':>5}  {'open%':>6}  "
        f"{'reply':>5} {'reply%':>6}  {'bnc':>4}"
    )
    for r in dom_rows:
        print(
            f"{r['sender_domain']:<28}  {r['sent']:>5} {r['opened']:>5}  "
            f"{r['open_rate'] * 100:>5.1f}%  {r['replied']:>5} {r['reply_rate'] * 100:>5.1f}%  "
            f"{r['leads_bounced']:>4}"
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
