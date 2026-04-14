#!/usr/bin/env python3.11
"""
Consolidate targets from a set of gathering runs into ONE Google Sheet per segment.

Pulls discovered_companies where is_target=true via SSH+docker psql, groups by
matched_segment, and creates/updates 4 sheets:
  OS | Targets | INFLUENCER_PLATFORMS — YYYY-MM-DD
  OS | Targets | IM_FIRST_AGENCIES — YYYY-MM-DD
  OS | Targets | AFFILIATE_PERFORMANCE — YYYY-MM-DD
  OS | Targets | SOCIAL_COMMERCE — YYYY-MM-DD

Anything with matched_segment LIKE 'NEW:%' goes to:
  OS | Targets | OTHER — YYYY-MM-DD

Idempotent: re-running overwrites existing sheets with same name.
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = Path("/Users/user/sales_engineer/.claude/mcp/google-sheets/token.json")
TARGETS_FOLDER_ID = "124SCStl6SHuMPquxyfj0Av5O8U4kNrTj"

SEGMENTS = [
    "AFFILIATE_PERFORMANCE",
    "SOCIAL_COMMERCE",
    "INFLUENCER_PLATFORMS",
    "IM_FIRST_AGENCIES",
]
HEADERS = ["domain", "name", "matched_segment", "confidence", "reasoning", "run_id"]


def fetch_targets(run_ids: list[int], project_id: int) -> list[dict]:
    run_list = ",".join(str(r) for r in run_ids)
    sql = f"""
        SELECT dc.domain,
               COALESCE(dc.name, ''),
               dc.matched_segment,
               dc.confidence,
               REPLACE(REPLACE(COALESCE(dc.reasoning, ''), '|', '/'), E'\\n', ' '),
               dc.latest_analysis_run_id
        FROM discovered_companies dc
        WHERE dc.project_id = {project_id}
          AND dc.is_target = true
          AND dc.domain = ANY(
              SELECT jsonb_array_elements_text(gr.filters->'domains')
              FROM gathering_runs gr WHERE gr.id IN ({run_list})
          )
        ORDER BY dc.matched_segment, dc.confidence DESC NULLS LAST
    """
    cmd = [
        "ssh",
        "hetzner",
        f"docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F'|' -c \"{sql.strip()}\"",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"psql failed: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    rows = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        rows.append(
            {
                "domain": parts[0].strip(),
                "name": parts[1].strip(),
                "matched_segment": parts[2].strip(),
                "confidence": parts[3].strip(),
                "reasoning": parts[4].strip(),
                "run_id": parts[5].strip(),
            }
        )
    return rows


def bucketize(rows: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {seg: [] for seg in SEGMENTS}
    buckets["OTHER"] = []
    for row in rows:
        seg = row["matched_segment"]
        if seg in SEGMENTS:
            buckets[seg].append(row)
        else:
            buckets["OTHER"].append(row)
    return buckets


def get_sheets_services():
    if not TOKEN_PATH.exists():
        print(f"Token not found at {TOKEN_PATH}", file=sys.stderr)
        sys.exit(1)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)
    sheets = build("sheets", "v4", credentials=creds).spreadsheets()
    drive = build("drive", "v3", credentials=creds)
    return sheets, drive


def find_existing_sheet(drive, title: str) -> str | None:
    """Look for an existing Sheet with this exact title in Targets folder."""
    q = f"name = '{title}' and '{TARGETS_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    resp = drive.files().list(q=q, fields="files(id,name)", pageSize=5).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upsert_sheet(sheets, drive, title: str, rows: list[dict]) -> str:
    data = [HEADERS] + [[str(r.get(h, "")) for h in HEADERS] for r in rows]
    sid = find_existing_sheet(drive, title)
    if sid:
        # Clear then rewrite
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
            fileId=sid, addParents=TARGETS_FOLDER_ID, removeParents=prev, fields="id"
        ).execute()
        action = "CREATED"
    url = f"https://docs.google.com/spreadsheets/d/{sid}"
    print(f"  ✓ {action}: {title} ({len(rows)} rows) → {url}")
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-ids",
        required=True,
        help="Comma-separated run IDs, e.g. 423,424,425,426,427,428",
    )
    ap.add_argument("--project-id", type=int, default=42)
    ap.add_argument(
        "--date", default=date.today().isoformat(), help="Date suffix YYYY-MM-DD"
    )
    args = ap.parse_args()

    run_ids = [int(x) for x in args.run_ids.split(",")]
    print(f"Fetching targets from runs {run_ids} (project {args.project_id})...")
    rows = fetch_targets(run_ids, args.project_id)
    print(f"  Total targets: {len(rows)}")

    buckets = bucketize(rows)
    for seg, items in buckets.items():
        print(f"  {seg}: {len(items)}")

    sheets, drive = get_sheets_services()
    print("\nUpserting Sheets...")
    for seg in SEGMENTS:
        title = f"OS | Targets | {seg} — {args.date}"
        upsert_sheet(sheets, drive, title, buckets[seg])
    if buckets["OTHER"]:
        title = f"OS | Targets | OTHER — {args.date}"
        upsert_sheet(sheets, drive, title, buckets["OTHER"])

    print("\nDone.")


if __name__ == "__main__":
    main()
