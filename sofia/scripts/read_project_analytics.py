#!/usr/bin/env python3
"""Read Project Analytics sheet to understand structure."""

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"
TAB = "project analytics"

def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)

def main():
    service = get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{TAB}!A1:M60",
    ).execute()
    rows = result.get("values", [])
    for i, row in enumerate(rows, 1):
        print(f"Row {i:02d}: {row}")

if __name__ == "__main__":
    main()
