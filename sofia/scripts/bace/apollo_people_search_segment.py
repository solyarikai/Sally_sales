#!/usr/bin/env python3.11
"""
Apollo /mixed_people/api_search for a set of domains (one segment).

Reads domains from Postgres (target companies for a given segment across gathering runs),
pulls people via Apollo's FREE /mixed_people/api_search endpoint, writes a Google Sheet.

Usage:
  APOLLO_API_KEY=... python3.11 apollo_people_search_segment.py \
      --segment SOCIAL_COMMERCE --run-ids 423,424,425,426,427,428 --project-id 42
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

APOLLO_BASE = "https://api.apollo.io/api/v1"
TOKEN_PATH = Path("/Users/user/sales_engineer/.claude/mcp/google-sheets/token.json")
LEADS_FOLDER_ID = "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe"

# v4 people filter (universal cross-segment)
V4_TITLES = [
    "CEO",
    "Co-Founder",
    "Founder",
    "COO",
    "Managing Director",
    "Managing Partner",
    "General Manager",
    "CTO",
    "Chief Technology Officer",
    "CPO",
    "Chief Product Officer",
    "CDO",
    "Chief Data Officer",
    "CMO",
    "VP Marketing",
    "VP Engineering",
    "VP of Engineering",
    "VP Technology",
    "VP Product",
    "VP of Product",
    "VP Data",
    "VP Analytics",
    "VP Platform",
    "VP Partnerships",
    "VP Growth",
    "Head of Engineering",
    "Head of Technology",
    "Head of Product",
    "Head of Data",
    "Head of Analytics",
    "Head of Platform",
    "Head of Integrations",
    "Head of Digital",
    "Head of Partnerships",
    "Head of Growth",
    "Head of Martech",
    "Director of Engineering",
    "Director of Technology",
    "Director of Product",
    "Director of Data",
    "Director of Analytics",
    "Director of Partnerships",
    "Director of Growth",
    "Director of Martech",
    "Technical Director",
    "Technology Director",
    "Chief Architect",
    "Co-Founder CTO",
    "Founding Engineer",
    "Technical Co-Founder",
]
V4_SENIORITIES = ["c_suite", "vp", "director", "head", "partner", "founder"]


def fetch_domains(segment: str, run_ids: list[int], project_id: int) -> list[str]:
    run_list = ",".join(str(r) for r in run_ids)
    sql = f"""
        SELECT DISTINCT dc.domain
        FROM discovered_companies dc
        WHERE dc.project_id = {project_id}
          AND dc.is_target = true
          AND dc.matched_segment = '{segment}'
          AND dc.domain = ANY(
              SELECT jsonb_array_elements_text(gr.filters->'domains')
              FROM gathering_runs gr WHERE gr.id IN ({run_list})
          )
        ORDER BY 1
    """
    cmd = [
        "ssh",
        "hetzner",
        f'docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -c "{sql.strip()}"',
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"psql failed: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    return [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]


def apollo_headers(api_key: str) -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


def apollo_search_one_domain(
    domain: str, api_key: str, per_page: int = 100
) -> list[dict]:
    """Search people at one domain. Returns list of person dicts (obfuscated last_name)."""
    all_people = []
    page = 1
    while page <= 10:  # safety cap
        payload = {
            "page": page,
            "per_page": per_page,
            "q_organization_domains_list": [domain],
            "person_titles": V4_TITLES,
            "person_seniorities": V4_SENIORITIES,
            "include_similar_titles": True,
        }
        r = httpx.post(
            f"{APOLLO_BASE}/mixed_people/api_search",
            headers=apollo_headers(api_key),
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            print(
                f"  HTTP {r.status_code} for {domain}: {r.text[:200]}", file=sys.stderr
            )
            return all_people
        data = r.json()
        people = data.get("people", [])
        all_people.extend(people)
        if len(people) < per_page:
            break
        page += 1
        time.sleep(0.3)
    return all_people


def apollo_bulk_match(person_ids: list[str], api_key: str) -> list[dict]:
    """Enrich a batch of people by id. Returns list of enriched person dicts.
    Does NOT reveal personal emails (no email credit spent)."""
    if not person_ids:
        return []
    payload = {
        "details": [{"id": pid} for pid in person_ids],
        "reveal_personal_emails": False,
        "reveal_phone_number": False,
    }
    r = httpx.post(
        f"{APOLLO_BASE}/people/bulk_match",
        headers=apollo_headers(api_key),
        json=payload,
        timeout=90,
    )
    if r.status_code != 200:
        print(f"  bulk_match HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return []
    data = r.json()
    # Response shape: {"matches": [person, ...]} or {"status":"success","matches":[...]}
    return data.get("matches", []) or []


def merge_record(raw: dict, enriched: dict, domain: str) -> dict:
    """Combine search (obfuscated) + enrichment (full) into final row."""
    # enrichment has the full name + linkedin_url
    src = enriched if enriched else raw
    org = src.get("organization") or raw.get("organization") or {}
    return {
        "domain": domain,
        "organization_name": org.get("name")
        or raw.get("organization", {}).get("name", ""),
        "first_name": src.get("first_name", "") or raw.get("first_name", ""),
        "last_name": src.get("last_name", "") or raw.get("last_name_obfuscated", ""),
        "title": src.get("title", "") or raw.get("title", ""),
        "seniority": src.get("seniority", "") or raw.get("seniority", ""),
        "linkedin_url": src.get("linkedin_url", "") or "",
        "person_id": src.get("id", "") or raw.get("id", ""),
        "city": src.get("city", "") or raw.get("city", "") or "",
        "state": src.get("state", "") or raw.get("state", "") or "",
        "country": src.get("country", "") or raw.get("country", "") or "",
        "headline": src.get("headline", "") or "",
    }


def get_sheets_services():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)
    sheets = build("sheets", "v4", credentials=creds).spreadsheets()
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def find_existing_sheet(drive, title: str, folder_id: str) -> str | None:
    q = f"name = '{title}' and '{folder_id}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    resp = drive.files().list(q=q, fields="files(id,name)", pageSize=5).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upsert_sheet(sheets, drive, title: str, rows: list[dict], folder_id: str) -> str:
    headers = (
        list(rows[0].keys())
        if rows
        else [
            "domain",
            "organization_name",
            "first_name",
            "last_name",
            "title",
            "seniority",
            "linkedin_url",
            "person_id",
            "has_email",
            "city",
            "state",
            "country",
        ]
    )
    data = [headers] + [[str(r.get(h, "")) for h in headers] for r in rows]
    sid = find_existing_sheet(drive, title, folder_id)
    if sid:
        sheets.values().clear(spreadsheetId=sid, range="Sheet1!A:Z").execute()
        sheets.values().update(
            spreadsheetId=sid,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": data},
        ).execute()
        action = "UPDATED"
    else:
        ss = sheets.create(body={"properties": {"title": title}}).execute()
        sid = ss["spreadsheetId"]
        sheets.values().update(
            spreadsheetId=sid,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": data},
        ).execute()
        meta = drive.files().get(fileId=sid, fields="parents").execute()
        prev = ",".join(meta.get("parents", []))
        drive.files().update(
            fileId=sid, addParents=folder_id, removeParents=prev, fields="id"
        ).execute()
        action = "CREATED"
    return f"{action}: https://docs.google.com/spreadsheets/d/{sid}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True)
    ap.add_argument("--run-ids", required=True)
    ap.add_argument("--project-id", type=int, default=42)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--folder-id", default=LEADS_FOLDER_ID)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true", help="Print domains, skip Apollo")
    args = ap.parse_args()

    api_key = os.environ.get("APOLLO_API_KEY", "")
    if not api_key and not args.dry_run:
        print("ERROR: APOLLO_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    run_ids = [int(x) for x in args.run_ids.split(",")]
    print(
        f"Fetching domains: segment={args.segment} runs={run_ids} project={args.project_id}"
    )
    domains = fetch_domains(args.segment, run_ids, args.project_id)
    print(f"  Domains: {len(domains)}")

    if args.dry_run:
        print("\n".join(domains))
        return

    # Step 1: search per-domain (obfuscated results, but we know which domain they belong to)
    print("\nStep 1 — searching people per domain (/mixed_people/api_search)...")
    raw_by_id: dict[str, dict] = {}  # person_id -> {"raw": ..., "domain": ...}
    domains_with_hits = 0
    for i, domain in enumerate(domains, 1):
        people = apollo_search_one_domain(domain, api_key, per_page=100)
        if people:
            domains_with_hits += 1
        for p in people:
            pid = p.get("id")
            if pid and pid not in raw_by_id:
                raw_by_id[pid] = {"raw": p, "domain": domain}
        if i % 10 == 0 or i == len(domains):
            print(
                f"  {i}/{len(domains)} domains | {domains_with_hits} with hits | {len(raw_by_id)} unique people"
            )
        time.sleep(0.2)  # 200/min → pace at 300ms

    # Step 2: bulk_match to de-obfuscate (full name, linkedin_url, title)
    print(f"\nStep 2 — enriching {len(raw_by_id)} people via /people/bulk_match...")
    all_ids = list(raw_by_id.keys())
    enriched_by_id: dict[str, dict] = {}
    BATCH = 10  # Apollo bulk_match: max 10 per request
    for i in range(0, len(all_ids), BATCH):
        batch_ids = all_ids[i : i + BATCH]
        matches = apollo_bulk_match(batch_ids, api_key)
        for m in matches:
            mid = m.get("id")
            if mid:
                enriched_by_id[mid] = m
        print(f"  {min(i + BATCH, len(all_ids))}/{len(all_ids)} enriched")
        time.sleep(0.2)

    # Step 3: merge
    print("\nStep 3 — merging search + enrichment...")
    deduped = []
    for pid, entry in raw_by_id.items():
        enr = enriched_by_id.get(pid, {})
        deduped.append(merge_record(entry["raw"], enr, entry["domain"]))

    print(
        f"  Total people: {len(deduped)} (across {domains_with_hits}/{len(domains)} domains)"
    )
    with_linkedin = sum(1 for r in deduped if r.get("linkedin_url"))
    print(f"  With linkedin_url: {with_linkedin}/{len(deduped)}")

    # Sort: domain, then title
    deduped.sort(key=lambda r: (r.get("domain", ""), r.get("title", "")))

    # Sheet
    sheets, drive = get_sheets_services()
    title = f"OS | People | {args.segment} — {args.date}"
    print(f"\nWriting Sheet: {title}")
    result = upsert_sheet(sheets, drive, title, deduped, args.folder_id)
    print(f"  ✓ {result}")


if __name__ == "__main__":
    main()
