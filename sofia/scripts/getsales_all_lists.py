#!/usr/bin/env python3
"""Fetch ALL GetSales lists (634 total) and find all OnSocial-related ones."""
import httpx
import json
import time

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

# Known replied list UUIDs (from scan results)
REPLIED_LIST_UUIDS = {
    "1481eb69", "29945658", "c9bcbe01", "c78d4a94",
    "58e1544e", "2f317ddf", "c45fa10e", "2f900c3a",
    "aa4ad892",
}

all_lists = []
offset = 0
limit = 100

while True:
    r = client.get(
        "https://amazing.getsales.io/leads/api/lists",
        params={"limit": limit, "offset": offset}
    )
    if r.status_code != 200:
        break
    data = r.json()
    batch = data.get("data", [])
    if not batch:
        break
    all_lists.extend(batch)
    offset += len(batch)
    if not data.get("has_more") or offset >= data.get("total", 0):
        break
    time.sleep(0.2)

print(f"Total lists fetched: {len(all_lists)}")

# Find OnSocial lists
os_keywords = ["onsocial", "on social", "infplat", "imagency", "india", "mena", "apac",
               "rajat", "albina", "sally", "platforms", "agencies", "influencer"]

os_lists = []
for l in all_lists:
    name_lower = l.get("name", "").lower()
    if any(kw in name_lower for kw in os_keywords):
        os_lists.append(l)

print(f"\n=== OnSocial/related lists ({len(os_lists)}) ===")
for l in os_lists:
    uuid_short = l["uuid"][:8]
    in_replied = any(l["uuid"].startswith(u) for u in REPLIED_LIST_UUIDS)
    flag = " ← HAS REPLIES THIS WEEK" if in_replied else ""
    print(f"  [{l['uuid']}] {l['name']}{flag}")

# Also show lists that had replies this week
print(f"\n=== Lists with replies this week (full names) ===")
for l in all_lists:
    if any(l["uuid"].startswith(u) for u in REPLIED_LIST_UUIDS):
        print(f"  [{l['uuid'][:8]}...] {l['name']}")

# Show all list names that include "rajat" or "albina"
print(f"\n=== Lists matching 'rajat' or 'albina' ===")
for l in all_lists:
    if "rajat" in l.get("name", "").lower() or "albina" in l.get("name", "").lower():
        print(f"  [{l['uuid']}] {l['name']}")

# Save all lists
with open("/tmp/gs_all_lists.json", "w") as f:
    json.dump(all_lists, f, indent=2)
print(f"\nSaved {len(all_lists)} lists to /tmp/gs_all_lists.json")
