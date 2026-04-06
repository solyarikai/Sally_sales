#!/usr/bin/env python3
"""
Weekly GetSales stats for OnSocial — Rajat Chauhan & Albina Yanchanka
Week: 2026-03-27 → 2026-04-03

Uses the efficient flows API approach (per magnum-opus patterns):
  1. /flows/api/flows             → find flows by sender profile (Rajat / Albina)
  2. /flows/api/linkedin-messages → inbox replies filtered by date (not list-by-list scanning)
  3. /flows/api/flows-leads       → leads contacted per flow

Run locally:
  python3.11 sofia/scripts/getsales_weekly_stats.py

Or on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && \
    python3 sofia/scripts/getsales_weekly_stats.py"
"""
import os
import asyncio
import json
from datetime import datetime, timezone

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
GS_TOKEN = os.environ.get(
    "GETSALES_API_KEY",
    # fallback for local runs without env
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"
)
BASE = "https://amazing.getsales.io"
HEADERS = {"Authorization": f"Bearer {GS_TOKEN}"}

WEEK_START = datetime(2026, 3, 27, tzinfo=timezone.utc)
WEEK_END   = datetime(2026, 4,  4, tzinfo=timezone.utc)

TARGET_ACCOUNTS = ["rajat", "albina"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def in_week(dt_str: str) -> bool:
    if not dt_str:
        return False
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return WEEK_START <= dt < WEEK_END
    except Exception:
        return False


async def get_paginated(client: httpx.AsyncClient, path: str, params: dict = None) -> list:
    """Fetch all pages from a paginated GetSales endpoint."""
    results = []
    offset = 0
    limit = 200
    base_params = {**(params or {}), "limit": limit}

    while True:
        r = await client.get(f"{BASE}{path}", params={**base_params, "offset": offset})
        if r.status_code == 429:
            await asyncio.sleep(15)
            continue
        if r.status_code != 200 or not r.text.strip():
            break
        data = r.json()
        batch = data.get("data", [])
        results.extend(batch)
        offset += len(batch)
        if not batch or not data.get("has_more") or offset >= data.get("total", 0):
            break
        await asyncio.sleep(0.2)

    return results


# ── Step 1: Get all flows with sender info ────────────────────────────────────
async def fetch_flows(client: httpx.AsyncClient) -> list:
    """GET /flows/api/flows — returns campaigns with sender_profile_uuid."""
    r = await client.get(f"{BASE}/flows/api/flows", params={"per_page": 200})
    if r.status_code == 200:
        return r.json().get("data", [])
    # try paginated form
    return await get_paginated(client, "/flows/api/flows")


# ── Step 2: Fetch messages by direction ───────────────────────────────────────
async def fetch_messages(client: httpx.AsyncClient, msg_type: str) -> list:
    """
    GET /flows/api/linkedin-messages?filter[type]=inbox|outbox|sent
    msg_type: "inbox" (replies) or "outbox" (sent by us)
    Stops early once messages go past the week window.
    """
    results = []
    offset = 0
    limit = 200
    pages_scanned = 0

    while True:
        r = await client.get(
            f"{BASE}/flows/api/linkedin-messages",
            params={
                "filter[type]": msg_type,
                "order_field": "sent_at",
                "order_type": "desc",
                "limit": limit,
                "offset": offset,
            }
        )
        if r.status_code == 429:
            await asyncio.sleep(15)
            continue
        if r.status_code != 200 or not r.text.strip():
            break

        data = r.json()
        batch = data.get("data", [])
        if not batch:
            break

        pages_scanned += 1
        too_old = 0

        for msg in batch:
            sent_at = msg.get("sent_at", "")
            if in_week(sent_at):
                results.append(msg)
            elif sent_at and sent_at < "2026-03-27":
                too_old += 1

        offset += len(batch)
        total = data.get("total", 0)
        print(f"  [{msg_type}] page {pages_scanned}: {offset}/{total} | week: {len(results)} | too old: {too_old}")

        if too_old == len(batch) and pages_scanned > 1:
            print(f"  [{msg_type}] Past week window, stopping.")
            break

        if not data.get("has_more") or offset >= total:
            break
        await asyncio.sleep(0.2)

    return results


# ── Step 3: Leads contacted per flow (count) ─────────────────────────────────
async def fetch_flow_lead_count(client: httpx.AsyncClient, flow_uuid: str) -> int:
    """GET /flows/api/flows-leads?filter[flow_uuid]=X — total leads in flow."""
    r = await client.get(
        f"{BASE}/flows/api/flows-leads",
        params={"filter[flow_uuid]": flow_uuid, "limit": 1}
    )
    if r.status_code == 200 and r.text.strip():
        return r.json().get("total", 0)
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:

        # 1. Fetch all flows
        print("Fetching flows (campaigns)...")
        flows = await fetch_flows(client)
        print(f"  Found {len(flows)} flows")

        # 2. Identify Rajat / Albina flows
        account_flows: dict[str, list] = {"Rajat Chauhan": [], "Albina Yanchanka": [], "Other OS": []}
        sender_uuid_to_account: dict[str, str] = {}
        all_os_keywords = ["onsocial", "infplat", "imagency", "india", "mena", "apac", "os |"]

        print("\nFlows breakdown:")
        for flow in flows:
            name_lower = flow.get("name", "").lower()
            sender_uuid = flow.get("sender_profile_uuid") or ""
            sender_name = (flow.get("sender_name") or flow.get("sender", {}).get("name", "") or "").lower()

            full_text = name_lower + " " + sender_name + " " + json.dumps(flow).lower()

            if "rajat" in full_text:
                account_flows["Rajat Chauhan"].append(flow)
                if sender_uuid:
                    sender_uuid_to_account[sender_uuid] = "Rajat Chauhan"
            elif "albina" in full_text:
                account_flows["Albina Yanchanka"].append(flow)
                if sender_uuid:
                    sender_uuid_to_account[sender_uuid] = "Albina Yanchanka"
            elif any(kw in full_text for kw in all_os_keywords):
                account_flows["Other OS"].append(flow)

        for account, flist in account_flows.items():
            if flist:
                print(f"  {account}: {len(flist)} flows")
                for f in flist:
                    print(f"    [{f.get('uuid','?')[:8]}] {f.get('name')} | sender_uuid={f.get('sender_profile_uuid','?')[:8] if f.get('sender_profile_uuid') else 'N/A'}")

        # 3. Fetch inbox (replies) and outbox (sent by us) for the week
        print(f"\nFetching messages ({WEEK_START.date()} → {WEEK_END.date()})...")
        inbox   = await fetch_messages(client, "inbox")
        outbox  = await fetch_messages(client, "outbox")
        print(f"  Inbox (replies):   {len(inbox)}")
        print(f"  Outbox (sent):     {len(outbox)}")

        # 4. Bucket messages by account via sender_profile_uuid
        empty_account = lambda: {"replies": [], "connects": [], "messages_out": [], "flow_leads": 0}
        stats: dict[str, dict] = {
            "Rajat Chauhan":    empty_account(),
            "Albina Yanchanka": empty_account(),
            "Other OS":         empty_account(),
            "Unknown":          empty_account(),
        }

        def msg_entry(msg):
            return {
                "lead_name": msg.get("lead_name") or (msg.get("lead") or {}).get("name", ""),
                "sent_at": msg.get("sent_at", ""),
                "linkedin_type": msg.get("linkedin_type", ""),
                "text_preview": (msg.get("text") or "")[:100],
                "sender_uuid": msg.get("sender_profile_uuid", ""),
                "flow_uuid": msg.get("flow_uuid", ""),
            }

        for msg in inbox:
            account = sender_uuid_to_account.get(msg.get("sender_profile_uuid", ""), "Unknown")
            stats[account]["replies"].append(msg_entry(msg))

        for msg in outbox:
            account = sender_uuid_to_account.get(msg.get("sender_profile_uuid", ""), "Unknown")
            ltype = (msg.get("linkedin_type") or "").lower()
            # connection_request / invite → коннект; остальное → сообщение
            if "connection" in ltype or "invite" in ltype:
                stats[account]["connects"].append(msg_entry(msg))
            else:
                stats[account]["messages_out"].append(msg_entry(msg))

        # 5. Count leads per account from flows
        print("\nFetching lead counts per flow...")
        for account, flist in account_flows.items():
            if account == "Other OS":
                continue
            for flow in flist:
                count = await fetch_flow_lead_count(client, flow["uuid"])
                stats[account]["flow_leads"] += count
                await asyncio.sleep(0.1)

        # ── Print report ───────────────────────────────────────────────────────
        print("\n" + "=" * 65)
        print(f"  WEEKLY GETSALES STATS — OnSocial")
        print(f"  Week: {WEEK_START.date()} → {WEEK_END.date()}")
        print("=" * 65)

        for account in ["Rajat Chauhan", "Albina Yanchanka"]:
            s = stats[account]
            flist = account_flows[account]
            print(f"\n{'─' * 55}")
            print(f"  {account.upper()}")
            print(f"{'─' * 55}")
            print(f"  Flows (campaigns):     {len(flist)}")
            print(f"  Total leads in flows:  {s['flow_leads']:,}")
            print(f"  Коннекты отправлены:   {len(s['connects'])}")
            print(f"  Сообщений исходящих:   {len(s['messages_out'])}")
            print(f"  Реплаев (входящих):    {len(s['replies'])}")

            if flist:
                print(f"\n  Campaigns:")
                for f in flist:
                    print(f"    {f.get('name')}")

            if s["replies"]:
                print(f"\n  Replies this week:")
                for rep in sorted(s["replies"], key=lambda x: x["sent_at"], reverse=True):
                    print(f"    {rep['sent_at'][:10]}  {rep['lead_name']}")
                    if rep["text_preview"]:
                        print(f"              \"{rep['text_preview']}\"")

        # Unknown sender check
        if stats["Unknown"]["replies"] or stats["Unknown"]["connects"] or stats["Unknown"]["messages_out"]:
            print(f"\n{'─' * 55}")
            print(f"  UNKNOWN SENDER — replies:{len(stats['Unknown']['replies'])} "
                  f"connects:{len(stats['Unknown']['connects'])} "
                  f"out:{len(stats['Unknown']['messages_out'])}")
            uuids = {m["sender_uuid"] for bucket in stats["Unknown"].values()
                     if isinstance(bucket, list) for m in bucket}
            print(f"  Unrecognized UUIDs: {uuids}")

        # Save output
        out = {
            "week": f"{WEEK_START.date()} to {WEEK_END.date()}",
            "sender_uuid_map": sender_uuid_to_account,
            "stats": {
                k: {
                    "flow_count": len(account_flows.get(k, [])),
                    "flow_leads": v["flow_leads"],
                    "connects": len(v["connects"]),
                    "messages_out": len(v["messages_out"]),
                    "replied_count": len(v["replies"]),
                    "replies": v["replies"],
                }
                for k, v in stats.items()
            },
        }
        out_path = "/tmp/gs_weekly_stats_w7.json"
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
