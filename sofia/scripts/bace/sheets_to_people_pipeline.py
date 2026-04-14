#!/usr/bin/env python3.11
"""
Sheets → People pipeline (no Hetzner/Postgres needed).

Reads target company domains from one or more Google Sheets,
deduplicates, runs Apollo free people search, Exa LinkedIn enrichment,
FindyMail email enrichment, and writes two output sheets:
  - OS | People | {SEGMENT} — {DATE}          (all contacts, LinkedIn only)
  - OS | People | {SEGMENT} with email — {DATE} (contacts with email only)

Usage:
  python3.11 sheets_to_people_pipeline.py \\
      --segment IMAGENCY \\
      --sheet-ids "SHEET_ID_1,SHEET_ID_2" \\
      --folder-id "TARGET_FOLDER_ID" \\
      [--skip-findymail] [--dry-run]

API keys from env (loaded from .mcp.json automatically if run via this script):
  APOLLO_API_KEY, EXA_API_KEY, FINDYMAIL_API_KEY
"""

import argparse
import json
import os
import re
import socket
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Global socket timeout to prevent hanging on Google API calls
socket.setdefaulttimeout(60)

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN_PATH = Path("/Users/user/sales_engineer/.claude/mcp/google-sheets/token.json")
MCP_JSON_PATH = Path("/Users/user/sales_engineer/.mcp.json")
DEFAULT_FOLDER_ID = "1BiNXztkKf5HVDglf37rnse0b60z6ytBL"  # 20/04 - 15/05

APOLLO_BASE = "https://api.apollo.io/api/v1"
EXA_BASE = "https://api.exa.ai"
FINDYMAIL_BASE = "https://app.findymail.com"
LINKEDIN_RE = re.compile(r"https?://(?:[\w]+\.)?linkedin\.com/in/([\w\-]+)", re.I)

# v4 universal people filter
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def load_keys_from_mcp():
    """Load API keys from .mcp.json into os.environ if not already set."""
    if not MCP_JSON_PATH.exists():
        return
    try:
        d = json.loads(MCP_JSON_PATH.read_text())
        for server_cfg in d.get("mcpServers", {}).values():
            for k, v in server_cfg.get("env", {}).items():
                if k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"  warn: could not load .mcp.json: {e}", file=sys.stderr)


def get_services():
    creds = Credentials.from_authorized_user_file(
        str(TOKEN_PATH),
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    sheets = build("sheets", "v4", credentials=creds).spreadsheets()
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def read_sheet_domains(sheets, sheet_id: str) -> list[str]:
    """Read all non-empty domains from column A (skip header)."""
    data = (
        sheets.values()
        .get(spreadsheetId=sheet_id, range="Sheet1!A:A")
        .execute()
        .get("values", [])
    )
    if len(data) < 2:
        return []
    return [row[0].strip().lower() for row in data[1:] if row and row[0].strip()]


# ── Apollo ────────────────────────────────────────────────────────────────────


def apollo_search_domain(domain: str, api_key: str) -> list[dict]:
    """Search people at one domain using free /mixed_people/api_search endpoint."""
    all_people = []
    page = 1
    while page <= 5:
        payload = {
            "page": page,
            "per_page": 100,
            "q_organization_domains_list": [domain],
            "person_titles": V4_TITLES,
            "person_seniorities": V4_SENIORITIES,
            "include_similar_titles": True,
        }
        try:
            r = httpx.post(
                f"{APOLLO_BASE}/mixed_people/api_search",
                headers={
                    "X-Api-Key": api_key,
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                },
                json=payload,
                timeout=60,
            )
        except Exception as e:
            print(f"  apollo error for {domain}: {e}", file=sys.stderr)
            break
        if r.status_code == 429:
            print("  apollo rate limit, sleeping 10s...", file=sys.stderr)
            time.sleep(10)
            continue
        if r.status_code != 200:
            print(
                f"  apollo HTTP {r.status_code} for {domain}: {r.text[:200]}",
                file=sys.stderr,
            )
            break
        data = r.json()
        people = data.get("people", [])
        all_people.extend(people)
        if len(people) < 100:
            break
        page += 1
        time.sleep(0.3)
    return all_people


def person_to_row(p: dict, domain: str, segment: str) -> dict:
    org = p.get("organization") or {}
    return {
        "domain": domain,
        "organization_name": org.get("name", ""),
        "first_name": p.get("first_name", ""),
        "last_name": p.get("last_name") or p.get("last_name_obfuscated", ""),
        "title": p.get("title", ""),
        "seniority": p.get("seniority", ""),
        "linkedin_url": p.get("linkedin_url") or "",
        "email": "",
        "city": p.get("city") or "",
        "country": p.get("country") or "",
        "segment": segment,
        "person_id": p.get("id", ""),
    }


# ── Exa LinkedIn ──────────────────────────────────────────────────────────────


def exa_find_linkedin(
    first_name: str, title: str, org: str, domain: str, api_key: str
) -> str | None:
    query = f"{first_name} {title} {org}".strip()
    if domain:
        query += f" {domain}"
    try:
        r = httpx.post(
            f"{EXA_BASE}/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "category": "people",
                "includeDomains": ["linkedin.com"],
                "numResults": 3,
                "type": "neural",
            },
            timeout=30,
        )
        if r.status_code != 200:
            return None
        for res in r.json().get("results", []):
            url = res.get("url", "")
            m = LINKEDIN_RE.search(url)
            if m:
                author = (res.get("author") or "").lower()
                if not author or first_name.lower() in author:
                    return f"https://www.linkedin.com/in/{m.group(1)}"
    except Exception as e:
        print(f"  exa error: {e}", file=sys.stderr)
    return None


