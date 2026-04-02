#!/usr/bin/env python3
"""Explore GetSales API to find how to exclude/stop leads."""
import httpx
import json

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=15)

# Load exclusion list
data = json.load(open("/tmp/smartlead_export/GS_EXCLUDE_replied.json"))
exclude = data["exclude_from_gs"]
print(f"Leads to exclude: {len(exclude)}")

# Look at the first lead in detail
uuid = exclude[0]["gs_uuid"]
print(f"\nChecking lead UUID: {uuid}")

r = client.get(f"https://amazing.getsales.io/leads/api/leads/{uuid}")
ct = r.headers.get("content-type", "")
print(f"GET leads/{uuid}: {r.status_code} [{ct[:30]}]")
if "json" in ct:
    print(json.dumps(r.json(), indent=2)[:2000])

# Check pipeline stages
print("\n--- Pipeline stages ---")
r = client.get("https://amazing.getsales.io/leads/api/pipeline-stages")
ct = r.headers.get("content-type", "")
print(f"Status: {r.status_code} [{ct[:30]}]")
if "json" in ct:
    print(r.text[:800])

# Check markers
print("\n--- Markers ---")
r = client.get("https://amazing.getsales.io/leads/api/markers")
ct = r.headers.get("content-type", "")
print(f"Status: {r.status_code} [{ct[:30]}]")
if "json" in ct:
    print(r.text[:800])

# Check flows
print("\n--- Flows ---")
r = client.get("https://amazing.getsales.io/leads/api/flows")
ct = r.headers.get("content-type", "")
print(f"Status: {r.status_code} [{ct[:30]}]")
if "json" in ct:
    print(r.text[:800])

# Try DELETE endpoint
print("\n--- DELETE test (dry run - OPTIONS only) ---")
r = client.request("OPTIONS", f"https://amazing.getsales.io/leads/api/leads/{uuid}")
print(f"OPTIONS: {r.status_code}, Allow: {r.headers.get('allow', 'n/a')}")

# Try PATCH to update status
print("\n--- PATCH test ---")
r = client.patch(
    f"https://amazing.getsales.io/leads/api/leads/{uuid}",
    json={"status": "test"},
)
ct = r.headers.get("content-type", "")
print(f"PATCH: {r.status_code} [{ct[:30]}] {r.text[:300]}")
