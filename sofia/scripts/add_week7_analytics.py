#!/usr/bin/env python3
"""
Add Week 7 [27/03 - 03/04] block to Project Analytics sheet.
Follows exact same structure as existing weeks.

Data from SmartLead weekly report (2026-04-03):
- IMAGENCY (IM-FIRST AGENCIES): 2938 sent, 26 replied, 1 meeting booked
- INFPLAT (INFLUENCER PLATFORMS + other): 1286 sent, 9 replied, 1 meeting booked
- Total: 4224 sent, 35 replied (0.83%), 2 meetings
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
TAB = "Project Analytics"


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def get_sheet_id(service, tab_name):
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == tab_name:
            return s["properties"]["sheetId"]
    return None


def main():
    service = get_service()
    sid = get_sheet_id(service, TAB)
    if not sid:
        print(f"ERROR: Tab '{TAB}' not found")
        return

    # ── Data ────────────────────────────────────────────────────────────────
    imagency_sent = 2938
    imagency_replied = 26
    imagency_meetings = 1   # Luciano Burattin (Meeting Booked)

    infplat_sent = 1286     # INFPLAT 789 + AFFPERF/INDIA/LATAM 497
    infplat_replied = 9
    infplat_meetings = 1    # Niloufer Dundh (Meeting Booked)

    total_sent = imagency_sent + infplat_sent       # 4224
    total_replied = imagency_replied + infplat_replied  # 35
    total_meetings = imagency_meetings + infplat_meetings  # 2

    reply_pct = f"{total_replied / total_sent * 100:.2f}%"
    meetings_pct = f"{total_meetings / total_replied * 100:.2f}%"

    # ── Rows to insert (10 rows + 1 empty separator = 11) ───────────────────
    # Matches exactly the format of existing weeks:
    # Row 1: Plan/Fact header
    # Row 2: Column headers
    # Row 3: LinkedIn — Marketing agencies
    # Row 4: LinkedIn — IM platforms & SaaS (contains week label)
    # Row 5: LinkedIn — Total
    # Row 6: Email section header
    # Row 7: Email — Marketing agencies
    # Row 8: Email — IM platforms & SaaS
    # Row 9: Email — Total
    # Row 10: empty separator

    new_rows = [
        # Row 1 — Plan/Fact header
        ['', '', '', '', 'Plan', 'Fact'],

        # Row 2 — Column headers
        ['DATE', 'Channel', 'Campaign launch date', 'Hypothesis',
         'Invites Sent', 'Invites Sent', 'Invites Accepted / %', '',
         'Reply / %', '', 'Meetings scheduled / %', '', 'Meetings held'],

        # Row 3 — LinkedIn: Marketing agencies (no LI data this week)
        ['', '', 'Feb 17', 'Marketing agencies',
         '', '', '', '', '', '', '', '', ''],

        # Row 4 — LinkedIn: IM platforms & SaaS (week label here)
        ['Week 7 [27/03 - 03/04]', 'Linkedin', '', 'IM platforms & SaaS',
         '', '', '', '', '', '', '', '', ''],

        # Row 5 — LinkedIn Total (all zeros — no LinkedIn activity tracked)
        ['', '', '', 'Total',
         '0', '0', '0', '0.00%', '0', '0.00%', '0', '0.00%', '0'],

        # Row 6 — Email section header
        ['', 'Email', '', 'Hypothesis',
         'Prospects Contacted', 'Prospects Contacted',
         'Reply / %', '', 'Meetings scheduled / %', '', 'Meetings held'],

        # Row 7 — Email: Marketing agencies (IMAGENCY)
        ['', '', 'Feb 17', 'Marketing agencies',
         '', str(imagency_sent), str(imagency_replied), '',
         str(imagency_meetings), '', str(imagency_meetings)],

        # Row 8 — Email: IM platforms & SaaS (INFPLAT + other)
        ['', '', '', 'IM platforms & SaaS',
         '', str(infplat_sent), str(infplat_replied), '',
         str(infplat_meetings), '', str(infplat_meetings)],

        # Row 9 — Email Total
        ['', '', '', 'Total',
         '', str(total_sent), str(total_replied), reply_pct,
         str(total_meetings), meetings_pct, str(total_meetings)],

        # Row 10 — empty separator
        [],
    ]

    # ── Insert 10 blank rows at the very top ─────────────────────────────────
    n = len(new_rows)
    print(f"Inserting {n} rows at top of '{TAB}'...")

    service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": sid,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": n,
                },
                "inheritFromBefore": False,
            }
        }]},
    ).execute()

    # ── Write data ────────────────────────────────────────────────────────────
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"{TAB}!A1",
        valueInputOption="RAW",
        body={"values": new_rows},
    ).execute()

    print("Done!")
    print()
    print(f"  Week 7 [27/03 - 03/04] added:")
    print(f"  Email — Marketing agencies:    {imagency_sent} sent, {imagency_replied} replied, {imagency_meetings} meeting")
    print(f"  Email — IM platforms & SaaS:   {infplat_sent} sent, {infplat_replied} replied, {infplat_meetings} meeting")
    print(f"  Email — Total:                 {total_sent} sent, {total_replied} replied ({reply_pct}), {total_meetings} meetings ({meetings_pct})")
    print()
    print(f"  Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid=343583930")


if __name__ == "__main__":
    main()
