#!/usr/bin/env python3
"""
Fetch GetSales LinkedIn inbox replies (27/03-03/04) for Rajat & Albina
and append them to the Replies sheet in Google Sheets.

Run:
  uv run --python 3.11 --with httpx --with google-auth --with google-api-python-client \
    python3 sofia/scripts/gs_replies_to_sheets.py
"""
import os, asyncio, json
from datetime import datetime, timezone
import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── GetSales config ──────────────────────────────────────────────────────────
GS_TOKEN = os.environ.get(
    "GETSALES_API_KEY",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"
)
BASE = "https://amazing.getsales.io"
GS_HEADERS = {"Authorization": f"Bearer {GS_TOKEN}"}

WEEK_START = datetime(2026, 3, 27, tzinfo=timezone.utc)
WEEK_END   = datetime(2026, 4,  4, tzinfo=timezone.utc)

# Known sender UUIDs
SENDER_MAP = {
    "f4ddb17a-d410-40d2-9130-d7cb00601d73": "Rajat Chauhan",
    "d5c18723-aca1-4ca4-84b8-60fdee894d67": "Albina Yanchanka",
}

# ── Google Sheets config ─────────────────────────────────────────────────────
TOKEN_PATH = ".claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "1KROy8xUYJym8osIQ-11LZL2o7oUInYnYRGbK66_CNQU"
SHEET_NAME = "Replies"


def in_week(dt_str: str) -> bool:
    if not dt_str:
        return False
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return WEEK_START <= dt < WEEK_END
    except Exception:
        return False


def fmt_time(dt_str: str) -> str:
    """Format ISO timestamp → 'Apr 03 08:15 UTC' to match existing sheet format."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d %H:%M UTC")
    except Exception:
        return dt_str


async def fetch_inbox(client: httpx.AsyncClient) -> list:
    """Fetch inbox messages for the week, filtered by our sender UUIDs."""
    results = []
    offset = 0
    limit = 200
    pages = 0
    WEEK_START_STR = "2026-03-27"

    while True:
        try:
            r = await client.get(
                f"{BASE}/flows/api/linkedin-messages",
                params={
                    "filter[type]": "inbox",
                    "order_field": "sent_at",
                    "order_type": "desc",
                    "limit": limit,
                    "offset": offset,
                }
            )
        except httpx.ReadTimeout:
            print("  Timeout, retrying in 10s...")
            await asyncio.sleep(10)
            continue

        if r.status_code == 429:
            await asyncio.sleep(15)
            continue
        if r.status_code != 200 or not r.text.strip():
            break

        data = r.json()
        batch = data.get("data", [])
        if not batch:
            break

        pages += 1
        # Track oldest message in batch to decide early stop
        oldest_in_batch = min((m.get("sent_at", "9999") for m in batch), default="9999")

        for msg in batch:
            sent_at = msg.get("sent_at", "")
            sender_uuid = msg.get("sender_profile_uuid", "")
            if sender_uuid not in SENDER_MAP:
                continue
            if in_week(sent_at):
                results.append(msg)

        offset += len(batch)
        total = data.get("total", 0)
        print(f"  [inbox] page {pages}: {offset}/{total} | matched: {len(results)} | oldest: {oldest_in_batch[:10]}")

        # Stop when the whole batch is older than our week window
        if oldest_in_batch < WEEK_START_STR:
            print("  Past week window, stopping.")
            break
        if not data.get("has_more") or offset >= total:
            break
        await asyncio.sleep(0.3)

    return results


async def fetch_lead_name(client: httpx.AsyncClient, lead_uuid: str) -> tuple[str, str]:
    """Returns (full_name, email) for a lead UUID."""
    if not lead_uuid:
        return "", ""
    try:
        r = await client.get(f"{BASE}/leads/api/leads/{lead_uuid}")
        if r.status_code == 200 and r.text.strip():
            d = r.json()
            lead = d.get("lead", d)
            first = lead.get("first_name", "")
            last = lead.get("last_name", "")
            email = lead.get("work_email") or lead.get("personal_email") or ""
            company = lead.get("company_name", "")
            name = f"{first} {last}".strip()
            if company:
                name = f"{name} ({company})"
            return name, email
    except Exception:
        pass
    return "", ""


async def fetch_flow_name(client: httpx.AsyncClient, flow_uuid: str) -> str:
    """Returns flow name for a flow UUID."""
    if not flow_uuid:
        return ""
    try:
        r = await client.get(f"{BASE}/flows/api/flows/{flow_uuid}")
        if r.status_code == 200 and r.text.strip():
            d = r.json()
            return d.get("name", "") or d.get("data", {}).get("name", "")
    except Exception:
        pass
    return ""


async def main():
    async with httpx.AsyncClient(headers=GS_HEADERS, timeout=60) as client:

        # 1. Fetch inbox replies
        print("Fetching inbox replies...")
        inbox = await fetch_inbox(client)
        print(f"  Total matched: {len(inbox)}")

        if not inbox:
            print("No replies found for Rajat/Albina this week.")
            return

        # 2. Fetch lead names and flow names
        print("\nFetching lead details...")
        rows = []
        flow_cache = {}

        for msg in sorted(inbox, key=lambda x: x.get("sent_at", ""), reverse=True):
            lead_uuid = msg.get("lead_uuid", "")
            flow_uuid = msg.get("flow_uuid", "")
            sender_uuid = msg.get("sender_profile_uuid", "")
            sender_name = SENDER_MAP.get(sender_uuid, "Unknown")
            sent_at = msg.get("sent_at", "")
            text = (msg.get("text") or "").strip()

            # Fetch lead name
            name, email = await fetch_lead_name(client, lead_uuid)
            await asyncio.sleep(0.1)

            # Fetch flow name (cached)
            if flow_uuid not in flow_cache:
                flow_cache[flow_uuid] = await fetch_flow_name(client, flow_uuid)
                await asyncio.sleep(0.1)
            flow_name = flow_cache.get(flow_uuid, "")

            print(f"  {fmt_time(sent_at)} | {sender_name} | {name} | {text[:60]}")

            rows.append([
                fmt_time(sent_at),
                f"LinkedIn ({sender_name})",
                name or "—",
                email or "—",
                flow_name or "—",
                "LinkedIn DM",
                text,
            ])

        print(f"\nPrepared {len(rows)} rows to add.")

        # 3. Append to Google Sheets
        print("\nConnecting to Google Sheets...")
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build('sheets', 'v4', credentials=creds)

        # Find last row
        existing = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:A"
        ).execute()
        last_row = len(existing.get("values", [])) + 1

        range_to_write = f"{SHEET_NAME}!A{last_row}"
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_write,
            valueInputOption="RAW",
            body={"values": rows}
        ).execute()

        print(f"  Written {len(rows)} rows starting at row {last_row}")
        print(f"\nDone! Sheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=605910629")


if __name__ == "__main__":
    asyncio.run(main())
