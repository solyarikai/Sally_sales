"""Export Archistruct targets to an existing Google Sheet.
Uses gspread since Drive quota is exceeded for creating new sheets."""
import asyncio
import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("export_targets")

async def main():
    from app.db import async_session_maker
    from sqlalchemy import text
    import gspread
    from google.oauth2.service_account import Credentials

    # Connect to Google Sheets
    creds = Credentials.from_service_account_file(
        "/app/google-credentials.json",
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    gc = gspread.authorize(creds)

    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT
                sr.domain,
                sr.confidence,
                sr.reasoning,
                sr.company_info->>'name' as company_name,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status,
                'https://' || sr.domain as url,
                sq.query_text as source_query
            FROM search_results sr
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            WHERE sr.project_id = 24
                AND sr.is_target = true
            ORDER BY sr.confidence DESC, sr.analyzed_at DESC
        """))
        rows = result.fetchall()
        logger.info(f"Found {len(rows)} targets")

    # Build data
    headers = [
        "Domain", "URL", "Company Name", "Description", "Services",
        "Location", "Industry", "Confidence", "Source Query",
        "Language", "Industry Match", "Service", "Company Type", "Geography",
        "Review Status", "Reasoning"
    ]

    data = [headers]
    for row in rows:
        services = row.services
        if services:
            try:
                sl = json.loads(services) if isinstance(services, str) else services
                services = ", ".join(sl) if isinstance(sl, list) else str(services)
            except:
                pass

        data.append([
            row.domain,
            row.url,
            row.company_name or "",
            row.description or "",
            services or "",
            row.location or "",
            row.industry or "",
            str(row.confidence or ""),
            row.source_query or "",
            str(row.language_match or ""),
            str(row.industry_match or ""),
            str(row.service_match or ""),
            str(row.company_type_score or ""),
            str(row.geography_match or ""),
            row.review_status or "",
            row.reasoning or "",
        ])

    # Open existing sheet and add/update worksheet
    sh = gc.open_by_key("1abhDmhw0ieUlMvPZzxHOlVY8PWdAUi3FGsBzHqIjUsI")

    tab_name = f"Targets {datetime.utcnow().strftime('%m-%d')}"
    try:
        ws = sh.add_worksheet(title=tab_name, rows=len(data)+5, cols=len(headers))
    except Exception:
        ws = sh.worksheet(tab_name)
        ws.clear()

    ws.update(range_name="A1", values=data)
    ws.format("A1:P1", {"textFormat": {"bold": True}})

    sheet_url = f"https://docs.google.com/spreadsheets/d/1abhDmhw0ieUlMvPZzxHOlVY8PWdAUi3FGsBzHqIjUsI/edit#gid={ws.id}"
    logger.info(f"Exported {len(rows)} targets to: {sheet_url}")

if __name__ == "__main__":
    asyncio.run(main())
