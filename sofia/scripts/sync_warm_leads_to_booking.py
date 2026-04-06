#!/usr/bin/env python3
"""
Sync warm leads from SmartLead weekly report → Leads booking_Sofia sheet.

Reads warm leads (Interested / Meeting Booked / Meeting Request / Positive Reply)
from the Replies tab of the weekly analytics sheet, checks if they're already in
the booking sheet (by email), and adds missing ones to the TOP as "pending".

Run locally:
  python3 sofia/scripts/sync_warm_leads_to_booking.py
"""

import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Source: SmartLead Weekly Replies tab
WEEKLY_SHEET_ID = "1KROy8xUYJym8osIQ-11LZL2o7oUInYnYRGbK66_CNQU"
WEEKLY_TAB = "Replies"

# Destination: OnSocial <> Sally — Leads booking_Sofia
BOOKING_SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
BOOKING_TAB = "Leads booking_Sofia"

WARM_CATEGORIES = {
    "interested",
    "meeting booked",
    "meeting request",
    "positive reply",
}


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def read_sheet(service, sheet_id, tab, range_="A1:Z2000"):
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!{range_}",
    ).execute()
    return result.get("values", [])


def main():
    service = get_service()

    # ── Read Replies tab ─────────────────────────────────────────────────────
    print("Reading SmartLead weekly Replies tab...")
    replies_data = read_sheet(service, WEEKLY_SHEET_ID, WEEKLY_TAB)
    if not replies_data:
        print("  No data in Replies tab.")
        return

    # Header: Reply Time | Category | Name | Email | Campaign | Subject | Reply Text
    header = [h.strip() for h in replies_data[0]]
    print(f"  Columns: {header}")

    try:
        col_cat   = header.index("Category")
        col_name  = header.index("Name")
        col_email = header.index("Email")
        col_camp  = header.index("Campaign")
        col_subj  = header.index("Subject")
        col_reply = header.index("Reply Text") if "Reply Text" in header else None
        col_time  = header.index("Reply Time")
    except ValueError as e:
        print(f"  Column not found: {e}")
        return

    warm_leads = []
    for row in replies_data[1:]:
        def cell(i):
            return row[i].strip() if i is not None and i < len(row) else ""

        category = cell(col_cat).lower()
        if category not in WARM_CATEGORIES:
            continue

        warm_leads.append({
            "reply_time": cell(col_time),
            "category":   cell(col_cat),
            "name":       cell(col_name),
            "email":      cell(col_email).lower(),
            "campaign":   cell(col_camp),
            "subject":    cell(col_subj),
            "reply_text": cell(col_reply) if col_reply is not None else "",
        })

    print(f"  Found {len(warm_leads)} warm leads: {[l['name'] for l in warm_leads]}")

    # ── Read booking sheet ───────────────────────────────────────────────────
    print(f"\nReading booking sheet ({BOOKING_TAB})...")
    booking_data = read_sheet(service, BOOKING_SHEET_ID, BOOKING_TAB)

    if not booking_data:
        booking_header = []
        booking_emails = set()
    else:
        booking_header = [h.strip() for h in booking_data[0]]
        print(f"  Columns: {booking_header}")

        # Find email column — try common names
        email_col_idx = None
        for candidate in ("Email", "email", "E-mail", "EMAIL"):
            if candidate in booking_header:
                email_col_idx = booking_header.index(candidate)
                break

        if email_col_idx is None:
            # Try column index 3 as fallback (common position)
            print("  ⚠️  No 'Email' column found — showing header to debug:")
            print(f"     {booking_header}")
            email_col_idx = None

        booking_emails = set()
        if email_col_idx is not None:
            for row in booking_data[1:]:
                if email_col_idx < len(row):
                    booking_emails.add(row[email_col_idx].strip().lower())

    print(f"  {len(booking_emails)} leads already in booking sheet")

    # ── Find missing leads ───────────────────────────────────────────────────
    missing = [l for l in warm_leads if l["email"] not in booking_emails]
    already = [l for l in warm_leads if l["email"] in booking_emails]

    print(f"\n  Already in booking sheet ({len(already)}):")
    for l in already:
        print(f"    ✓  [{l['category']:>16}]  {l['name']} <{l['email']}>")

    print(f"\n  Missing — will add as PENDING ({len(missing)}):")
    for l in missing:
        print(f"    →  [{l['category']:>16}]  {l['name']} <{l['email']}>")

    if not missing:
        print("\n  Nothing to add. All warm leads are already in the booking sheet.")
        return

    # ── Build rows to insert ─────────────────────────────────────────────────
    # We'll prepend rows after the header.
    # Match booking sheet columns as best we can.
    # Common columns: Status | Name | Email | Company | Campaign | Reply | Notes | Date
    # We'll insert with Status = "PENDING", fill what we know.

    if not booking_header:
        # Create simple header
        booking_header = ["Status", "Name", "Email", "Campaign", "Subject", "Reply", "Reply Time", "Category"]
        # Write header first
        service.spreadsheets().values().update(
            spreadsheetId=BOOKING_SHEET_ID,
            range=f"{BOOKING_TAB}!A1",
            valueInputOption="RAW",
            body={"values": [booking_header]},
        ).execute()

    def make_row(lead):
        """Map lead fields onto booking sheet columns."""
        row = [""] * max(len(booking_header), 8)
        for i, col in enumerate(booking_header):
            col_l = col.lower()
            if "status" in col_l:
                row[i] = "PENDING"
            elif col_l in ("name", "full name", "contact"):
                row[i] = lead["name"]
            elif "email" in col_l:
                row[i] = lead["email"]
            elif "campaign" in col_l:
                row[i] = lead["campaign"]
            elif "subject" in col_l:
                row[i] = lead["subject"]
            elif "reply" in col_l and "time" not in col_l and "date" not in col_l:
                row[i] = lead["reply_text"]
            elif "time" in col_l or "date" in col_l:
                row[i] = lead["reply_time"]
            elif "categor" in col_l or "type" in col_l:
                row[i] = lead["category"]
        return row

    new_rows = [make_row(l) for l in missing]

    # Insert at row 2 (after header) — shift existing rows down
    # Use insertDimension + update approach:
    # 1. Insert N blank rows after row 1
    # 2. Write data into those rows

    # Get sheet metadata to find sheetId
    meta = service.spreadsheets().get(spreadsheetId=BOOKING_SHEET_ID).execute()
    booking_sid = None
    for s in meta["sheets"]:
        if s["properties"]["title"] == BOOKING_TAB:
            booking_sid = s["properties"]["sheetId"]
            break

    if booking_sid is None:
        print(f"  ERROR: Tab '{BOOKING_TAB}' not found in booking spreadsheet")
        return

    n = len(new_rows)
    print(f"\nInserting {n} row(s) at top of '{BOOKING_TAB}'...")

    # Insert blank rows
    service.spreadsheets().batchUpdate(
        spreadsheetId=BOOKING_SHEET_ID,
        body={"requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": booking_sid,
                    "dimension": "ROWS",
                    "startIndex": 1,   # after header (row index 0)
                    "endIndex": 1 + n,
                },
                "inheritFromBefore": False,
            }
        }]},
    ).execute()

    # Write data
    service.spreadsheets().values().update(
        spreadsheetId=BOOKING_SHEET_ID,
        range=f"{BOOKING_TAB}!A2",
        valueInputOption="RAW",
        body={"values": new_rows},
    ).execute()

    print("  Done!")
    print(f"\nAdded {n} pending lead(s) to the top of Leads booking_Sofia:")
    for l in missing:
        print(f"  → [{l['category']:>16}]  {l['name']}  {l['email']}")

    print(f"\n  Booking sheet: https://docs.google.com/spreadsheets/d/{BOOKING_SHEET_ID}")


if __name__ == "__main__":
    main()
