#!/usr/bin/env python3
"""
Upload GetSales-formatted xlsx files to GetSales lists via API.
Deduplicates by linkedin nickname against ALL existing GetSales contacts.

Usage:
    python3.11 sofia/scripts/upload_xlsx_to_getsales.py
"""

import json
import time
import openpyxl
import httpx

GS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

BASE = "https://amazing.getsales.io/leads/api"
HEADERS = {"Authorization": f"Bearer {GS_TOKEN}"}
BATCH_SIZE = 50

# ── File → List mapping ──────────────────────────────────────────────────────

FILES_TO_LISTS = [
    {
        "files": [
            "sofia/get_sales_hub/2026-04-01/OS _ Leads _ IMAGENCY No Email GetSales — 2026-03-28.xlsx",
        ],
        "list_uuid": "8545b518-6f88-410d-8256-dbaab2979b5d",  # OS | IM_FIRST_AGENCIES | 19.03
        "list_name": "OS | IM_FIRST_AGENCIES | 19.03",
    },
    {
        "files": [
            "sofia/get_sales_hub/2026-04-01/OS _ Leads _ INFPLAT No Email GetSales — 2026-03-28.xlsx",
            "sofia/get_sales_hub/2026-04-01/OS _ Leads _ INFPLAT No Email GetSales — 2026-03-31.xlsx",
        ],
        "list_uuid": "2f900c3a-589c-4b25-a9f4-422a0c4e57c1",  # OS | INFLUENCER_PLATFORMS | 19.03
        "list_name": "OS | INFLUENCER_PLATFORMS | 19.03",
    },
]


def read_xlsx(path: str) -> list[dict]:
    """Read xlsx into list of dicts using header row."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows_iter)]
    result = []
    for row in rows_iter:
        d = {}
        for i, val in enumerate(row):
            if i < len(header):
                d[header[i]] = str(val).strip() if val is not None else ""
        if d.get("first_name") or d.get("full_name") or d.get("linkedin_nickname"):
            result.append(d)
    wb.close()
    return result


def dedup_within_files(all_rows: list[dict]) -> list[dict]:
    """Dedup rows by linkedin_nickname within a batch of files.
    GetSales API auto-deduplicates by linkedin against existing contacts,
    so we only need to dedup between the files we're uploading."""
    seen = set()
    result = []
    skipped = 0
    for row in all_rows:
        nick = (row.get("linkedin_nickname") or "").strip().lower()
        if not nick:
            result.append(row)
            continue
        if nick in seen:
            skipped += 1
            continue
        seen.add(nick)
        result.append(row)
    if skipped:
        print(f"  Dedup between files: skipped {skipped} duplicates", flush=True)
    return result


def xlsx_row_to_gs_lead(row: dict) -> dict:
    """Convert xlsx row (GetSales export format) to GetSales API lead format."""
    # Map custom fields (cf_* columns)
    custom_fields = {}
    for k, v in row.items():
        if k.startswith("cf_") and v:
            custom_fields[k] = v

    lead = {
        "first_name": row.get("first_name", ""),
        "last_name": row.get("last_name", ""),
        "position": row.get("position", ""),
        "headline": row.get("headline", ""),
        "about": row.get("about", ""),
        "linkedin": row.get("linkedin_nickname", ""),
        "company_name": row.get("company_name", ""),
        "company_ln_id": row.get("company_linkedin_id", ""),
        "work_email": row.get("work_email", ""),
        "personal_email": row.get("personal_email", ""),
        "work_phone_number": row.get("work_phone", ""),
        "personal_phone_number": row.get("personal_phone", ""),
        "facebook": row.get("facebook_nickname", ""),
        "twitter": row.get("twitter_nickname", ""),
        "tags": [t.strip() for t in row.get("tags", "").split(",") if t.strip()],
    }

    # Add custom fields
    if custom_fields:
        lead["custom_fields"] = custom_fields

    # Clean empty values
    lead = {k: v for k, v in lead.items() if v and v != "None"}

    return lead


def upload_leads(leads: list[dict], list_uuid: str, list_name: str):
    """Upload leads to GetSales list in batches."""
    client = httpx.Client(headers=HEADERS, timeout=30)
    total_uploaded = 0

    for i in range(0, len(leads), BATCH_SIZE):
        batch = leads[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(leads) + BATCH_SIZE - 1) // BATCH_SIZE

        for attempt in range(3):
            try:
                r = client.post(
                    f"{BASE}/leads",
                    json={"leads": batch, "list_uuid": list_uuid},
                    timeout=60,
                )
                if r.status_code == 429:
                    print(f"  Rate limited, waiting 30s...", flush=True)
                    time.sleep(30)
                    continue
                if r.status_code in (200, 201):
                    data = r.json()
                    count = len(data) if isinstance(data, list) else 0
                    total_uploaded += count
                    print(f"  Batch {batch_num}/{total_batches}: {count} uploaded [{total_uploaded}/{len(leads)}]", flush=True)
                    break
                else:
                    print(f"  Batch {batch_num} error {r.status_code}: {r.text[:200]}", flush=True)
                    break
            except Exception as e:
                print(f"  Batch {batch_num} retry {attempt+1}: {e}", flush=True)
                time.sleep(5)

        time.sleep(1)  # rate limit courtesy

    client.close()
    return total_uploaded


def main():
    # GetSales API auto-deduplicates by linkedin nickname (same UUID returned).
    # We only dedup between files in each group.

    for group in FILES_TO_LISTS:
        list_uuid = group["list_uuid"]
        list_name = group["list_name"]
        files = group["files"]

        print(f"{'='*60}")
        print(f"Target list: {list_name} ({list_uuid})")

        # Step 1: Read all xlsx files for this list
        all_rows = []
        for fpath in files:
            rows = read_xlsx(fpath)
            print(f"  Read {len(rows)} rows from {fpath.split('/')[-1]}")
            all_rows.extend(rows)

        print(f"  Total rows: {len(all_rows)}")

        # Step 2: Dedup between files
        new_rows = dedup_within_files(all_rows)
        print(f"  Leads to upload: {len(new_rows)} (GS will auto-skip existing by linkedin)")

        if not new_rows:
            print(f"  Nothing to upload.\n")
            continue

        # Step 3: Convert to API format and upload
        leads_payload = [xlsx_row_to_gs_lead(row) for row in new_rows]
        uploaded = upload_leads(leads_payload, list_uuid, list_name)

        print(f"  DONE: {uploaded}/{len(new_rows)} uploaded to '{list_name}'\n")


if __name__ == "__main__":
    main()
