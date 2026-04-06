#!/usr/bin/env python3
"""
Fetch exact values from "Leads booking_Sofia" Google Sheet.
Outputs JSON with all leads.
"""

import json
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.api_python_client import discovery

TOKEN_PATH = Path("/Users/sofia/Documents/GitHub/Sally_sales/.claude/google-sheets/token.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Sheet ID for "OnSocial <> Sally"
SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"

# Sheet name
SHEET_NAME = "Leads booking_Sofia"

def get_sheets_service():
    """Authenticate and return Google Sheets service."""
    creds = None
    
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    # Refresh if needed
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            print(f"Token refresh failed: {e}", file=sys.stderr)
            return None
    
    if not creds:
        print("ERROR: No valid credentials found at", TOKEN_PATH, file=sys.stderr)
        return None
    
    return discovery.build('sheets', 'v4', credentials=creds)

def fetch_leads():
    """Fetch all rows from Leads booking_Sofia sheet."""
    service = get_sheets_service()
    if not service:
        return None
    
    try:
        # Fetch all data from the sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A:Z"
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            print("ERROR: No data found in sheet", file=sys.stderr)
            return None
        
        # First row = headers
        headers = rows[0]
        
        # Extract column indices
        col_indices = {}
        for i, h in enumerate(headers):
            col_indices[h] = i
        
        leads = []
        # Process data rows (skip header)
        for i, row in enumerate(rows[1:], start=2):
            # Pad row to match header length
            while len(row) < len(headers):
                row.append("")
            
            # Build lead object with exact values
            lead = {
                "row_number": i,
                "Name": row[col_indices.get("Name", -1)] if "Name" in col_indices else "",
                "Title": row[col_indices.get("Title", -1)] if "Title" in col_indices else "",
                "Company": row[col_indices.get("Company", -1)] if "Company" in col_indices else "",
                "Email": row[col_indices.get("Email", -1)] if "Email" in col_indices else "",
                "Status": row[col_indices.get("Status", -1)] if "Status" in col_indices else "",
                "Last_Message": row[col_indices.get("Last Message", -1)] if "Last Message" in col_indices else "",
                "Reply": row[col_indices.get("Reply", -1)] if "Reply" in col_indices else "",
                "Notes_Sally": row[col_indices.get("Notes (Sally)", -1)] if "Notes (Sally)" in col_indices else "",
                "Notes_OnSocial": row[col_indices.get("Notes (OnSocial)", -1)] if "Notes (OnSocial)" in col_indices else "",
                "Last_message_date": row[col_indices.get("Last touch date", -1)] if "Last touch date" in col_indices else "",
                "Last_reply_date": row[col_indices.get("Last touch date", -1)] if "Last touch date" in col_indices else "",
            }
            
            # Only include non-empty rows (has email or name)
            if lead["Email"] or lead["Name"]:
                leads.append(lead)
        
        return leads
    
    except Exception as e:
        print(f"ERROR fetching sheet: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

def main():
    leads = fetch_leads()
    if leads:
        # Output as JSON to stdout
        print(json.dumps(leads, indent=2, ensure_ascii=False))
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
