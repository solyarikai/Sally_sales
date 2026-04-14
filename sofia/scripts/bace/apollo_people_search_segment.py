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


def apollo_search(
    domains: list[str],
    api_key: str,
    page: int = 1,
    per_page: int = 100,
) -> dict:
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    payload = {
        "page": page,
        "per_page": per_page,
        "q_organization_domains_list": domains,
        "person_titles": V4_TITLES,
        "person_seniorities": V4_SENIORITIES,
        "include_similar_titles": True,
    }
    r = httpx.post(
        f"{APOLLO_BASE}/mixed_people/api_search",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text[:400]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def normalize_person(p: dict) -> dict:
    org = p.get("organization") or {}
    return {
        "domain": (org.get("primary_domain") or org.get("website_url") or "")
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/"),
        "organization_name": org.get("name", ""),
        "first_name": p.get("first_name", ""),
        "last_name": p.get("last_name_obfuscated", "") or p.get("last_name", ""),
        "title": p.get("title", ""),
        "seniority": p.get("seniority", ""),
        "linkedin_url": p.get("linkedin_url", "") or "",
        "person_id": p.get("id", ""),
        "has_email": p.get("has_email"),
        "city": p.get("city", "") or "",
        "state": p.get("state", "") or "",
        "country": p.get("country", "") or "",
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

    print("\nQuerying Apollo /mixed_people/api_search...")
    all_people = []
    page = 1
    while page <= args.max_pages:
        data = apollo_search(domains, api_key, page=page, per_page=100)
        people = data.get("people", [])
        total = data.get("total_entries", 0)
        pagination = data.get("pagination", {}) or {}
        total_pages = pagination.get("total_pages", 1)
        print(
            f"  page {page}/{total_pages} | returned {len(people)} | total_entries {total}"
        )
        all_people.extend(normalize_person(p) for p in people)
        if page >= total_pages or not people:
            break
        page += 1
        time.sleep(0.5)  # gentle on rate limit

    # Deduplicate by person_id
    seen = set()
    deduped = []
    for p in all_people:
        pid = p.get("person_id")
        if pid and pid in seen:
            continue
        seen.add(pid)
        deduped.append(p)
    print(f"\n  Total people: {len(deduped)} (across {len(domains)} domains)")

    # Coverage stats
    matched_domains = {p["domain"] for p in deduped if p.get("domain")}
    print(f"  Domains with people: {len(matched_domains)}/{len(domains)}")

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
