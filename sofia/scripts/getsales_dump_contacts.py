#!/usr/bin/env python3
"""Download all LinkedIn nicknames and emails from GetSales for deduplication."""
import httpx
import json
import time

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

headers = {"Authorization": f"Bearer {GS_TOKEN}"}
client = httpx.Client(headers=headers, timeout=30)

print("Downloading all GetSales contacts (linkedin nicknames + emails)...", flush=True)
gs_linkedin = set()
gs_email = set()

offset = 0
limit = 1000
total = None
t_start = time.time()

while True:
    for attempt in range(8):
        try:
            r = client.get(
                "https://amazing.getsales.io/leads/api/leads",
                params={"limit": limit, "offset": offset}
            )
            if r.status_code == 429:
                print("  Rate limited, waiting 15s...", flush=True)
                time.sleep(15)
                continue
            if not r.text.strip():
                print(f"  Empty response at offset {offset}, retry {attempt+1}...", flush=True)
                time.sleep(5 * (attempt + 1))
                continue
            data = r.json()
            break
        except Exception as e:
            print(f"  Retry {attempt+1}/8 at offset {offset}: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        print(f"  Skipping offset {offset} after 5 failures", flush=True)
        offset += limit
        continue

    if total is None:
        total = data.get("total", 0)
        print(f"Total in GetSales: {total}", flush=True)

    batch = data.get("data", [])
    if not batch:
        break

    for item in batch:
        lead = item["lead"]
        li = (lead.get("linkedin") or "").strip().lower()
        email = (lead.get("work_email") or lead.get("personal_email") or "").strip().lower()
        if li:
            gs_linkedin.add(li)
        if email:
            gs_email.add(email)

    offset += len(batch)
    if offset % 20000 == 0:
        elapsed = time.time() - t_start
        print(f"  {offset}/{total} ({elapsed:.0f}s)...", flush=True)

    if not data.get("has_more"):
        break

elapsed = time.time() - t_start
print(f"Done: {len(gs_linkedin):,} LinkedIn, {len(gs_email):,} emails in {elapsed:.0f}s", flush=True)

with open("/tmp/gs_linkedin_set.json", "w") as f:
    json.dump({"linkedin": list(gs_linkedin), "email": list(gs_email)}, f)

print("Saved to /tmp/gs_linkedin_set.json", flush=True)
