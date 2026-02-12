"""
Export targets + contacts to Google Sheets.
===========================================
Simple export script — no search, no Apollo.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("export_sheets")

ARCHISTRUCT_PROJECT_ID = 24
ARCHISTRUCT_COMPANY_ID = 1
DELIRYO_PROJECT_ID = 18
SHARE_WITH = ["pn@getsally.io"]


async def export_to_sheets(project_id: int, company_id: int, project_name: str) -> str:
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info(f"--- Exporting {project_name} to Google Sheets ---")

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
                sr.analyzed_at,
                'https://' || sr.domain as url
            FROM search_results sr
            WHERE sr.project_id = :project_id
                AND sr.is_target = true
                AND sr.review_status != 'rejected'
            ORDER BY sr.confidence DESC, sr.analyzed_at DESC
        """), {"project_id": project_id})
        target_rows = result.fetchall()

        contacts_result = await session.execute(text("""
            SELECT
                dc.domain,
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.phone,
                ec.job_title,
                ec.linkedin_url,
                ec.source,
                ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :project_id
                AND dc.company_id = :company_id
                AND dc.is_target = true
            ORDER BY dc.domain, ec.is_verified DESC, ec.source
        """), {"project_id": project_id, "company_id": company_id})
        contact_rows = contacts_result.fetchall()

        domain_contacts = {}
        for c in contact_rows:
            d = c.domain
            if d not in domain_contacts:
                domain_contacts[d] = []
            domain_contacts[d].append(c)

        logger.info(f"{project_name}: {len(target_rows)} targets, contacts for {len(domain_contacts)} domains")

        headers = [
            "Domain", "URL", "Company Name", "Description", "Services",
            "Location", "Industry", "Confidence",
            "Language", "Industry Match", "Service Match", "Company Type", "Geography",
            "Review Status",
            "Contact 1 Name", "Contact 1 Email", "Contact 1 Phone",
            "Contact 1 Title", "Contact 1 LinkedIn", "Contact 1 Source",
            "Contact 2 Name", "Contact 2 Email", "Contact 2 Phone",
            "Contact 2 Title", "Contact 2 LinkedIn", "Contact 2 Source",
            "Contact 3 Name", "Contact 3 Email", "Contact 3 Phone",
            "Contact 3 Title", "Contact 3 LinkedIn", "Contact 3 Source",
            "Reasoning",
        ]

        data = [headers]
        for row in target_rows:
            services = row.services
            if services:
                try:
                    sl = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(sl) if isinstance(sl, list) else str(services)
                except Exception:
                    pass

            row_data = [
                row.domain, row.url, row.company_name or "", row.description or "",
                services or "", row.location or "", row.industry or "",
                str(row.confidence or ""),
                str(row.language_match or ""), str(row.industry_match or ""),
                str(row.service_match or ""), str(row.company_type_score or ""),
                str(row.geography_match or ""), row.review_status or "",
            ]

            contacts = domain_contacts.get(row.domain, [])
            for i in range(3):
                if i < len(contacts):
                    c = contacts[i]
                    name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                    row_data.extend([name, c.email or "", c.phone or "",
                                     c.job_title or "", c.linkedin_url or "",
                                     str(c.source or "")])
                else:
                    row_data.extend([""] * 6)

            row_data.append(row.reasoning or "")
            data.append(row_data)

        title = f"{project_name} Targets + Contacts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        url = google_sheets_service.create_and_populate(
            title=title,
            data=data,
            share_with=SHARE_WITH,
        )

        if url:
            logger.info(f"{project_name}: Exported {len(target_rows)} targets to: {url}")
        else:
            logger.error(f"{project_name}: Google Sheets export FAILED, saving JSON fallback")
            fallback = f"/scripts/{project_name.lower()}_targets.json"
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)
            url = fallback

        return url


async def main():
    from sqlalchemy import text
    from app.db import async_session_maker

    logger.info("=" * 60)
    logger.info("GOOGLE SHEETS EXPORT")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        row = await session.execute(text("SELECT company_id FROM projects WHERE id = :pid"), {"pid": DELIRYO_PROJECT_ID})
        deliryo_company_id = row.scalar_one()

    results = {}

    try:
        results["archistruct"] = await export_to_sheets(ARCHISTRUCT_PROJECT_ID, ARCHISTRUCT_COMPANY_ID, "ArchiStruct")
    except Exception as e:
        logger.error(f"ArchiStruct export FAILED: {e}", exc_info=True)
        results["archistruct_error"] = str(e)

    try:
        results["deliryo"] = await export_to_sheets(DELIRYO_PROJECT_ID, deliryo_company_id, "Deliryo")
    except Exception as e:
        logger.error(f"Deliryo export FAILED: {e}", exc_info=True)
        results["deliryo_error"] = str(e)

    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
