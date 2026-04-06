#!/usr/bin/env python3
"""
SmartLead Weekly — Format to CSV + Google Sheets
=================================================
Reads weekly JSON report, creates:
  1. Campaign summary table
  2. All replies table
Saves both locally (CSV) and to Google Sheets.

Run: ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_weekly_format.py"
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ─────────────────────────────────────────────────────────────────
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
REPORT_PATH = f"sofia/reports/smartlead_weekly_{TODAY}.json"
TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = f"OS | Analytics | SmartLead Weekly — {TODAY}"

# Local output
LOCAL_SUMMARY = f"sofia/reports/OS_Analytics_SmartLead_Weekly_{TODAY}_summary.csv"
LOCAL_REPLIES = f"sofia/reports/OS_Analytics_SmartLead_Weekly_{TODAY}_replies.csv"


# ── Google Sheets auth ──────────────────────────────────────────────────────
def get_sheets_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def create_spreadsheet(service, title):
    result = service.spreadsheets().create(body={"properties": {"title": title}}).execute()
    return result["spreadsheetId"]


def write_sheet(service, sheet_id, range_, values):
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def format_header(service, sheet_id, sheet_name, num_cols):
    """Bold + background for header row."""
    # Get sheet id by name
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sid = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == sheet_name)
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": num_cols},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }},
            {"autoResizeDimensions": {
                "dimensions": {"sheetId": sid, "dimension": "COLUMNS",
                               "startIndex": 0, "endIndex": num_cols}
            }},
        ]},
    ).execute()


# ── Load report ─────────────────────────────────────────────────────────────
def load_report():
    with open(REPORT_PATH) as f:
        return json.load(f)


# ── Build tables ─────────────────────────────────────────────────────────────
def build_summary_table(report):
    header = ["Campaign", "Status", "Sent", "Opened", "Replied", "Reply%", "Bounced", "Unsubscribed"]
    rows = [header]

    totals = report["totals"]
    sent_total = totals.get("sent", 0)

    for cr in report["campaigns"]:
        m = cr["metrics"]
        sent = m["sent"]
        replied = m["replied"]
        r_pct = f"{replied/sent*100:.1f}%" if sent > 0 else "—"
        rows.append([
            cr["name"],
            cr["status"],
            sent,
            m["opened"],
            replied,
            r_pct,
            m["bounced"],
            m["unsubscribed"],
        ])

    # Totals row
    r_pct_total = f"{totals['replied']/sent_total*100:.1f}%" if sent_total > 0 else "—"
    rows.append([
        "TOTAL", "",
        totals["sent"], totals["opened"], totals["replied"],
        r_pct_total, totals["bounced"], totals["unsubscribed"],
    ])
    return rows


def build_replies_table(report):
    header = ["Reply Time", "Category", "Name", "Email", "Campaign", "Subject"]
    rows = [header]

    for cr in report["campaigns"]:
        camp_name = cr["name"]
        for r in cr.get("replied_leads", []):
            # Format reply time nicely
            rt = r.get("reply_time", "")
            try:
                dt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
                rt_fmt = dt.strftime("%b %d %H:%M UTC")
            except Exception:
                rt_fmt = rt

            rows.append([
                rt_fmt,
                r.get("category", ""),
                r.get("name", ""),
                r.get("email", ""),
                camp_name,
                r.get("subject", ""),
            ])

    # Sort by reply time desc (skip header)
    rows[1:] = sorted(rows[1:], key=lambda x: x[0], reverse=True)
    return rows


# ── CSV save ─────────────────────────────────────────────────────────────────
def save_csv(path, rows):
    import csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"  CSV saved: {path}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Loading report: {REPORT_PATH}")
    report = load_report()

    summary_rows = build_summary_table(report)
    replies_rows = build_replies_table(report)

    # Print summary
    print()
    print("=" * 80)
    print(f"  CAMPAIGN SUMMARY — {report['period']}")
    print("=" * 80)
    fmt = "{:<50} {:>8} {:>8} {:>8} {:>6}"
    print(fmt.format("Campaign", "Sent", "Replied", "Reply%", "Bounce"))
    print("-" * 80)
    for row in summary_rows[1:]:
        name = str(row[0])[:49]
        print(fmt.format(name, row[2], row[4], row[5], row[6]))

    print()
    print("=" * 80)
    print(f"  ALL REPLIES ({len(replies_rows)-1} total)")
    print("=" * 80)
    for row in replies_rows[1:]:
        cat = str(row[1]).strip() or "?"
        print(f"  {row[0]:<20}  [{cat:>16}]  {row[2]:<30}  {row[3]}")
        print(f"  {'':20}   {'Subject:':>16}   {row[5]}")
        print()

    # Save CSVs
    save_csv(LOCAL_SUMMARY, summary_rows)
    save_csv(LOCAL_REPLIES, replies_rows)

    # Google Sheets
    print(f"\nCreating Google Sheet: {SPREADSHEET_NAME}")
    service = get_sheets_service()
    sheet_id = create_spreadsheet(service, SPREADSHEET_NAME)
    print(f"  Sheet ID: {sheet_id}")

    # Rename Sheet1 → Summary, add Replies sheet
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    first_sid = meta["sheets"][0]["properties"]["sheetId"]

    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [
            {"updateSheetProperties": {
                "properties": {"sheetId": first_sid, "title": "Summary"},
                "fields": "title",
            }},
            {"addSheet": {"properties": {"title": "Replies"}}},
        ]},
    ).execute()

    write_sheet(service, sheet_id, "Summary!A1", summary_rows)
    write_sheet(service, sheet_id, "Replies!A1", replies_rows)

    format_header(service, sheet_id, "Summary", len(summary_rows[0]))
    format_header(service, sheet_id, "Replies", len(replies_rows[0]))

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    print(f"\n  Google Sheet: {url}")
    print("  Done!")


if __name__ == "__main__":
    main()
