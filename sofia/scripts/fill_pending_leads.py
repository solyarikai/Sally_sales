#!/usr/bin/env python3
"""
Fill missing fields for pending leads in Leads booking_Sofia sheet.
Rows 10-13 contain the new warm leads — add Title, Company, Website, LinkedIn.
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

BOOKING_SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
BOOKING_TAB = "Leads booking_Sofia"

# Row data [rows 10-13 (A2:A5 after insert, but let's check)]
# Row 2: Sylvia Hysen
# Row 3: Akhilesh Kumar
# Row 4: Niloufer Dundh
# Row 5: Ricardo Giacoman Marcos

LEADS_TO_FILL = [
    {
        "row": 2,
        "name": "Sylvia Hysen",
        "email": "sylvia@milmagz.com",
        "title": "Co-founder & Publisher",
        "company": "Millennial Magazine",
        "website": "millennialmagazine.com",
        "location": "Los Angeles, USA",
        "linkedin": "https://www.linkedin.com/in/sylviahysen/",
    },
    {
        "row": 3,
        "name": "Akhilesh Kumar",
        "email": "akhilesh@digimag.co.in",
        "title": "Senior Business Executive",
        "company": "DigiMag",
        "website": "digimag.co.in",
        "location": "Mumbai, India",
        "linkedin": "https://www.linkedin.com/in/akhileshktd/",
    },
    {
        "row": 4,
        "name": "Niloufer Dundh",
        "email": "nilouferdundh@ventesavenues.in",
        "title": "Founder & CEO (former)",
        "company": "Ventes Avenues",
        "website": "ventesavenues.in",
        "location": "India",
        "linkedin": "https://www.linkedin.com/in/niloufer-dundh-53980313/",
    },
    {
        "row": 5,
        "name": "Ricardo Giacoman Marcos",
        "email": "ricardo@colectivomas.com",
        "title": "—",
        "company": "Colectivo Mas",
        "website": "colectivomas.com",
        "location": "Latin America",
        "linkedin": "—",
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
    print(f"  Columns found: {list(header.keys())}\n")

    # Map our fields to sheet columns
    field_map = {
        "title": "Title",
        "company": "Company",
        "website": "Website",
        "location": "Location",
        "linkedin": "LinkedIn",
    }

    for lead in LEADS_TO_FILL:
        row = lead["row"]
        print(f"Row {row}: {lead['name']} <{lead['email']}>")

        for field, col_name in field_map.items():
            if col_name not in header:
                print(f"  ⚠️  Column '{col_name}' not found, skipping")
                continue

            col_idx = header[col_name]
            value = lead.get(field, "")

            update_cell(service, row, col_idx, value)
            print(f"  ✓ {col_name}: {value}")

        print()

    print("Done! All pending leads updated.")
    print(f"\nSheet: https://docs.google.com/spreadsheets/d/{BOOKING_SHEET_ID}/edit?gid=1993663378")


if __name__ == "__main__":
    main()