# ── FindyMail ─────────────────────────────────────────────────────────────────


def findymail_by_linkedin(linkedin_url: str, api_key: str) -> str:
    try:
        r = httpx.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"linkedin_url": linkedin_url},
            timeout=30,
        )
        if r.status_code == 200:
            d = r.json()
            return d.get("email") or (d.get("contact") or {}).get("email", "")
        if r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return ""
    except RuntimeError:
        raise
    except Exception:
        return ""


def findymail_by_name_domain(
    first_name: str, last_name: str, domain: str, api_key: str
) -> str:
    """Fallback: search by name + domain when no LinkedIn."""
    if not first_name or not domain:
        return ""
    try:
        r = httpx.post(
            f"{FINDYMAIL_BASE}/api/search/name",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"name": f"{first_name} {last_name}".strip(), "domain": domain},
            timeout=30,
        )
        if r.status_code == 200:
            d = r.json()
            return d.get("email") or (d.get("contact") or {}).get("email", "")
        if r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return ""
    except RuntimeError:
        raise
    except Exception:
        return ""


# ── Sheets output ─────────────────────────────────────────────────────────────

HEADERS_ALL = [
    "domain",
    "organization_name",
    "first_name",
    "last_name",
    "title",
    "seniority",
    "linkedin_url",
    "email",
    "city",
    "country",
    "segment",
]


