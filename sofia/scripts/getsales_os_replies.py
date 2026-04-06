#!/usr/bin/env python3
"""
Fetch OnSocial LinkedIn replies this week (27/03-03/04) from GetSales.
Filter by OS list UUIDs, check sender_profile_uuid in markers.
"""
import httpx
import json
import time
from datetime import datetime, timezone

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

# OnSocial lists from previous exploration
OS_LISTS = {
    "5c955efc-b23b-402a-a82b-1b0af670c94c": "OS | INFPLAT_MENA_APAC_04.01",
    "a6e3ae0c-f4f9-4279-bc4f-c2d6e59a7a01": "OS | INFPLAT_INDIA | 01.04",
    "43c1e21f-1eb8-4f69-9611-e4ce0119a2f7": "OS | IMAGENCY_INDIA | 01.04",
    "67b27d2a-0497-4629-8880-02d9c5b8459a": "OnSocial |",
    "cef12704-4430-48bb-b374-82c16a399b8e": "OnSocial_Sally - LEADS #C",
    "c0a6c29d-f091-4f8f-b44d-de16a3a26022": "OnSocial | Platforms",
    "25932db3-0e53-42a5-9864-5796047e7907": "OnSocial_MA",
    "9820884e-69c3-42fa-ac5d-4aa1d8461832": "OnSocial | IM platforms & SaaS",
    "f8552177-4cd7-486c-be88-31ca16d30c6d": "OnSocial | Marketing agencies",
    "e7b27509-3440-44fe-aaee-367fd720e113": "OnSocial | PR firms",
    "5671d165-62ee-424e-be85-69831a3defcf": "OnSocial | Generic",
}

WEEK_START = "2026-03-27T00:00:00Z"
WEEK_END   = "2026-04-04T00:00:00Z"

def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except:
        return None

week_start_dt = parse_dt(WEEK_START)
week_end_dt   = parse_dt(WEEK_END)

def in_week(dt_str):
    dt = parse_dt(dt_str)
    if not dt:
        return False
    return week_start_dt <= dt <= week_end_dt

sender_profiles_seen = {}  # uuid → {name, count}
all_replied = []

print(f"Scanning {len(OS_LISTS)} OnSocial lists for replies {WEEK_START[:10]} → {WEEK_END[:10]}")
print("=" * 70)

for list_uuid, list_name in OS_LISTS.items():
    print(f"\n[{list_name}]")
    offset = 0
    limit = 200
    list_replied = []
    list_total = 0

    while True:
        r = client.get(
            "https://amazing.getsales.io/leads/api/leads",
            params={"list_uuid": list_uuid, "limit": limit, "offset": offset}
        )
        if r.status_code == 429:
            time.sleep(15)
            continue
        if r.status_code != 200 or not r.text.strip():
            break

        data = r.json()
        batch = data.get("data", [])
        if offset == 0:
            list_total = data.get("total", 0)
        if not batch:
            break

        for item in batch:
            lead = item["lead"]
            markers = item.get("markers", [])

            # Check if replied this week
            replied_at = lead.get("last_stop_on_reply_at")
            if not in_week(replied_at):
                continue

            # Get sender profile from markers
            sender_uuid = None
            marker_info = {}
            if markers:
                m = markers[0] if isinstance(markers, list) else markers
                sender_uuid = m.get("sender_profile_uuid")
                marker_info = m

            # Track sender profiles
            if sender_uuid:
                if sender_uuid not in sender_profiles_seen:
                    sender_profiles_seen[sender_uuid] = {"count": 0}
                sender_profiles_seen[sender_uuid]["count"] += 1

            list_replied.append({
                "list": list_name,
                "list_uuid": list_uuid,
                "first_name": lead.get("first_name", ""),
                "last_name": lead.get("last_name", ""),
                "position": lead.get("position", ""),
                "company": lead.get("company_name", ""),
                "linkedin": lead.get("linkedin", ""),
                "email": lead.get("work_email") or lead.get("personal_email") or "",
                "replied_at": replied_at,
                "pipeline_stage": lead.get("pipeline_stage_uuid", ""),
                "linkedin_status": lead.get("linkedin_status", ""),
                "sender_profile_uuid": sender_uuid,
                "unread_counts": lead.get("unread_counts", []),
                "tags": lead.get("tags", []),
            })

        offset += len(batch)
        if not data.get("has_more") or offset >= list_total:
            break
        time.sleep(0.3)

    print(f"  Total in list: {list_total} | Replied this week: {len(list_replied)}")
    all_replied.extend(list_replied)
    for r in list_replied:
        print(f"  ✓ {r['first_name']} {r['last_name']} | {r['position']} @ {r['company']}")
        print(f"    replied: {r['replied_at']} | sender_uuid: {r['sender_profile_uuid']}")
        print(f"    linkedin: {r['linkedin']} | unread: {r['unread_counts']}")

print("\n" + "=" * 70)
print(f"TOTAL REPLIED THIS WEEK: {len(all_replied)}")
print(f"\nSender profile UUIDs seen ({len(sender_profiles_seen)}):")
for uuid, info in sender_profiles_seen.items():
    print(f"  {uuid} → {info['count']} leads")

# Try to look up sender profile names
print("\n=== Fetching sender profile details ===")
for uuid in sender_profiles_seen:
    r = client.get(f"https://amazing.getsales.io/leads/api/sender-profiles/{uuid}")
    print(f"  /sender-profiles/{uuid} → {r.status_code}")
    if r.status_code == 200 and r.text.strip():
        try:
            data = r.json()
            print(f"    {json.dumps(data)[:300]}")
        except:
            pass
