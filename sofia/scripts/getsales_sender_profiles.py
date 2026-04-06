#!/usr/bin/env python3
"""Find sender profiles (Rajat, Albina) and their replied leads."""
import httpx
import json
import time

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

TARGET_NAMES = ["rajat", "albina"]

def get(path, params=None):
    url = f"https://amazing.getsales.io{path}"
    try:
        r = client.get(url, params=params or {})
        print(f"  GET {path} [{','.join(f'{k}={v}' for k,v in (params or {}).items())}] → {r.status_code}")
        if r.status_code == 200 and r.text.strip():
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"    [{len(data)} items]", end="")
                    if data:
                        print(f" keys={list(data[0].keys()) if isinstance(data[0], dict) else '?'}")
                        for item in data[:5]:
                            print(f"      {json.dumps(item)[:200]}")
                    else:
                        print()
                elif isinstance(data, dict):
                    print(f"    keys={list(data.keys())}")
                    items = data.get("data", [])
                    print(f"    total={data.get('total')}, items={len(items)}")
                    for item in items[:5]:
                        print(f"      {json.dumps(item)[:200]}")
                return data
            except Exception as e:
                print(f"    parse error: {e} | body: {r.text[:100]}")
        elif r.status_code != 404:
            print(f"    body: {r.text[:100]}")
    except Exception as e:
        print(f"    error: {e}")
    return None

print("=== 1. Sender profile endpoints ===")
get("/leads/api/sender-profiles")
get("/leads/api/linkedin-sender-profiles")
get("/api/sender-profiles")
get("/api/v1/sender-profiles")

print("\n=== 2. Single lead detail (check flows) ===")
# Get a lead and check its full structure
r = client.get("https://amazing.getsales.io/leads/api/leads/2cf18cfc-fd3b-486b-bd83-33276e95461a")
if r.status_code == 200:
    data = r.json()
    print(f"  Single lead keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    print(f"  Full: {json.dumps(data, indent=2)[:2000]}")

print("\n=== 3. Lists with 'OnSocial' or sender filter ===")
r = client.get("https://amazing.getsales.io/leads/api/lists", params={"limit": 200})
if r.status_code == 200:
    data = r.json()
    lists = data.get("data", [])
    print(f"  Total lists: {data.get('total')}, fetched: {len(lists)}")
    os_lists = [l for l in lists if any(kw in l.get("name","").lower() for kw in ["onsocial","on social","infplat","imagency","india","mena","apac"])]
    print(f"  OnSocial-related lists ({len(os_lists)}):")
    for l in os_lists:
        print(f"    [{l['uuid']}] {l['name']}")

print("\n=== 4. Check flows field in leads with last_stop_on_reply_at ===")
# Scan more leads to find one with flows
offset = 0
found = 0
while found < 3 and offset < 500:
    r = client.get("https://amazing.getsales.io/leads/api/leads", params={"limit": 50, "offset": offset})
    if r.status_code != 200:
        break
    data = r.json()
    batch = data.get("data", [])
    if not batch:
        break
    for item in batch:
        lead = item["lead"]
        flows = item.get("flows", [])
        if flows:
            print(f"\n  Lead with flows: {lead.get('first_name')} {lead.get('last_name')}")
            print(f"  replied_at: {lead.get('last_stop_on_reply_at')}")
            print(f"  flows: {json.dumps(flows, indent=2)[:1000]}")
            found += 1
            if found >= 3:
                break
        if lead.get("last_stop_on_reply_at") and not flows:
            print(f"\n  Replied lead WITHOUT flows: {lead.get('first_name')} {lead.get('last_name')} | replied={lead.get('last_stop_on_reply_at')} | list={lead.get('list_uuid')}")
            found += 1
            if found >= 3:
                break
    offset += 50
    time.sleep(0.3)

print(f"\nScanned {offset} leads, found {found} with flows/replies")
