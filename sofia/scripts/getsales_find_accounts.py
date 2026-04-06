#!/usr/bin/env python3
"""Find Rajat Chauhan and Albina Yanchanka accounts in GetSales via data_sources and flows."""
import httpx
import json
import time

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

def get(path, params=None):
    url = f"https://amazing.getsales.io{path}"
    r = client.get(url, params=params or {})
    print(f"  GET {path} → {r.status_code}")
    if r.status_code == 200 and r.text.strip():
        try:
            return r.json()
        except:
            pass
    return None

print("=== 1. Data sources (LinkedIn accounts) ===")
data = get("/leads/api/data-sources")
if data:
    items = data if isinstance(data, list) else data.get("data", [])
    print(f"  {len(items)} data sources")
    for item in items[:20]:
        print(f"    {json.dumps(item)}")

print("\n=== 2. Try /leads/api/senders or /leads/api/operators ===")
get("/leads/api/senders")
get("/leads/api/operators")
get("/leads/api/profiles")

print("\n=== 3. Look at flows in a sample replied lead ===")
# Get a lead with replied status
r = client.get("https://amazing.getsales.io/leads/api/leads", params={"limit": 50, "offset": 0})
if r.status_code == 200:
    data = r.json()
    batch = data.get("data", [])
    replied_leads = [item for item in batch if item["lead"].get("last_stop_on_reply_at")]
    print(f"  Found {len(replied_leads)} replied leads in first 50")
    for item in replied_leads[:2]:
        lead = item["lead"]
        flows = item.get("flows", [])
        print(f"\n  Lead: {lead.get('first_name')} {lead.get('last_name')}")
        print(f"  replied_at: {lead.get('last_stop_on_reply_at')}")
        print(f"  data_source_uuid: {lead.get('data_source_uuid')}")
        print(f"  list_uuid: {lead.get('list_uuid')}")
        print(f"  flows ({len(flows)}): {json.dumps(flows[:2], indent=2)[:800]}")

print("\n=== 4. Try lead conversations/messages endpoint ===")
# Try to get messages for a specific lead
r = client.get("https://amazing.getsales.io/leads/api/leads", params={"limit": 5})
if r.status_code == 200:
    data = r.json()
    batch = data.get("data", [])
    if batch:
        lead_uuid = batch[0]["lead"]["uuid"]
        print(f"  Testing with lead uuid: {lead_uuid}")
        get(f"/leads/api/leads/{lead_uuid}/messages")
        get(f"/leads/api/leads/{lead_uuid}/conversations")
        get(f"/leads/api/leads/{lead_uuid}/chat")
        get(f"/leads/api/leads/{lead_uuid}")

print("\n=== 5. Check inbox/messages endpoint ===")
get("/leads/api/inbox")
get("/leads/api/messages")
get("/leads/api/conversations")
get("/leads/api/chats")
