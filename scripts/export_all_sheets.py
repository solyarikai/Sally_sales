"""Export all projects' targets + contacts to Google Sheets."""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("export_sheets")

SHARE_WITH = ["pn@getsally.io"]


async def export_to_sheets(project_id: int, company_id: int, project_name: str) -> str:
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info(f"--- Exporting {project_name} (project_id={project_id}) ---")

    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT
                sr.domain, sr.confidence, sr.reasoning,
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
                'https://' || sr.domain as url
            FROM search_results sr
            WHERE sr.project_id = :project_id
                AND sr.is_target = true AND sr.review_status != 'rejected'
            ORDER BY sr.confidence DESC, sr.analyzed_at DESC
        """), {"project_id": project_id})
        target_rows = result.fetchall()

        contacts_result = await session.execute(text("""
            SELECT dc.domain, ec.first_name, ec.last_name, ec.email, ec.phone,
                   ec.job_title, ec.linkedin_url, ec.source, ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :project_id AND dc.company_id = :company_id AND dc.is_target = true
            ORDER BY dc.domain, ec.is_verified DESC, ec.source
        """), {"project_id": project_id, "company_id": company_id})
        contact_rows = contacts_result.fetchall()

        domain_contacts = {}
        for c in contact_rows:
            domain_contacts.setdefault(c.domain, []).append(c)

        logger.info(f"{project_name}: {len(target_rows)} targets, contacts for {len(domain_contacts)} domains")

        # One row per contact — company data is duplicated for easy reading
        headers = [
            "Domain", "URL", "Company Name", "Description", "Services",
            "Location", "Industry", "Confidence",
            "Review Status",
            "Contact Name", "Email", "Phone", "Job Title", "LinkedIn", "Source", "Verified",
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
            company_cols = [
                row.domain, row.url, row.company_name or "", row.description or "",
                services or "", row.location or "", row.industry or "",
                str(row.confidence or ""),
                row.review_status or "",
            ]
            contacts = domain_contacts.get(row.domain, [])
            if contacts:
                for c in contacts:
                    name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                    data.append(company_cols + [
                        name, c.email or "", c.phone or "",
                        c.job_title or "", c.linkedin_url or "",
                        str(c.source or ""), "Yes" if c.is_verified else "",
                        row.reasoning or "",
                    ])
            else:
                # Company with no contacts — still include it
                data.append(company_cols + ["", "", "", "", "", "", "", row.reasoning or ""])

        title = f"{project_name} Targets + Contacts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        url = google_sheets_service.create_and_populate(title=title, data=data, share_with=SHARE_WITH)
        if url:
            logger.info(f"{project_name}: {len(target_rows)} targets -> {url}")
        else:
            logger.error(f"{project_name}: Sheets FAILED")
            fallback = f"/scripts/{project_name.lower().replace(' ', '_')}_targets.json"
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)
            url = fallback
        return url


async def main():
    from sqlalchemy import text
    from app.db import async_session_maker

    logger.info("=" * 60)
    logger.info("GOOGLE SHEETS EXPORT — ALL PROJECTS")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        rows = await session.execute(text("""
            SELECT DISTINCT dc.project_id, dc.company_id, p.name as project_name
            FROM discovered_companies dc
            JOIN projects p ON p.id = dc.project_id
            WHERE dc.is_target = true
            ORDER BY dc.project_id
        """))
        projects = rows.fetchall()

    results = {}
    for proj in projects:
        try:
            results[proj.project_name] = await export_to_sheets(proj.project_id, proj.company_id, proj.project_name)
        except Exception as e:
            logger.error(f"{proj.project_name} FAILED: {e}", exc_info=True)
            results[f"{proj.project_name}_error"] = str(e)

    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")


if __name__ == "__main__":
    asyncio.run(main())
