#!/usr/bin/env python3.11
"""
Exa LinkedIn enricher for people without linkedin_url.
Reads People Sheet → searches LinkedIn via Exa → updates sheet with linkedin_url.
Then runs FindyMail on found linkedin URLs.

Usage:
  EXA_API_KEY=... FINDYMAIL_API_KEY=... python3.11 exa_linkedin_enricher.py \
      --sheet-id <SHEET_ID> --segment AFFPERF
"""

import argparse
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = Path("/Users/user/sales_engineer/.claude/mcp/google-sheets/token.json")
LEADS_FOLDER_ID = "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe"
EXA_BASE = "https://api.exa.ai"
FINDYMAIL_BASE = "https://app.findymail.com"

LINKEDIN_RE = re.compile(r"https?://(?:[\w]+\.)?linkedin\.com/in/([\w\-]+)", re.I)


def get_services():
    creds = Credentials.from_authorized_user_file(
        str(TOKEN_PATH),
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return (
        build("sheets", "v4", credentials=creds).spreadsheets(),
        build("drive", "v3", credentials=creds),
    )


def read_sheet(svc, sheet_id: str) -> tuple[list[str], list[dict]]:
    data = (
        svc.values()
        .get(spreadsheetId=sheet_id, range="Sheet1!A:Z")
        .execute()
        .get("values", [])
    )
    if not data:
        return [], []
    headers = data[0]
    rows = [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in data[1:]]
    return headers, rows


def write_sheet(svc, sheet_id: str, headers: list[str], rows: list[dict]):
    data = [headers] + [[str(r.get(h, "")) for h in headers] for r in rows]
    svc.values().clear(spreadsheetId=sheet_id, range="Sheet1!A:Z").execute()
    svc.values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": data},
    ).execute()


def exa_search_linkedin(
    first_name: str, title: str, org: str, domain: str, api_key: str
) -> str | None:
    """Search Exa for LinkedIn URL. Returns linkedin.com/in/... or None."""
    query = f"{first_name} {title} {org}".strip()
    if domain:
        query += f" {domain}"
    payload = {
        "query": query,
        "category": "people",
        "includeDomains": ["linkedin.com"],
        "numResults": 3,
        "type": "neural",
    }
    try:
        r = httpx.post(
            f"{EXA_BASE}/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        for res in results:
            url = res.get("url", "")
            m = LINKEDIN_RE.search(url)
            if m:
                # Quick sanity: author name should contain first_name
                author = (res.get("author") or "").lower()
                if first_name.lower() in author or not author:
                    return f"https://www.linkedin.com/in/{m.group(1)}"
        return None
    except Exception as e:
        print(f"  exa error: {e}", file=sys.stderr)
        return None


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
            contact = d.get("contact") or {}
            return d.get("email") or contact.get("email") or ""
        if r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return ""
    except RuntimeError:
        raise
    except Exception:
        return ""


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


def upsert_leads_sheet(
    sheets, drive, title: str, rows: list[dict], folder_id: str
) -> str:
    headers = [
        "domain",
        "organization_name",
        "first_name",
        "last_name",
        "email",
        "title",
        "seniority",
        "linkedin_url",
        "city",
        "state",
        "country",
    ]
    data = [headers] + [[str(r.get(h, "")) for h in headers] for r in rows]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--segment", required=True)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--folder-id", default=LEADS_FOLDER_ID)
    ap.add_argument(
        "--skip-findymail",
        action="store_true",
        help="Only find LinkedIn, skip FindyMail",
    )
    args = ap.parse_args()

    exa_key = os.environ.get("EXA_API_KEY", "")
    fm_key = os.environ.get("FINDYMAIL_API_KEY", "")
    if not exa_key:
        print("ERROR: EXA_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not fm_key and not args.skip_findymail:
        print(
            "ERROR: FINDYMAIL_API_KEY not set (or use --skip-findymail)",
            file=sys.stderr,
        )
        sys.exit(1)

    sheets, drive = get_services()
    headers, rows = read_sheet(sheets, args.sheet_id)
    print(f"Loaded {len(rows)} rows from sheet")

    # Ensure linkedin_url and email columns exist
    if "linkedin_url" not in headers:
        headers.append("linkedin_url")
    if "email" not in headers:
        headers.append("email")

    targets = [
        r
        for r in rows
        if r.get("first_name") and r.get("domain") and not r.get("linkedin_url")
    ]
    print(f"  {len(targets)} without linkedin_url (will search via Exa)")

    # Step 1: Exa → LinkedIn URL
    li_found = 0
    for i, r in enumerate(targets, 1):
        li = exa_search_linkedin(
            r.get("first_name", ""),
            r.get("title", ""),
            r.get("organization_name", "") or r.get("domain", ""),
            r.get("domain", ""),
            exa_key,
        )
        if li:
            r["linkedin_url"] = li
            li_found += 1
        if i % 10 == 0 or i == len(targets):
            print(f"  Exa: {i}/{len(targets)} searched | {li_found} LinkedIn found")
        time.sleep(0.2)

    print(
        f"\nExa done: {li_found}/{len(targets)} LinkedIn URLs found (~${li_found * 0.007:.2f})"
    )

    # Save linkedin_url back to sheet
    write_sheet(sheets, args.sheet_id, headers, rows)
    print("  ✓ LinkedIn URLs saved to source sheet")

    if args.skip_findymail:
        print("Skipping FindyMail (--skip-findymail).")
        return

    # Step 2: FindyMail by linkedin_url for newly found + existing ones without email
    to_enrich = [r for r in rows if r.get("linkedin_url") and not r.get("email")]
    print(f"\nFindyMail: {len(to_enrich)} with linkedin_url but no email...")
    fm_found = 0
    for i, r in enumerate(to_enrich, 1):
        email = findymail_by_linkedin(r["linkedin_url"], fm_key)
        if email:
            r["email"] = email
            fm_found += 1
        if i % 10 == 0 or i == len(to_enrich):
            print(f"  FindyMail: {i}/{len(to_enrich)} | {fm_found} emails found")
        time.sleep(0.1)

    print(
        f"\nFindyMail done: {fm_found}/{len(to_enrich)} emails found (~${fm_found * 0.01:.2f})"
    )

    # Save emails back to sheet
    write_sheet(sheets, args.sheet_id, headers, rows)
    print("  ✓ Emails saved to source sheet")

    # Create/update Leads sheet with people that have email
    leads = [r for r in rows if r.get("email")]
    leads.sort(key=lambda r: (r.get("domain", ""), r.get("title", "")))
    if leads:
        leads_title = f"OS | Leads | {args.segment} — {args.date}"
        print(f"\nWriting Leads sheet: {leads_title} ({len(leads)} rows)")
        res = upsert_leads_sheet(sheets, drive, leads_title, leads, args.folder_id)
        print(f"  ✓ {res}")
    else:
        print("\nNo leads with email found.")

    print(f"\nDone. Total cost estimate: ~${(li_found * 0.007 + fm_found * 0.01):.2f}")


if __name__ == "__main__":
    main()
