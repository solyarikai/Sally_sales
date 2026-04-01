"""
Google Sheets export — standalone, uses service account credentials.
Writes contacts to a new tab in the EasyStaff Global reference sheet.
"""
import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SHEET_ID = "17O43ThvMNB5ToqsRjwNn81MYe2tjrNql5W93-H3x008"
CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/google-credentials.json")


def _get_service():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def export_companies(run_id: int, companies: List[Dict[str, Any]], tab_name: str = None) -> str:
    """Export Phase 1 company list to Google Sheet. Returns sheet URL."""
    tab = tab_name or f"DACH-LATAM Companies run{run_id}"
    svc = _get_service()

    headers = [
        "Domain", "Company Name", "HQ Country", "Employees",
        "Industry", "LATAM Countries", "LATAM Employee Count", "Approved",
    ]
    rows = [headers]
    for c in companies:
        rows.append([
            c["domain"],
            c["name"] or "",
            c["hq_country"] or "",
            str(c["employees"] or ""),
            c["industry"] or "",
            c["latam_countries"] or "",
            str(c["latam_count"] or 0),
            "YES" if c["approved"] else "NO",
        ])

    _write_tab(svc, tab, rows)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    logger.info(f"Exported {len(companies)} companies to '{tab}': {url}")
    return url


def export_contacts(run_id: int, contacts: List[Dict[str, Any]], tab_name: str = None) -> str:
    """Export Phase 2 CEO/CFO contacts to Google Sheet. Returns sheet URL."""
    tab = tab_name or f"DACH-LATAM Contacts run{run_id}"
    svc = _get_service()

    headers = [
        "First Name", "Last Name", "Title", "LinkedIn URL",
        "Company Domain", "Apollo ID",
    ]
    rows = [headers]
    for c in contacts:
        rows.append([
            c["first_name"] or "",
            c["last_name"] or "",
            c["title"] or "",
            c["linkedin_url"] or "",
            c["company_domain"] or "",
            c["apollo_id"] or "",
        ])

    _write_tab(svc, tab, rows)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    logger.info(f"Exported {len(contacts)} contacts to '{tab}': {url}")
    return url


def _write_tab(svc, tab_name: str, rows: List[List[str]]):
    """Create or overwrite a tab with rows."""
    try:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        ).execute()
        logger.info(f"Created tab '{tab_name}'")
    except Exception:
        logger.info(f"Tab '{tab_name}' already exists, overwriting")

    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()
