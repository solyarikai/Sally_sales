"""
Export Inxy GAMING-ONLY companies + contacts to Google Sheets.
Filters to: team_confirmed, gaming, gaming_top_up segments only.
Sheet: https://docs.google.com/spreadsheets/d/104K9DNItN19aXgnnbesQ4jvhdxRGdD8CZJhytblmYf8/
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("export_inxy")

SHEET_ID = "104K9DNItN19aXgnnbesQ4jvhdxRGdD8CZJhytblmYf8"
PROJECT_ID = 48


async def main():
    from app.db import async_session_maker
    from sqlalchemy import text
    import gspread
    from google.oauth2.service_account import Credentials

    # Connect to Google Sheets
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file("/app/google-credentials.json", scopes=scopes)
    gc = gspread.authorize(creds)

    try:
        sh = gc.open_by_key(SHEET_ID)
        logger.info(f"Opened sheet: {sh.title}")
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"Sheet not found or not shared with service account. Share with: autoreplies@autoreplies010226.iam.gserviceaccount.com")
        return

    async with async_session_maker() as session:
        # Get all gaming target companies
        targets = await session.execute(text("""
            SELECT
                sr.domain,
                sr.company_info->>'name' as company_name,
                sr.company_info->>'description' as description,
                sr.matched_segment,
                sr.confidence,
                sr.scores->>'overall_score' as score
            FROM search_results sr
            WHERE sr.project_id = :pid AND sr.is_target = true
            ORDER BY sr.confidence DESC, sr.domain
        """), {"pid": PROJECT_ID})
        target_rows = targets.fetchall()
        logger.info(f"Found {len(target_rows)} target companies")

        # Get contacts for these targets
        contacts = await session.execute(text("""
            SELECT
                dc.domain,
                COALESCE(ec.first_name, '') as first_name,
                COALESCE(ec.last_name, '') as last_name,
                COALESCE(ec.job_title, '') as title,
                COALESCE(ec.email, '') as email,
                COALESCE(ec.linkedin_url, '') as linkedin,
                ec.source
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            JOIN search_results sr ON dc.search_result_id = sr.id
            WHERE sr.project_id = :pid AND sr.is_target = true
            ORDER BY dc.domain, ec.source
        """), {"pid": PROJECT_ID})
        contact_rows = contacts.fetchall()
        logger.info(f"Found {len(contact_rows)} contacts")

    # DO NOT touch Sheet1 — it has the curated 165 companies already
    # Read Sheet1 domains to match contacts against
    try:
        ws_main = sh.worksheet("Sheet1")
        sheet_domains = set()
        rows = ws_main.get_all_values()
        for row in rows[1:]:  # skip header
            if row and row[0]:
                sheet_domains.add(row[0].strip().lower())
        logger.info(f"Sheet1 has {len(sheet_domains)} companies — NOT touching it")
    except Exception as e:
        logger.warning(f"Could not read Sheet1: {e}")
        sheet_domains = None

    # Only export contacts that match Sheet1 domains
    if sheet_domains:
        contact_rows = [r for r in contact_rows if r.domain and r.domain.lower() in sheet_domains]
        logger.info(f"Filtered to {len(contact_rows)} contacts matching Sheet1 domains")

    # Add/update Contacts tab only
    try:
        ws_contacts = sh.worksheet("Contacts")
    except gspread.exceptions.WorksheetNotFound:
        ws_contacts = sh.add_worksheet(title="Contacts", rows=500, cols=10)

    contact_header = ["Domain", "First Name", "Last Name", "Title", "Email", "LinkedIn", "Source"]
    contact_data = [contact_header]
    for r in contact_rows:
        email = r.email or ""
        # Clean up malformed emails
        email = email.replace("u003e", "").replace("<", "").replace(">", "")
        contact_data.append([
            r.domain or "",
            r.first_name or "",
            r.last_name or "",
            r.title or "",
            email,
            r.linkedin or "",
            r.source or "",
        ])

    ws_contacts.clear()
    ws_contacts.update(range_name="A1", values=contact_data)
    logger.info(f"Wrote {len(contact_data)-1} contacts to 'Contacts' sheet")

    # Delete the Companies tab we incorrectly created earlier
    try:
        old_companies = sh.worksheet("Companies")
        sh.del_worksheet(old_companies)
        logger.info("Removed old 'Companies' tab")
    except:
        pass

    logger.info(f"Done! Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/")


if __name__ == "__main__":
    asyncio.run(main())
