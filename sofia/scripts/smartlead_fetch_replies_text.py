#!/usr/bin/env python3
"""
SmartLead — Fetch actual reply text for weekly report
======================================================
Loads existing weekly JSON report, fetches message history for each replied lead,
updates Google Sheet "Replies" tab with actual reply text.

Run locally (needs google-auth token):
  cd ~/Documents/GitHub/Sally_sales
  python3 sofia/scripts/smartlead_fetch_replies_text.py
"""

import json
import os
import time
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ──────────────────────────────────────────────────────────────────
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
REPORT_PATH = f"sofia/reports/smartlead_weekly_{TODAY}.json"
TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

# Sheet to update (created by smartlead_weekly_format.py)
SHEET_NAME = f"OS | Analytics | SmartLead Weekly — {TODAY}"


# ── HTML → plain text ────────────────────────────────────────────────────────
class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return " ".join(self.fed)


def strip_html(html):
    if not html:
        return ""
    s = MLStripper()
    s.feed(html)
    text = s.get_data()
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Trim quoted original email (usually starts with "On ... wrote:")
    for marker in ["On ", "From:", "-----Original", "________________________________"]:
        idx = text.find(marker, 50)
        if idx > 50:
            text = text[:idx].strip()
            break
    return text[:1000]  # cap at 1000 chars


# ── SmartLead API ─────────────────────────────────────────────────────────────
def api_get(path, params=None):
    q = params or {}
    q["api_key"] = API_KEY
    for attempt in range(3):
        try:
            resp = httpx.get(f"{BASE_URL}{path}", params=q, timeout=30)
            if resp.status_code == 429:
                print("  rate limited, waiting 5s...")
                time.sleep(5)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == 2:
                print(f"  API error: {e}")
                return {}
            time.sleep(2)
    return {}


def get_lead_id(campaign_id, email):
    """Find lead_id via global leads endpoint."""
    data = api_get("/leads/", {"email": email})
    if isinstance(data, dict) and data.get("id"):
        return data["id"]
    return None


def get_message_history(campaign_id, lead_id):
    """Fetch full message history for a lead."""
    data = api_get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")
    if isinstance(data, dict):
        return data.get("history", data.get("messages", []))
    if isinstance(data, list):
        return data
    return []


def extract_reply_text(history):
    """Extract only the lead's reply from message history."""
    replies = []
    for msg in history:
        # SmartLead marks inbound messages as type=REPLY or from_email != sender
        msg_type = msg.get("type", "").upper()
        stats = msg.get("stats_id") or msg.get("email_stats_id")

        # Look for reply messages
        if msg_type in ("REPLY", "INBOUND") or msg.get("is_reply") or msg.get("reply_time"):
            body = msg.get("email_body", "") or msg.get("body", "") or msg.get("message", "")
            text = strip_html(body)
            if text:
                replies.append(text)

    # Fallback: last message if nothing tagged as reply
    if not replies and history:
        last = history[-1]
        body = last.get("email_body", "") or last.get("body", "") or last.get("message", "")
        replies.append(strip_html(body))

    return " | ".join(replies) if replies else "(no reply text found)"


# ── Google Sheets ─────────────────────────────────────────────────────────────
def get_sheets_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds)


def find_sheet_id(service, sheet_name):
    """Find spreadsheet ID by name."""
    result = service.files().list(
        q=f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet'",
        fields="files(id,name)",
    ).execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    return None


def update_replies_sheet(service, spreadsheet_id, rows):
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Replies!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Format header
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sid = next(s["properties"]["sheetId"] for s in meta["sheets"]
               if s["properties"]["title"] == "Replies")
    num_cols = len(rows[0]) if rows else 7
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
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


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY:
        raise ValueError("SMARTLEAD_API_KEY not set")

    print(f"Loading: {REPORT_PATH}")
    with open(REPORT_PATH) as f:
        report = json.load(f)

    # Collect all replied leads with campaign_id
    all_replies = []
    for cr in report["campaigns"]:
        for r in cr.get("replied_leads", []):
            all_replies.append({**r, "campaign_id": cr["id"], "campaign": cr["name"]})

    # Sort by reply_time desc
    all_replies.sort(key=lambda x: x.get("reply_time", ""), reverse=True)

    print(f"Fetching reply texts for {len(all_replies)} leads...\n")

    rows = [["Reply Time", "Category", "Name", "Email", "Campaign", "Subject", "Reply Text"]]

    for r in all_replies:
        cid = r["campaign_id"]
        email = r["email"]
        name = r.get("name", "")
        cat = r.get("category", "")

        print(f"  {name} ({email})...", end=" ", flush=True)

        # Get lead_id
        lead_id = get_lead_id(cid, email)
        if not lead_id:
            print("lead not found")
            reply_text = "(lead not found)"
        else:
            history = get_message_history(cid, lead_id)
            reply_text = extract_reply_text(history)
            print(f"ok ({len(reply_text)} chars)")

        # Format reply time
        rt = r.get("reply_time", "")
        try:
            dt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
            rt_fmt = dt.strftime("%b %d %H:%M UTC")
        except Exception:
            rt_fmt = rt

        rows.append([rt_fmt, cat, name, email, r.get("campaign", ""), r.get("subject", ""), reply_text])
        time.sleep(0.3)

    # Print table
    print()
    print("=" * 100)
    print("  ALL REPLIES WITH TEXT")
    print("=" * 100)
    for row in rows[1:]:
        print(f"\n  {row[0]}  [{row[1]:>16}]  {row[2]}")
        print(f"  Email:   {row[3]}")
        print(f"  Subject: {row[5]}")
        print(f"  Reply:   {row[6]}")

    # Update Google Sheet
    print(f"\nUpdating Google Sheet: {SHEET_NAME}")
    service = get_sheets_service()

    # Need drive API for search
    drive_service = build("drive", "v3", credentials=Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES))
    result = drive_service.files().list(
        q=f"name='{SHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet'",
        fields="files(id,name)",
    ).execute()
    files = result.get("files", [])

    if not files:
        print("  Sheet not found, creating new one...")
        result2 = service.spreadsheets().create(body={"properties": {"title": SHEET_NAME}}).execute()
        spreadsheet_id = result2["spreadsheetId"]
        # Add Replies sheet
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Replies"}}}]},
        ).execute()
    else:
        spreadsheet_id = files[0]["id"]
        print(f"  Found sheet: {spreadsheet_id}")

    update_replies_sheet(service, spreadsheet_id, rows)

    # Save locally too
    local_path = f"sofia/reports/OS_Analytics_SmartLead_Weekly_{TODAY}_replies_full.csv"
    import csv
    with open(local_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"  CSV saved: {local_path}")

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    print(f"\n  Google Sheet updated: {url}")
    print("  Done!")


if __name__ == "__main__":
    main()
