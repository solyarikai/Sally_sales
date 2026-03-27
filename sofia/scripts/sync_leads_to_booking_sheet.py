#!/usr/bin/env python3
"""
sync_leads_to_booking_sheet.py
Pulls replied leads from all OnSocial Smartlead campaigns
and adds new ones to the "Leads booking_Sofia" Google Sheet.

Usage:
    python3 sync_leads_to_booking_sheet.py
    python3 sync_leads_to_booking_sheet.py --dry-run   # preview without writing
    python3 sync_leads_to_booking_sheet.py --slack      # also send Slack notification
"""

import argparse
import json
import subprocess
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Config ──────────────────────────────────────────────────────────────────
SMARTLEAD_API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
GOOGLE_CREDS_PATH = "/Users/sofia/Documents/GitHub/Sally_sales/magnum-opus/google-credentials.json"
SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
SHEET_GID = 1993663378

SLACK_WEBHOOK_URL = ""   # Paste Slack webhook URL here (optional)

# Smartlead lead_category_id that means "replied / interested"
# 1 = Interested, others are also positive replies — adjust as needed
REPLY_CATEGORIES = None  # None = ALL categories (any reply), or e.g. {1, 5}

# Which campaign name patterns to include (case-insensitive, substring match)
CAMPAIGN_FILTER = "onsocial"

# Sheet column order (must match actual headers in row 1)
COLUMNS = [
    "",            # A — empty (row number / checkbox area)
    "Meeting Date",
    "Name",
    "Title",
    "Company",
    "Website",
    "Location",
    "Email",
    "LinkedIn",
    "Connection",
    "Channel",
    "Campaign",
    "Segment",
    "Status",
    "Qualification",
    "Notes (Sally)",
    "Notes (OnSocial)",
    "Closer",
    "Last Message",
    "Reply",
    "Last touch date",
    "Last touch by",
    "Сhecked",
]
# ────────────────────────────────────────────────────────────────────────────


