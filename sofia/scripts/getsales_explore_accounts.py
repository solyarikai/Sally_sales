#!/usr/bin/env python3
"""Explore GetSales API to find Rajat Chauhan and Albina Yanchanka accounts + their replies."""
import httpx
import json
import time

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

TARGET_ACCOUNTS = ["rajat chauhan", "albina yanchanka"]

def try_endpoint(path, params=None):
    url = f"https://amazing.getsales.io{path}"
    try:
        r = client.get(url, params=params or {})
        print(f"  GET {path} → {r.status_code}")
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, list):
                print(f"    List of {len(data)} items")
                if data:
                    print(f"    First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else data[0]}")
                    print(f"    First item: {json.dumps(data[0], indent=2)[:500]}")
            elif isinstance(data, dict):
                print(f"    Dict keys: {list(data.keys())}")
                print(f"    Preview: {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            print(f"    Body: {r.text[:200]}")
    except Exception as e:
        print(f"    Error: {e}")
    return None

print("=== 1. Explore account-related endpoints ===")
try_endpoint("/leads/api/accounts")
try_endpoint("/leads/api/linkedin-accounts")
try_endpoint("/leads/api/users")
try_endpoint("/api/accounts")
try_endpoint("/api/linkedin-accounts")
try_endpoint("/api/users")

print("\n=== 2. Check /leads/api/lists for account info ===")
lists_data = try_endpoint("/leads/api/lists")

print("\n=== 3. Sample a few leads to see if they have account fields ===")
r = client.get("https://amazing.getsales.io/leads/api/leads", params={"limit": 3, "offset": 0})
if r.status_code == 200:
    data = r.json()
    batch = data.get("data", [])
    if batch:
        print(f"Lead keys: {list(batch[0].keys())}")
        lead = batch[0].get("lead", batch[0])
        print(f"Inner lead keys: {list(lead.keys()) if isinstance(lead, dict) else 'not dict'}")
        print(json.dumps(batch[0], indent=2)[:1000])

print("\n=== 4. Search for Rajat and Albina by name ===")
for name in ["Rajat", "Albina"]:
    r = client.get("https://amazing.getsales.io/leads/api/leads", params={"search": name, "limit": 5})
    if r.status_code == 200 and r.text.strip():
        data = r.json()
        batch = data.get("data", [])
        print(f"\n  Search '{name}': {len(batch)} results, total={data.get('total')}")
        for item in batch[:3]:
            lead = item.get("lead", item)
            print(f"    {lead.get('first_name')} {lead.get('last_name')} | li={lead.get('linkedin')} | keys_extra={[k for k in item.keys() if k != 'lead']}")
