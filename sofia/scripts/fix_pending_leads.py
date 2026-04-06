#!/usr/bin/env python3
"""
Fix pending leads data — find actual rows by email, fill correct rows.
"""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

BOOKING_SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
BOOKING_TAB = "Leads booking_Sofia"

LEADS_DATA = {
    "sylvia@milmagz.com": {
        "name": "Sylvia Hysen",
        "title": "Co-founder & Publisher",
        "company": "Millennial Magazine",
        "website": "millennialmagazine.com",
        "location": "Los Angeles, USA",
        "linkedin": "https://www.linkedin.com/in/sylviahysen/",
        "notes_sally": "Co-founder & Publisher of Millennial Magazine. 20+ years in entertainment/digital media. Recommended by White House as top 100 digital media influencer.",
    },
    "akhilesh@digimag.co.in": {
        "name": "Akhilesh Kumar",
        "title": "Senior Business Executive",
        "company": "DigiMag",
        "website": "digimag.co.in",
        "location": "Mumbai, India",
        "linkedin": "https://www.linkedin.com/in/akhileshktd/",
        "notes_sally": "Senior Business Executive at DigiMag (Mumbai). Leads revenue/sales. 6+ years experience. Specialize in performance marketing, branding, social media, CGI/3D.",
    },
    "nilouferdundh@ventesavenues.in": {
        "name": "Niloufer Dundh",
        "title": "Founder & CEO (former)",
        "company": "Ventes Avenues",
        "website": "ventesavenues.in",
        "location": "India",
        "linkedin": "https://www.linkedin.com/in/niloufer-dundh-53980313/",
        "notes_sally": "Founder & CEO of Ventes Avenues (Mobile AdTech). 30+ years in sales/marketing. Recently transitioned from operational role (early 2025).",
    },
    "ricardo@colectivomas.com": {
        "name": "Ricardo Giacoman Marcos",
        "title": "",
        "company": "Colectivo Mas",
        "website": "colectivomas.com",
        "location": "Latin America",
        "linkedin": "",
        "notes_sally": "Colectivo Mas - Latin America focus. Limited public info found.",
    },
}

FIELD_TO_COL = {
    "title": "Title",
    "company": "Company",
    "website": "Website",
    "location": "Location",
    "linkedin": "LinkedIn",
    "notes_sally": "Notes (Sally)",
}


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def main():
    service = get_service()

    # Read full sheet
    result = service.spreadsheets().values().get(
        spreadsheetId=BOOKING_SHEET_ID,
        range=f"{BOOKING_TAB}!A1:Z200",
    ).execute()
    rows = result.get("values", [])

    header = [h.strip() for h in rows[0]]
    col_map = {h: i for i, h in enumerate(header)}

    # Find email column
    email_col = col_map.get("Email")
    if email_col is None:
        print("ERROR: Email column not found")
        return

    print(f"Header: {header}\n")

    # Clear bad data from rows 2-5 (where we wrongly wrote earlier)
    print("Clearing wrongly filled rows 2-5...")
    for field, col_name in FIELD_TO_COL.items():
        if col_name in col_map:
            col_idx = col_map[col_name]
            col_letter = chr(65 + col_idx)
            service.spreadsheets().values().clear(
                spreadsheetId=BOOKING_SHEET_ID,
                range=f"{BOOKING_TAB}!{col_letter}2:{col_letter}5",
            ).execute()
    print("  Done clearing.\n")

    # Find actual row numbers for each lead by email
    for row_idx, row in enumerate(rows[1:], start=2):
        if email_col >= len(row):
            continue
        email = row[email_col].strip().lower()
        if email not in LEADS_DATA:
            continue

        data = LEADS_DATA[email]
        print(f"Row {row_idx}: {data['name']} <{email}>")

        updates = []
        for field, col_name in FIELD_TO_COL.items():
            if col_name not in col_map:
                print(f"  ⚠️  Column '{col_name}' not found")
                continue
            col_idx = col_map[col_name]
            col_letter = chr(65 + col_idx)
            value = data.get(field, "")
            updates.append({
                "range": f"{BOOKING_TAB}!{col_letter}{row_idx}",
                "values": [[value]],
            })
            print(f"  ✓ {col_name} = {value[:50]}")

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=BOOKING_SHEET_ID,
                body={"valueInputOption": "RAW", "data": updates},
            ).execute()
        print()

    print("All done!")
    print(f"\nSheet: https://docs.google.com/spreadsheets/d/{BOOKING_SHEET_ID}/edit?gid=1993663378")


if __name__ == "__main__":
    main()