def find_sheet(drive, title: str, folder_id: str) -> str | None:
    q = (
        f"name = '{title}' and '{folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    )
    files = (
        drive.files()
        .list(q=q, fields="files(id)", pageSize=5)
        .execute()
        .get("files", [])
    )
    return files[0]["id"] if files else None


def write_or_create_sheet(
    sheets, drive, title: str, rows: list[dict], folder_id: str
) -> str:
    data = [HEADERS_ALL] + [[str(r.get(h, "")) for h in HEADERS_ALL] for r in rows]
    sid = find_sheet(drive, title, folder_id)
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


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    load_keys_from_mcp()

    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True, help="e.g. IMAGENCY")
    ap.add_argument(
        "--sheet-ids", required=True, help="Comma-separated source sheet IDs"
    )
    ap.add_argument("--folder-id", default=DEFAULT_FOLDER_ID, help="Output folder ID")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--skip-exa", action="store_true", help="Skip Exa LinkedIn lookup")
    ap.add_argument(
        "--skip-findymail", action="store_true", help="Skip FindyMail enrichment"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Print domains only, no API calls"
    )
    ap.add_argument(
        "--cache-file",
        default="",
        help="Path to JSON cache file (save/resume progress)",
    )
    ap.add_argument(
        "--from-step",
        default="apollo",
        choices=["apollo", "exa", "findymail", "sheets"],
        help="Resume from step (requires --cache-file)",
    )
    args = ap.parse_args()

    apollo_key = os.environ.get("APOLLO_API_KEY", "")
    exa_key = os.environ.get("EXA_API_KEY", "")
    fm_key = os.environ.get("FINDYMAIL_API_KEY", "")

    if not apollo_key and not args.dry_run:
        sys.exit("ERROR: APOLLO_API_KEY not set")
    if not exa_key and not args.skip_exa and not args.dry_run:
        sys.exit("ERROR: EXA_API_KEY not set")

    sheet_ids = [s.strip() for s in args.sheet_ids.split(",") if s.strip()]

    # ── Step 1: Read & dedup domains ─────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"Segment: {args.segment} | Date: {args.date}")
    print(f"Source sheets: {len(sheet_ids)}")

    sheets_svc, drive_svc = get_services()
    all_domains: set[str] = set()
    for sid in sheet_ids:
        domains = read_sheet_domains(sheets_svc, sid)
        print(f"  Sheet {sid[:20]}...: {len(domains)} domains")
        all_domains.update(domains)

    domains_list = sorted(all_domains)
    print(f"\nUnique domains after dedup: {len(domains_list)}")

    if args.dry_run:
        print("\n".join(domains_list))
        return

    # ── Step 2: Apollo People Search ─────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("Step 2 — Apollo /mixed_people/api_search (free endpoint)...")
    all_rows: list[dict] = []
    seen_person_ids: set[str] = set()
    domains_with_hits = 0

    for i, domain in enumerate(domains_list, 1):
        people = apollo_search_domain(domain, apollo_key)
        new_for_domain = 0
        for p in people:
            pid = p.get("id", "")
            if pid and pid in seen_person_ids:
                continue
            if pid:
                seen_person_ids.add(pid)
            row = person_to_row(p, domain, args.segment)
            all_rows.append(row)
            new_for_domain += 1
        if new_for_domain > 0:
            domains_with_hits += 1
        if i % 20 == 0 or i == len(domains_list):
            print(
                f"  {i}/{len(domains_list)} domains | {domains_with_hits} with hits | {len(all_rows)} people"
            )
        time.sleep(0.25)

    print(
        f"\nApollo done: {len(all_rows)} people from {domains_with_hits}/{len(domains_list)} domains"
    )

    if not all_rows:
        print("No people found. Exiting.")
        return

    # ── Step 3: Exa → LinkedIn URL ────────────────────────────────────────────
    if not args.skip_exa:
        print(f"\n{'─' * 60}")
        without_li = [r for r in all_rows if not r.get("linkedin_url")]
        print(
            f"Step 3 — Exa LinkedIn lookup for {len(without_li)} people without LinkedIn..."
        )
        li_found = 0
        for i, r in enumerate(without_li, 1):
            li = exa_find_linkedin(
                r.get("first_name", ""),
                r.get("title", ""),
                r.get("organization_name", "") or r.get("domain", ""),
                r.get("domain", ""),
                exa_key,
            )
            if li:
                r["linkedin_url"] = li
                li_found += 1
            if i % 25 == 0 or i == len(without_li):
                print(
                    f"  Exa: {i}/{len(without_li)} | {li_found} found (~${li_found * 0.007:.2f})"
                )
            time.sleep(0.2)
        print(f"Exa done: {li_found}/{len(without_li)} LinkedIn URLs found")
    else:
        print("\nSkipping Exa (--skip-exa)")

    # ── Step 4: FindyMail → email ─────────────────────────────────────────────
    if not args.skip_findymail:
        if not fm_key:
            print("\nWARN: FINDYMAIL_API_KEY not set, skipping email enrichment")
        else:
            print(f"\n{'─' * 60}")
            to_enrich = [r for r in all_rows if not r.get("email")]
            print(f"Step 4 — FindyMail for {len(to_enrich)} people...")
            fm_found = 0
            out_of_credits = False
            for i, r in enumerate(to_enrich, 1):
                if out_of_credits:
                    break
                try:
                    if r.get("linkedin_url"):
                        email = findymail_by_linkedin(r["linkedin_url"], fm_key)
                    else:
                        email = findymail_by_name_domain(
                            r.get("first_name", ""),
                            r.get("last_name", ""),
                            r.get("domain", ""),
                            fm_key,
                        )
                    if email:
                        r["email"] = email
                        fm_found += 1
                except RuntimeError:
                    print(
                        f"\n  OUT OF FINDYMAIL CREDITS at {i}/{len(to_enrich)}",
                        file=sys.stderr,
                    )
                    out_of_credits = True
                    break
                if i % 25 == 0 or i == len(to_enrich):
                    print(
                        f"  FindyMail: {i}/{len(to_enrich)} | {fm_found} emails (~${fm_found * 0.01:.2f})"
                    )
                time.sleep(0.15)
            print(f"FindyMail done: {fm_found}/{len(to_enrich)} emails found")
    else:
        print("\nSkipping FindyMail (--skip-findymail)")

    # ── Step 5: Write output sheets ───────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("Step 5 — Writing output sheets...")

    # All people (LinkedIn only + with email) sorted by domain
    all_sorted = sorted(
        all_rows, key=lambda r: (r.get("domain", ""), r.get("title", ""))
    )

    # Sheet 1: LinkedIn only (no email)
    li_only = [r for r in all_sorted if r.get("linkedin_url") and not r.get("email")]
    title_li = f"OS | People | {args.segment} LinkedIn only — {args.date}"
    if li_only:
        res = write_or_create_sheet(
            sheets_svc, drive_svc, title_li, li_only, args.folder_id
        )
        print(f"  LinkedIn only ({len(li_only)} rows): {res}")
    else:
        print("  LinkedIn only: 0 rows, skipping")

    # Sheet 2: with email
    with_email = [r for r in all_sorted if r.get("email")]
    title_email = f"OS | People | {args.segment} with email — {args.date}"
    if with_email:
        res = write_or_create_sheet(
            sheets_svc, drive_svc, title_email, with_email, args.folder_id
        )
        print(f"  With email ({len(with_email)} rows): {res}")
    else:
        print("  With email: 0 rows, skipping")

    # Summary
    total_with_li = sum(1 for r in all_rows if r.get("linkedin_url"))
    total_with_email = sum(1 for r in all_rows if r.get("email"))
    print(f"\n{'=' * 60}")
    print(f"DONE — {args.segment}")
    print(f"  Domains processed:  {len(domains_list)}")
    print(f"  Total people:       {len(all_rows)}")
    print(
        f"  With LinkedIn:      {total_with_li} ({total_with_li * 100 // max(len(all_rows), 1)}%)"
    )
    print(
        f"  With email:         {total_with_email} ({total_with_email * 100 // max(len(all_rows), 1)}%)"
    )


if __name__ == "__main__":
    main()
