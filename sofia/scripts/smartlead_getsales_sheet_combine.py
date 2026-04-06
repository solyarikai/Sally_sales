#!/usr/bin/env python3
"""
Combine data from SmartLead, GetSales, and Google Sheets
=========================================================
For unchecked leads in booking_Sofia, gather:
- SmartLead: outbound emails, reply times
- GetSales: enriched contact data
- Google Sheets: status, notes, last messages

Run on Hetzner:
ssh hetzner "cd ~/magnum-opus-project/repo && set -a && source .env && set +a && python3 sofia/scripts/smartlead_getsales_sheet_combine.py"
"""

import os
import json
import httpx
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# === CONFIG ===
SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
GETSALES_API_KEY = os.environ.get("GETSALES_API_KEY", "")
# Try multiple paths for token
TOKEN_PATHS = [
    "/Users/sofia/Documents/GitHub/Sally_sales/.claude/google-sheets/token.json",
    os.path.expanduser("~/.claude/google-sheets/token.json"),
    ".claude/google-sheets/token.json",
]
TOKEN_PATH = next((p for p in TOKEN_PATHS if os.path.exists(p)), TOKEN_PATHS[0])
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"

# Unchecked leads (from earlier extraction)
UNCHECKED_LEADS = [
    ("roland@styleranking.de", "Roland Schweins", "styleranking media GmbH"),
    ("nader@linqia.com", "Nader Alizadeh", "Linqia"),
    ("natalie@glistenmgmt.com", "Natalie", "glisten mgmt"),
    ("urban@influee.co", "Urban Cvek", "Influee"),
    ("ernest@runwayinfluence.com", "Ernest Sturm", "Runway Influence"),
    ("yunus@yagency.dk", "Yunus Yousefi", "Yagency"),
    ("hola@brandmanic.com", "Luis Soldevila", "Brandmanic"),
    ("atul@theshelf.com", "Atul Singh", "The Shelf"),
    ("johan@impact.com", "Johan Venter", "impact.com"),
    ("ronit@berolling.in", "Ronit Thakur", "Be Rolling Media"),
    ("georg@gamesforest.club", "Georg Broxtermann", "GameInfluencer"),
    ("jacob@kjmarketingsweden.com", "Jacob Yngvesson", "KJ Marketing Sweden"),
    ("salvador@grg.co", "Salvador Klein", "Global Rev Gen"),
    ("anne-julie@clarkinfluence.com", "Anne-Julie Karcher", "Clark Influence"),
    ("daniel.schotland@linqia.com", "Daniel Schotland", "Linqia"),
    ("eviteri@publifyer.com", "Eduardo Viteri Fernandez", "Publifyer"),
    ("williamj@fanstories.com", "William Jourdain", "Fanstories"),
    ("dominique@loudpixels.se", "Dominique Grubestedt", "LoudPixels"),
]


