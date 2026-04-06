#!/usr/bin/env python3
"""
Fill Notes columns for pending leads with research info.
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

BOOKING_SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
BOOKING_TAB = "Leads booking_Sofia"

LEADS_NOTES = [
    {
        "row": 2,
        "name": "Sylvia Hysen",
        "notes_sally": "Co-founder & Publisher of Millennial Magazine. 20+ years in entertainment/digital media. Recommended by White House as top 100 digital media influencer.",
    },
    {
        "row": 3,
        "name": "Akhilesh Kumar",
        "notes_sally": "Senior Business Executive at DigiMag (Mumbai). Leads revenue/sales. 6+ years experience. Specialize in performance marketing, branding, social media, CGI/3D.",
    },
    {
        "row": 4,
        "name": "Niloufer Dundh",
        "notes_sally": "Founder & CEO of Ventes Avenues (Mobile AdTech). 30+ years in sales/marketing. Recently transitioned from operational role (early 2025).",
    },
    {
        "row": 5,
        "name": "Ricardo Giacoman Marcos",
        "notes_sally": "Colectivo Mas - Latin America focus. Limited public info found, requires further research.",
    },
]


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def read_header(service):
    """Read header row to find column indices."""
    result = service.spreadsheets().values().get(
        spreadsheetId=BOOKING_SHEET_ID,
        range=f"{BOOKING_TAB}!A1:Z1",
    ).execute()
    header = result.get("values", [[]])[0]
    return {h.strip(): i for i, h in enumerate(header)}


def update_cell(service, row, col_idx, value):
    """Update a single cell."""
    col_letter = chr(65 + col_idx)  # A=0, B=1, ...
    service.spreadsheets().values().update(
        spreadsheetId=BOOKING_SHEET_ID,
        range=f"{BOOKING_TAB}!{col_letter}{row}",
        valueInputOption="RAW",
        body={"values": [[value]]},
    ).execute()


def main():
    service = get_service()

    print("Reading header...")
    header = read_header(service)
    print(f"  Found {len(header)} columns\n")

    # Get column indices
    notes_col = "Notes (Sally)"
    if notes_col not in header:
        print(f"ERROR: Column '{notes_col}' not found")
        print(f"Available columns: {list(header.keys())}")
        return

    col_idx = header[notes_col]

    for lead in LEADS_NOTES:
        row = lead["row"]
        name = lead["name"]
        notes = lead.get("notes_sally", "")

        print(f"Row {row}: {name}")
        print(f"  Notes: {notes[:60]}...")

        update_cell(service, row, col_idx, notes)
        print(f"  ✓ Updated Notes (Sally)\n")

    print("Done!")
    print(f"\nSheet: https://docs.google.com/spreadsheets/d/{BOOKING_SHEET_ID}/edit?gid=1993663378")


if __name__ == "__main__":
    main()
