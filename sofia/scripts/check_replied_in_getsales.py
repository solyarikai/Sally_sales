#!/usr/bin/env python3
"""
Find SmartLead REPLIED leads in GetSales OS lists.
Goal: exclude them from LinkedIn outreach to avoid double-touching.
"""
import httpx
import csv
import io
import os
import json
import re
import time

# SmartLead
SL_API_KEY = os.environ["SMARTLEAD_API_KEY"]
SL_BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGNS = [
    (3065429, "INFPLAT_MENA_APAC"),
    (3059650, "INFPLAT_INDIA"),
    (3063527, "IMAGENCY_INDIA"),
    (3064966, "INDIA_GENERAL"),
]

# GetSales
GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"
GS_LISTS = {
    "IMAGENCY_INDIA": "43c1e21f-1eb8-4f69-9611-e4ce0119a2f7",
    "INFPLAT_INDIA": "a6e3ae0c-f4f9-4279-bc4f-c2d6e59a7a01",
    "INFPLAT_MENA_APAC": "5c955efc-b23b-402a-a82b-1b0af670c94c",
}


def extract_nickname(url):
    if not url or "/in/" not in url:
        return ""
    m = re.search(r"/in/([^/?#]+)", url.lower().rstrip("/"))
    return m.group(1).strip() if m else ""


def main():
    sl_client = httpx.Client(timeout=60)

    # --- Step 1: Get replied leads from SmartLead ---
    print("=== Step 1: SmartLead replied leads ===")
    replied = []
    for cid, cname in CAMPAIGNS:
        resp = sl_client.get(
            f"{SL_BASE}/campaigns/{cid}/leads-export",
            params={"api_key": SL_API_KEY},
        )
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            reply_count = int(row.get("reply_count", 0) or 0)
            category = (row.get("category") or "").strip()
            if reply_count > 0 or category:
                li = (row.get("linkedin_profile") or "").strip()
                replied.append({
                    "email": (row.get("email") or "").strip().lower(),
                    "first_name": row.get("first_name", ""),
                    "last_name": row.get("last_name", ""),
                    "company": row.get("company_name", ""),
                    "category": category,
                    "reply_count": reply_count,
                    "linkedin_url": li,
                    "linkedin_nickname": extract_nickname(li),
                    "campaign": cname,
                })

    print(f"Replied total: {len(replied)}")
    for r in replied:
        print(f"  [{r['campaign']}] {r['email']} | {r['first_name']} {r['last_name']} | cat={r['category']} | li={r['linkedin_nickname']}")

    # --- Step 2: Load GetSales OS lists ---
    print("\n=== Step 2: GetSales OS lists ===")
    gs_client = httpx.Client(
        headers={"Authorization": f"Bearer {GS_TOKEN}"},
        timeout=20,
    )

    gs_by_nickname = {}
    gs_by_email = {}

    for list_name, list_uuid in GS_LISTS.items():
        offset = 0
        count = 0
        while True:
            time.sleep(0.3)
            ok = False
            for attempt in range(4):
                try:
                    r = gs_client.get(
                        "https://amazing.getsales.io/leads/api/leads",
                        params={"list_uuid": list_uuid, "limit": 500, "offset": offset},
                    )
                    if not r.text.strip():
                        time.sleep(3)
                        continue
                    data = r.json()
                    ok = True
                    break
                except Exception:
                    time.sleep(3)
            if not ok:
                break

            batch = data.get("data", [])
            if not batch:
                break
            for item in batch:
                lead = item["lead"]
                li = (lead.get("linkedin") or "").strip().lower()
                email = (lead.get("work_email") or "").strip().lower()
                uuid = lead.get("uuid", "")
                name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
                info = {"name": name, "email": email, "list": list_name, "uuid": uuid, "li": li}
                if li:
                    gs_by_nickname[li] = info
                if email:
                    gs_by_email[email] = info
            count += len(batch)
            offset += len(batch)
            if not data.get("has_more"):
                break
        print(f"  {list_name}: {count} contacts")

    print(f"GetSales totals: {len(gs_by_nickname)} by LinkedIn, {len(gs_by_email)} by email")

    # --- Step 3: Cross-reference ---
    sep = "=" * 60
    print(f"\n{sep}")
    print("CROSS-REFERENCE: SmartLead replied -> GetSales")
    print(sep)

    found_in_gs = []
    not_in_gs = []

    for r in replied:
        nick = r["linkedin_nickname"]
        email = r["email"]

        gs_match = None
        match_by = ""
        if nick and nick in gs_by_nickname:
            gs_match = gs_by_nickname[nick]
            match_by = "linkedin"
        elif email and email in gs_by_email:
            gs_match = gs_by_email[email]
            match_by = "email"

        if gs_match:
            found_in_gs.append({**r, "gs_uuid": gs_match["uuid"], "gs_list": gs_match["list"]})
            print(f"  FOUND [{match_by}]: {r['first_name']} {r['last_name']} ({r['email']}) -> GS list: {gs_match['list']}")
        else:
            not_in_gs.append(r)
            print(f"  NOT IN GS: {r['first_name']} {r['last_name']} ({r['email']}) | li_nick={nick}")

    print(f"\n{sep}")
    print(f"REPLIED in SmartLead:     {len(replied)}")
    print(f"FOUND in GetSales:        {len(found_in_gs)}  <-- EXCLUDE from LinkedIn outreach")
    print(f"NOT in GetSales:          {len(not_in_gs)}  <-- no action needed")
    print(sep)

    # Save
    result = {
        "exclude_from_gs": found_in_gs,
        "not_in_gs": not_in_gs,
    }
    with open("/tmp/smartlead_export/GS_EXCLUDE_replied.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved /tmp/smartlead_export/GS_EXCLUDE_replied.json")


if __name__ == "__main__":
    main()
