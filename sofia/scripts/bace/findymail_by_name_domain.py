#!/usr/bin/env python3.11
"""
FindyMail enrichment when linkedin_url is unavailable.
Reads a People Sheet → searches email by first_name + domain → writes updated Sheet + separate Leads Sheet.

Usage:
  FINDYMAIL_API_KEY=... python3.11 findymail_by_name_domain.py \
      --sheet-id <SHEET_ID> --segment AFFPERF
"""

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = Path("/Users/user/sales_engineer/.claude/mcp/google-sheets/token.json")
LEADS_FOLDER_ID = "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe"
FINDYMAIL_BASE = "https://app.findymail.com"


def read_sheet(svc, sheet_id: str) -> list[dict]:
    data = (
        svc.values()
        .get(spreadsheetId=sheet_id, range="Sheet1!A:Z")
        .execute()
        .get("values", [])
    )
    if not data:
        return []
    headers = data[0]
    return [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in data[1:]]


def findymail_search(first_name: str, domain: str, api_key: str) -> dict:
    try:
        r = httpx.post(
            f"{FINDYMAIL_BASE}/api/search/name",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"name": first_name, "domain": domain},
            timeout=30,
        )
        if r.status_code == 200:
            d = r.json()
            contact = d.get("contact") or {}
            return {
                "email": contact.get("email") or "",
                "linkedin_url": contact.get("linkedin_url") or "",
                "job_title": contact.get("job_title") or "",
            }
        if r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": "", "linkedin_url": "", "job_title": ""}
    except RuntimeError:
        raise
    except Exception as e:
        print(f"  err {e}", file=sys.stderr)
        return {"email": "", "linkedin_url": "", "job_title": ""}


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


def find_sheet(drive, title: str, folder_id: str) -> str | None:
    q = (
        f"name = '{title}' and '{folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    )
    resp = drive.files().list(q=q, fields="files(id,name)", pageSize=5).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upsert_sheet(
    sheets, drive, title: str, headers: list[str], rows: list[dict], folder_id: str
) -> str:
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
    ap.add_argument(
        "--sheet-id", required=True, help="People Sheet ID with first_name + domain"
    )
    ap.add_argument("--segment", required=True, help="e.g. AFFPERF, INFPLAT, IMAGENCY")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--folder-id", default=LEADS_FOLDER_ID)
    args = ap.parse_args()

    api_key = os.environ.get("FINDYMAIL_API_KEY", "")
    if not api_key:
        print("ERROR: FINDYMAIL_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    sheets, drive = get_services()

    print(f"Reading source sheet {args.sheet_id}...")
    rows = read_sheet(sheets, args.sheet_id)
    print(f"  {len(rows)} rows")

    targets = [
        r
        for r in rows
        if r.get("first_name", "").strip() and r.get("domain", "").strip()
    ]
    print(f"  {len(targets)} with first_name + domain")

    print("\nQuerying FindyMail /api/search/name...")
    found = 0
    for i, r in enumerate(targets, 1):
        first = r["first_name"].strip()
        domain = r["domain"].strip()
        result = findymail_search(first, domain, api_key)
        r["email"] = result["email"]
        if result["linkedin_url"] and not r.get("linkedin_url"):
            r["linkedin_url"] = result["linkedin_url"]
        if result["email"]:
            found += 1
        if i % 10 == 0 or i == len(targets):
            print(f"  {i}/{len(targets)} searched | {found} found")
        time.sleep(0.1)

    print(f"\nFound: {found}/{len(targets)} (${found * 0.01:.2f} est.)")

    # Write back to source People sheet (updated with emails)
    src_headers = list(targets[0].keys()) if targets else []
    if "email" not in src_headers:
        src_headers.append("email")
    print("\nUpdating source People sheet with emails...")
    sheets.values().clear(spreadsheetId=args.sheet_id, range="Sheet1!A:Z").execute()
    data = [src_headers] + [[str(r.get(h, "")) for h in src_headers] for r in rows]
    sheets.values().update(
        spreadsheetId=args.sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": data},
    ).execute()
    print(f"  ✓ https://docs.google.com/spreadsheets/d/{args.sheet_id}")

    # Create separate Leads sheet with only people that have email
    leads = [r for r in targets if r.get("email")]
    leads.sort(key=lambda r: (r.get("domain", ""), r.get("title", "")))
    if leads:
        leads_title = f"OS | Leads | {args.segment} — {args.date}"
        leads_headers = [
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
        print(f"\nWriting Leads sheet: {leads_title}")
        res = upsert_sheet(
            sheets, drive, leads_title, leads_headers, leads, args.folder_id
        )
        print(f"  ✓ {res}")

    print("\nDone.")


if __name__ == "__main__":
    main()
