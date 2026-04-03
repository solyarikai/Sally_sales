"""Export Archistruct targets to Google Sheet.
Run inside Docker container with DB + Google credentials access."""
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
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import select, text

    async with async_session_maker() as session:
        # Fetch all targets for project 24
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
                sr.analyzed_at,
                'https://' || sr.domain as url
            FROM search_results sr
            WHERE sr.project_id = 24
                AND sr.is_target = true
            ORDER BY sr.confidence DESC, sr.analyzed_at DESC
        """))
        rows = result.fetchall()

        logger.info(f"Found {len(rows)} targets for export")

        # Build sheet data
        headers = [
            "Domain", "URL", "Company Name", "Description", "Services",
            "Location", "Industry", "Confidence", "Language Match",
            "Industry Match", "Service Match", "Company Type", "Geography Match",
            "Review Status", "Reasoning", "Analyzed At"
        ]

        data = [headers]
        for row in rows:
            services = row.services
            if services:
                try:
                    services_list = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(services_list) if isinstance(services_list, list) else str(services)
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
                str(row.language_match or ""),
                str(row.industry_match or ""),
                str(row.service_match or ""),
                str(row.company_type_score or ""),
                str(row.geography_match or ""),
                row.review_status or "",
                row.reasoning or "",
                str(row.analyzed_at or ""),
            ])

        # Export to Google Sheet
        title = f"Archistruct Targets — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        share_with = ["pn@getsally.io"]

        url = google_sheets_service.create_and_populate(
            title=title,
            data=data,
            share_with=share_with,
        )

        if url:
            logger.info(f"Exported {len(rows)} targets to: {url}")
        else:
            logger.error("Export failed!")
            # Fallback: save as JSON
            with open("/scripts/archistruct_targets.json", "w") as f:
                json.dump([dict(zip(headers, row)) for row in data[1:]], f, indent=2, default=str, ensure_ascii=False)
            logger.info("Saved fallback JSON to /scripts/archistruct_targets.json")

if __name__ == "__main__":
    asyncio.run(main())
