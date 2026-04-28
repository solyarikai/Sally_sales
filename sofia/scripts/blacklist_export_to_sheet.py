#!/usr/bin/env python3
"""
project_blacklist (DB) -> Google Sheets mirror.

Writes a read-only mirror of the leadgen `project_blacklist` table to a
dedicated tab in the OS | Ops | Blacklist spreadsheet (or any spreadsheet
provided via --spreadsheet-id). The mirror tab is fully overwritten on
each run; manually-curated tabs in the same spreadsheet are never touched.

Tab name (default): "Mirror — project_blacklist (auto)"
  - Created on first run if it doesn't exist.
  - Cleared and re-filled on every subsequent run.
  - Header row is written explicitly; comment in cell A1 of the sheet
    metadata explains it's auto-generated.

Schema written to the tab:
  Domain | Source | Reason | Created At | Project ID

Auth:
  Reuses the same OAuth user-token pattern as
  magnum-opus/scripts/sofia/bace/pipeline.py:_get_gsheets_creds().
  Searches token.json in:
    ~/.claude/google-sheets/token.json
    <repo>/.claude/mcp/google-sheets/token.json
    ~/magnum-opus-project/repo/sofia/.google-sheets/token.json
    <repo>/sofia/.google-sheets/token.json

Run locations:
  - Local (dev):  python3 sofia/scripts/blacklist_export_to_sheet.py --dry-run
  - Hetzner:      python3 scripts/sofia/blacklist_export_to_sheet.py
                  (cron after blacklist_sync_smartlead.py at 03:30 UTC)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Built-in project registry — mirrors blacklist_sync_smartlead.py.
PROJECT_REGISTRY: dict[str, int] = {
    "onsocial": 42,
}

# OS | Ops | Blacklist spreadsheet (canonical destination for OnSocial).
DEFAULT_SPREADSHEET_ID = "1drDBlOBr_BEeYd0Fv5292IbAfdTApLgITOht6PZHCU4"
DEFAULT_TAB_NAME = "Mirror — project_blacklist (auto)"

SCRIPT_DIR = Path(__file__).resolve().parent
SOFIA_DIR = SCRIPT_DIR.parent
REPO_ROOT = SOFIA_DIR.parent

HEADERS = ["Domain", "Source", "Reason", "Created At", "Project ID"]


def _get_gsheets_creds() -> Path | None:
    for path in [
        Path.home() / ".claude/google-sheets/token.json",
        REPO_ROOT / ".claude/mcp/google-sheets/token.json",
        Path.home() / "magnum-opus-project/repo/sofia/.google-sheets/token.json",
        SOFIA_DIR / ".google-sheets" / "token.json",
    ]:
        if path.exists():
            return path
    return None


def fetch_blacklist_rows(project_id: int) -> list[list[str]]:
    """Read project_blacklist via docker exec. Hetzner-only."""
    sql = (
        "SELECT domain, COALESCE(source,''), COALESCE(reason,''), "
        "to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'), "
        "project_id "
        f"FROM project_blacklist WHERE project_id = {project_id} "
        "ORDER BY created_at DESC NULLS LAST, domain ASC;"
    )
    cmd = [
        "docker",
        "exec",
        "leadgen-postgres",
        "psql",
        "-U",
        "leadgen",
        "-d",
        "leadgen",
        "-tA",
        "-F",
        "\t",
        "-c",
        sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"psql read failed: {result.stderr.strip()[:200]}")
    rows: list[list[str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        # Pad short rows defensively.
        while len(parts) < 5:
            parts.append("")
        rows.append(parts[:5])
    return rows


def ensure_tab(sheets_svc, spreadsheet_id: str, tab_name: str) -> int:
    """Return the sheetId for tab_name, creating the tab if missing."""
    meta = sheets_svc.get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == tab_name:
            return props.get("sheetId")

    response = sheets_svc.batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
    ).execute()
    return response["replies"][0]["addSheet"]["properties"]["sheetId"]


def overwrite_tab(
    sheets_svc, spreadsheet_id: str, tab_name: str, rows: list[list[str]]
) -> None:
    """Clear the tab and write headers + rows."""
    sheets_svc.values().clear(
        spreadsheetId=spreadsheet_id, range=f"'{tab_name}'!A:Z", body={}
    ).execute()
    values = [HEADERS] + rows
    sheets_svc.values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default="onsocial",
        help=f"Project name. Known: {', '.join(sorted(PROJECT_REGISTRY))}.",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help="Override project_id directly (skips --project lookup).",
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=DEFAULT_SPREADSHEET_ID,
        help=f"Target Google Sheets ID. Default: {DEFAULT_SPREADSHEET_ID} (OS | Ops | Blacklist).",
    )
    parser.add_argument(
        "--tab",
        default=DEFAULT_TAB_NAME,
        help=f"Destination tab name. Default: {DEFAULT_TAB_NAME!r}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary, do not write to Sheets.",
    )
    args = parser.parse_args()

    if args.project_id is not None:
        project_id = args.project_id
        project_label = f"id={project_id}"
    else:
        name = args.project.lower()
        if name not in PROJECT_REGISTRY:
            known = ", ".join(sorted(PROJECT_REGISTRY))
            raise SystemExit(f"Unknown --project {name!r}. Known: {known}.")
        project_id = PROJECT_REGISTRY[name]
        project_label = name

    print(f"Project: {project_label} (project_id={project_id})")
    print(f"Spreadsheet: {args.spreadsheet_id}")
    print(f"Tab:         {args.tab!r}")

    rows = fetch_blacklist_rows(project_id)
    print(f"Rows fetched from project_blacklist: {len(rows)}")

    if args.dry_run:
        for row in rows[:5]:
            print(f"  sample: {row}")
        if len(rows) > 5:
            print(f"  ... and {len(rows) - 5} more")
        print("Dry run — nothing written.")
        return 0

    token_path = _get_gsheets_creds()
    if not token_path:
        raise SystemExit(
            "Google Sheets token.json not found in any known path. "
            "Place it at ~/.claude/google-sheets/token.json (or other known location)."
        )

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SystemExit(
            f"Missing dependency: {exc}. Install with: pip install google-auth google-api-python-client"
        )

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    sheets_svc = build("sheets", "v4", credentials=creds).spreadsheets()

    ensure_tab(sheets_svc, args.spreadsheet_id, args.tab)
    overwrite_tab(sheets_svc, args.spreadsheet_id, args.tab, rows)
    print(f"Wrote {len(rows)} rows to '{args.tab}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