def sl_get(path: str):
    """Call Smartlead API via rtk proxy curl."""
    url = f"https://server.smartlead.ai/api/v1/{path}"
    if "?" in url:
        url += f"&api_key={SMARTLEAD_API_KEY}"
    else:
        url += f"?api_key={SMARTLEAD_API_KEY}"

    result = subprocess.run(
        ["rtk", "proxy", "curl", "-s", url],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def get_all_campaigns() -> list[dict]:
    data = sl_get("campaigns")
    return data if isinstance(data, list) else []


def get_campaign_leads(campaign_id: int) -> list[dict]:
    """Paginate through all leads in a campaign."""
    leads = []
    offset = 0
    limit = 100
    while True:
        data = sl_get(f"campaigns/{campaign_id}/leads?limit={limit}&offset={offset}")
        page = data.get("data", [])
        if not page:
            break
        leads.extend(page)
        offset += limit
        if len(page) < limit:
            break
        time.sleep(0.25)
    return leads


def build_lead_row(lead_entry: dict, campaign_name: str) -> dict:
    """Map Smartlead lead → sheet columns."""
    l = lead_entry.get("lead", {})
    cf = l.get("custom_fields", {}) or {}

    first = (l.get("first_name") or "").strip()
    last = (l.get("last_name") or "").strip()
    name = f"{first} {last}".strip()

    title = (
        cf.get("Contact_Title") or cf.get("Job_title") or cf.get("job_title")
        or cf.get("title") or cf.get("Title") or ""
    )
    segment = cf.get("SEGMENT") or cf.get("Segment") or cf.get("segment") or ""
    location = (
        l.get("location") or cf.get("Person_location") or cf.get("Person_Location")
        or cf.get("Company_Location") or cf.get("companyLocation") or ""
    )

    return {
        "": "",
        "Meeting Date": "",
        "Name": name,
        "Title": title,
        "Company": l.get("company_name") or "",
        "Website": l.get("website") or "",
        "Location": location,
        "Email": l.get("email") or "",
        "LinkedIn": l.get("linkedin_profile") or cf.get("LinkedIn_URL") or cf.get("linkedin_url") or "",
        "Connection": "Pending",
        "Channel": "Email",
        "Campaign": campaign_name,
        "Segment": segment,
        "Status": "",
        "Qualification": "",
        "Notes (Sally)": "",
        "Notes (OnSocial)": "",
        "Closer": "",
        "Last Message": "",
        "Reply": "",
        "Last touch date": "",
        "Last touch by": "",
        "Сhecked": "",
    }


def row_to_values(row_dict: dict) -> list:
    return [row_dict.get(col, "") for col in COLUMNS]


def slack_notify(new_leads: list[dict], webhook_url: str):
    if not webhook_url:
        return
    lines = [f"*{len(new_leads)} new replied leads added to booking sheet*"]
    for l in new_leads[:10]:
        lines.append(f"• {l['Name']} — {l['Company']} ({l['Campaign']})")
    if len(new_leads) > 10:
        lines.append(f"_...and {len(new_leads) - 10} more_")
    payload = json.dumps({"text": "\n".join(lines)})
    subprocess.run(
        ["curl", "-s", "-X", "POST", "-H", "Content-type: application/json",
         "--data", payload, webhook_url],
        capture_output=True
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--slack", action="store_true", help="Send Slack notification")
    args = parser.parse_args()

    import gspread
    from google.oauth2.service_account import Credentials

    # ── Connect to Google Sheet ──────────────────────────────────────────────
    print("Connecting to Google Sheet...")
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.get_worksheet_by_id(SHEET_GID)

    existing_rows = ws.get_all_values()
    # Collect existing emails (col H = index 7)
    existing_emails = set()
    for row in existing_rows[1:]:  # skip header
        if len(row) > 7 and row[7].strip():
            existing_emails.add(row[7].strip().lower())
    print(f"  {len(existing_emails)} existing emails in sheet")

    # ── Fetch Smartlead campaigns ────────────────────────────────────────────
    print("\nFetching Smartlead campaigns...")
    all_campaigns = get_all_campaigns()
    onsocial_campaigns = [
        c for c in all_campaigns
        if CAMPAIGN_FILTER.lower() in c.get("name", "").lower()
        and c.get("status") not in ("ARCHIVED", "DRAFTED")
    ]
    print(f"  Found {len(onsocial_campaigns)} OnSocial campaigns")

    # ── Collect replied leads ────────────────────────────────────────────────
    new_leads = []
    seen_emails = set(existing_emails)

    for camp in onsocial_campaigns:
        camp_id = camp["id"]
        camp_name = camp["name"]
        print(f"\n  [{camp.get('status')}] {camp_name} (ID {camp_id})")

        leads = get_campaign_leads(camp_id)
        replied = [
            l for l in leads
            if l.get("lead_category_id") is not None
            and (REPLY_CATEGORIES is None or l["lead_category_id"] in REPLY_CATEGORIES)
        ]
        print(f"    {len(leads)} total leads, {len(replied)} replied")

        for entry in replied:
            email = (entry.get("lead", {}).get("email") or "").strip().lower()
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)
            row = build_lead_row(entry, camp_name)
            new_leads.append(row)

    # ── Write to sheet ───────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"New leads to add: {len(new_leads)}")

    if not new_leads:
        print("Nothing to add. All replied leads already in sheet.")
        return

    # Preview
    for l in new_leads:
        print(f"  + {l['Name']} | {l['Company']} | {l['Email']} | {l['Campaign']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    # Find the PENDING section row to insert after
    pending_row_idx = None
    for i, row in enumerate(existing_rows):
        if row and row[1].strip().upper() == "PENDING":
            pending_row_idx = i + 2  # 1-indexed, insert after PENDING header row
            break

    if pending_row_idx is None:
        # No PENDING section found, append at end
        pending_row_idx = len(existing_rows) + 1

    print(f"\nInserting {len(new_leads)} rows at row {pending_row_idx}...")

    rows_to_insert = [row_to_values(l) for l in new_leads]
    ws.insert_rows(rows_to_insert, row=pending_row_idx)
    print(f"✓ Added {len(new_leads)} leads to the sheet")

    if args.slack and SLACK_WEBHOOK_URL:
        slack_notify(new_leads, SLACK_WEBHOOK_URL)
        print("✓ Slack notification sent")

    print(f"\nDone at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
