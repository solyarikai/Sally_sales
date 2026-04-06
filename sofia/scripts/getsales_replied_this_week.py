#!/usr/bin/env python3
"""
One-pass scan: find ALL leads replied 27/03-03/04 in GetSales.
Identify sender_profile_uuids matching Rajat/Albina (OnSocial accounts).
Much faster: single scan, not 11x repeated.
"""
import httpx
import json
import time
from datetime import datetime

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

# OnSocial lists (all known)
OS_LIST_UUIDS = {
    "5c955efc-b23b-402a-a82b-1b0af670c94c",
    "a6e3ae0c-f4f9-4279-bc4f-c2d6e59a7a01",
    "43c1e21f-1eb8-4f69-9611-e4ce0119a2f7",
    "67b27d2a-0497-4629-8880-02d9c5b8459a",
    "cef12704-4430-48bb-b374-82c16a399b8e",
    "c0a6c29d-f091-4f8f-b44d-de16a3a26022",
    "25932db3-0e53-42a5-9864-5796047e7907",
    "9820884e-69c3-42fa-ac5d-4aa1d8461832",
    "f8552177-4cd7-486c-be88-31ca16d30c6d",
    "e7b27509-3440-44fe-aaee-367fd720e113",
    "5671d165-62ee-424e-be85-69831a3defcf",
}

WEEK_START = datetime.fromisoformat("2026-03-27T00:00:00+00:00")
WEEK_END   = datetime.fromisoformat("2026-04-04T00:00:00+00:00")

def in_week(s):
    if not s:
        return False
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return WEEK_START <= dt <= WEEK_END
    except:
        return False

# Single pass over all leads
offset = 0
limit = 500
total = None
all_replied = []
sender_uuid_counts = {}
os_replied = []

print("Scanning all leads for replies 27/03-03/04...")
t0 = time.time()
pages = 0

while True:
    r = client.get(
        "https://amazing.getsales.io/leads/api/leads",
        params={"limit": limit, "offset": offset}
    )
    if r.status_code == 429:
        print("  Rate limited, waiting 15s...")
        time.sleep(15)
        continue
    if r.status_code != 200 or not r.text.strip():
        print(f"  Error at offset {offset}: status={r.status_code}")
        break

    data = r.json()
    if total is None:
        total = data.get("total", 0)
        print(f"Total leads: {total:,}")

    batch = data.get("data", [])
    if not batch:
        break

    for item in batch:
        lead = item["lead"]
        markers = item.get("markers", [])
        replied_at = lead.get("last_stop_on_reply_at")

        if not in_week(replied_at):
            continue

        sender_uuid = None
        if markers:
            m = markers[0] if isinstance(markers, list) else markers
            sender_uuid = m.get("sender_profile_uuid")

        if sender_uuid:
            sender_uuid_counts[sender_uuid] = sender_uuid_counts.get(sender_uuid, 0) + 1

        lead_list_uuid = lead.get("list_uuid", "")
        is_os = lead_list_uuid in OS_LIST_UUIDS

        entry = {
            "first_name": lead.get("first_name", ""),
            "last_name": lead.get("last_name", ""),
            "position": lead.get("position", ""),
            "company": lead.get("company_name", ""),
            "linkedin": lead.get("linkedin", ""),
            "replied_at": replied_at,
            "list_uuid": lead_list_uuid,
            "sender_uuid": sender_uuid,
            "is_os": is_os,
        }
        all_replied.append(entry)
        if is_os:
            os_replied.append(entry)

    offset += len(batch)
    pages += 1

    if pages % 20 == 0:
        elapsed = time.time() - t0
        pct = offset / total * 100 if total else 0
        print(f"  {offset:,}/{total:,} ({pct:.1f}%) | {elapsed:.0f}s | replied this week: {len(all_replied)}")

    if not data.get("has_more") or offset >= total:
        break
    time.sleep(0.2)

elapsed = time.time() - t0
print(f"\nDone: {offset:,} leads scanned in {elapsed:.0f}s")
print(f"Replied this week (all): {len(all_replied)}")
print(f"Replied this week (OS lists): {len(os_replied)}")

print(f"\n=== Sender profile UUIDs (all replied this week) ===")
for uuid, count in sorted(sender_uuid_counts.items(), key=lambda x: -x[1]):
    print(f"  {uuid} — {count} replies")

print(f"\n=== OS list replied leads ===")
for r in os_replied:
    print(f"  {r['first_name']} {r['last_name']} | {r['position']} @ {r['company']}")
    print(f"    replied: {r['replied_at']} | sender: {r['sender_uuid']} | list: {r['list_uuid']}")

# Try to look up sender profiles
print(f"\n=== Fetching sender profile names ===")
for uuid in sender_uuid_counts:
    resp = client.get(f"https://amazing.getsales.io/leads/api/sender-profiles/{uuid}")
    if resp.status_code == 200 and resp.text.strip():
        try:
            d = resp.json()
            name = d.get("name") or d.get("first_name", "") + " " + d.get("last_name", "")
            ln = d.get("linkedin") or d.get("linkedin_url") or ""
            print(f"  {uuid}: {name.strip()} | {ln} | {json.dumps(d)[:150]}")
        except:
            pass
    elif resp.status_code != 404:
        print(f"  {uuid}: status={resp.status_code}")

# Save result
import json as jsmod
with open("/tmp/gs_replied_week7.json", "w") as f:
    jsmod.dump({
        "all_replied": all_replied,
        "os_replied": os_replied,
        "sender_uuid_counts": sender_uuid_counts,
    }, f, indent=2)
print(f"\nSaved to /tmp/gs_replied_week7.json")