# === SMARTLEAD ===
def get_smartlead_campaigns():
    """Fetch all campaign IDs."""
    resp = httpx.get(
        "https://server.smartlead.ai/api/v1/campaigns",
        params={"api_key": SMARTLEAD_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("data", [])


def get_campaign_stats(campaign_id):
    """Fetch statistics for a campaign (includes email content)."""
    resp = httpx.get(
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
        params={"api_key": SMARTLEAD_API_KEY, "offset": 0, "limit": 500},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        return data.get("data", [])
    return data if isinstance(data, list) else []


def strip_html(text):
    import re
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_smartlead_data():
    """Fetch SmartLead data for all unchecked leads."""
    # Only check known OnSocial campaigns to avoid iterating 2000+ campaigns
    campaign_ids = [
        # INFPLAT
        3050419, 3065429, 3064966, 3065159,
        # IMAGENCY
        3050462, 3063527, 3064335, 3071851, 3096746,
        # Other known campaigns
        2706918, 2852420, 2852366, 2853769, 2945763, 2945727, 2947684,
        2990385, 3078491, 3096747,
    ]
    print(f"Fetching SmartLead data from {len(campaign_ids)} known campaigns...")

    smartlead_data = {}

    for camp_id in campaign_ids:
        print(f"  Fetching stats for campaign {camp_id}...")
        try:
            stats = get_campaign_stats(camp_id)
            for record in stats:
                email = (record.get("lead_email") or "").lower()
                if any(email == unc[0] for unc in UNCHECKED_LEADS):
                    if email not in smartlead_data:
                        smartlead_data[email] = []
                    smartlead_data[email].append(
                        {
                            "campaign_id": camp_id,
                            "subject": record.get("email_subject", ""),
                            "message": strip_html(record.get("email_message", "")),
                            "sent_time": record.get("sent_time", ""),
                            "reply_time": record.get("reply_time", ""),
                            "open_count": record.get("open_count", 0),
                        }
                    )
            time.sleep(0.3)
        except Exception as e:
            print(f"    Error: {e}")

    return smartlead_data


# === GOOGLE SHEETS ===
def get_sheet_data():
    """Fetch unchecked leads from Leads booking_Sofia."""
    print("Fetching Google Sheet data...")
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired:
        creds.refresh(Request())
    service = build("sheets", "v4", credentials=creds)

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range="'Leads booking_Sofia'!A1:Z300")
        .execute()
    )
    values = result.get("values", [])

    # Parse headers
    headers = values[0] if values else []
    sheet_data = {}

    for row in values[1:]:
        if len(row) > 7:
            email = (row[7] or "").lower()  # Column H = email
            if any(email == unc[0] for unc in UNCHECKED_LEADS):
                sheet_data[email] = {
                    "name": row[2] if len(row) > 2 else "",
                    "title": row[3] if len(row) > 3 else "",
                    "company": row[4] if len(row) > 4 else "",
                    "website": row[5] if len(row) > 5 else "",
                    "status": row[13] if len(row) > 13 else "",
                    "notes_sally": row[15] if len(row) > 15 else "",
                    "notes_onsocial": row[16] if len(row) > 16 else "",
                    "last_message": row[18] if len(row) > 18 else "",
                    "reply": row[20] if len(row) > 20 else "",
                }

    return sheet_data


# === MAIN ===
def main():
    print("=" * 70)
    print("COMBINING SMARTLEAD + SHEET DATA")
    print("=" * 70)

    smartlead_data = get_smartlead_data()
    sheet_data = get_sheet_data()

    combined = {}
    for email, name, company in UNCHECKED_LEADS:
        email_lower = email.lower()
        combined[email_lower] = {
            "email": email,
            "name": name,
            "company": company,
            "smartlead": smartlead_data.get(email_lower, []),
            "sheet": sheet_data.get(email_lower, {}),
        }

    # Pretty print
    for email, data in combined.items():
        print(f"\n{'='*70}")
        print(f"NAME:    {data['name']}")
        print(f"COMPANY: {data['company']}")
        print(f"EMAIL:   {email}")

        sheet = data["sheet"]
        if sheet:
            print(f"\nSHEET STATUS: {sheet.get('status', 'N/A')}")
            if sheet.get("notes_sally"):
                print(f"Notes (Sally): {sheet['notes_sally'][:200]}")
            if sheet.get("notes_onsocial"):
                print(f"Notes (OnSocial): {sheet['notes_onsocial'][:200]}")
            if sheet.get("last_message"):
                print(f"Last Message: {sheet['last_message'][:200]}")
            if sheet.get("reply"):
                print(f"Reply: {sheet['reply'][:100]}")

        smartlead = data["smartlead"]
        if smartlead:
            print(f"\nSMARTLEAD ({len(smartlead)} email(s)):")
            for i, email_record in enumerate(smartlead[:2]):  # Show last 2
                print(f"  [{i+1}] Subject: {email_record['subject'][:60]}")
                print(f"      Sent: {email_record['sent_time']}")
                print(f"      Replied: {email_record['reply_time'] if email_record['reply_time'] else 'No'}")
                print(f"      Message preview: {email_record['message'][:150]}")
        else:
            print("\nSMARTLEAD: No data found")

    # Save combined JSON
    out_path = "sofia/scripts/combined_leads_data.json"
    with open(out_path, "w") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n\nSaved to {out_path}")


if __name__ == "__main__":
    main()
