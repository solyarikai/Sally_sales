"""
Retry Apollo enrichment (with rate limiting) + Google Sheets export.
===================================================================
Fixes:
1. Apollo rate limiting (1.3s between calls, retry on 429)
2. Broader search (no title filter initially, then with titles)
3. Google Sheets export with properly mounted credentials
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
logger = logging.getLogger("retry_apollo_export")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ============================================================
# Config
# ============================================================
ARCHISTRUCT_PROJECT_ID = 24
ARCHISTRUCT_COMPANY_ID = 1

DELIRYO_PROJECT_ID = 18

ARCHISTRUCT_APOLLO_TITLES = [
    "CEO", "Founder", "Co-Founder", "Managing Director", "Owner",
    "General Manager", "Director", "Head of Sales",
    "VP Business Development", "Chief Operating Officer",
    "General Director", "Commercial Director",
]

DELIRYO_APOLLO_TITLES = [
    "CEO", "Founder", "Co-Founder", "Managing Partner", "Director",
    "Head of Family Office", "CIO", "Portfolio Manager", "Partner",
    "Managing Director", "Chief Investment Officer",
    "Head of Wealth Management", "Senior Partner",
]

SHARE_WITH = ["pn@getsally.io"]


async def retry_apollo(project_id: int, company_id: int, titles: list, project_name: str):
    """Retry Apollo enrichment with rate limiting and broader search."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from sqlalchemy import select

    logger.info(f"--- Apollo retry for {project_name} (project_id={project_id}) ---")

    async with async_session_maker() as session:
        # Get targets that have 0 Apollo results
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.company_id == company_id,
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.apollo_people_count == 0,
            ).order_by(DiscoveredCompany.confidence.desc())
        )
        targets = list(result.scalars().all())
        logger.info(f"{project_name}: {len(targets)} targets need Apollo re-enrichment")

        if not targets:
            return {"processed": 0, "people_found": 0}

        apollo_service.reset_credits()
        stats = {"processed": 0, "people_found": 0, "with_email": 0}

        for dc in targets:
            # Single call — no title filter, grab all people, enrich by ID
            people = await apollo_service.enrich_by_domain(dc.domain, limit=5)

            for person in people:
                ec = ExtractedContact(
                    discovered_company_id=dc.id,
                    email=person.get("email"),
                    phone=person.get("phone"),
                    first_name=person.get("first_name"),
                    last_name=person.get("last_name"),
                    job_title=person.get("job_title"),
                    linkedin_url=person.get("linkedin_url"),
                    source=ContactSource.APOLLO,
                    is_verified=person.get("is_verified", False),
                    verification_method="apollo" if person.get("is_verified") else None,
                    raw_data=person.get("raw_data"),
                )
                session.add(ec)

            dc.apollo_people_count = len(people)
            dc.apollo_enriched_at = datetime.utcnow()
            dc.contacts_count = (dc.contacts_count or 0) + len(people)
            stats["processed"] += 1
            stats["people_found"] += len(people)
            stats["with_email"] += sum(1 for p in people if p.get("email"))

            # Commit every 20 domains
            if stats["processed"] % 20 == 0:
                await session.commit()
                logger.info(f"{project_name}: {stats['processed']}/{len(targets)} processed, {stats['people_found']} people found")

        await session.commit()
        logger.info(f"{project_name} Apollo complete: {stats}")
        return stats


async def export_to_sheets(project_id: int, company_id: int, project_name: str) -> str:
    """Export targets + contacts to Google Sheets."""
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
            domain = c.domain
            if domain not in domain_contacts:
                domain_contacts[domain] = []
            domain_contacts[domain].append(c)

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
                    services_list = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(services_list) if isinstance(services_list, list) else str(services)
                except Exception:
                    pass

            row_data = [
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
            ]

            contacts = domain_contacts.get(row.domain, [])
            for i in range(3):
                if i < len(contacts):
                    c = contacts[i]
                    name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                    row_data.extend([
                        name,
                        c.email or "",
                        c.phone or "",
                        c.job_title or "",
                        c.linkedin_url or "",
                        str(c.source or ""),
                    ])
                else:
                    row_data.extend(["", "", "", "", "", ""])

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
            logger.error(f"{project_name}: Google Sheets export failed!")
            fallback_path = f"/scripts/{project_name.lower()}_targets.json"
            with open(fallback_path, "w", encoding="utf-8") as f:
                json.dump(
                    [dict(zip(headers, r)) for r in data[1:]],
                    f, indent=2, default=str, ensure_ascii=False,
                )
            logger.info(f"Saved fallback JSON to {fallback_path}")
            url = fallback_path

        return url


async def main():
    from sqlalchemy import text

    start = datetime.utcnow()
    logger.info("=" * 70)
    logger.info("RETRY: APOLLO ENRICHMENT + GOOGLE SHEETS EXPORT")
    logger.info(f"Time: {start.isoformat()}")
    logger.info("=" * 70)

    results = {}

    # Get Deliryo company_id
    from app.db import async_session_maker
    async with async_session_maker() as session:
        row = await session.execute(
            text("SELECT company_id FROM projects WHERE id = :pid"),
            {"pid": DELIRYO_PROJECT_ID},
        )
        deliryo_company_id = row.scalar_one()

    # Apollo retry for ArchiStruct
    try:
        results["archistruct_apollo"] = await retry_apollo(
            ARCHISTRUCT_PROJECT_ID, ARCHISTRUCT_COMPANY_ID,
            ARCHISTRUCT_APOLLO_TITLES, "ArchiStruct",
        )
    except Exception as e:
        logger.error(f"ArchiStruct Apollo FAILED: {e}", exc_info=True)
        results["archistruct_apollo_error"] = str(e)

    # Apollo retry for Deliryo
    try:
        results["deliryo_apollo"] = await retry_apollo(
            DELIRYO_PROJECT_ID, deliryo_company_id,
            DELIRYO_APOLLO_TITLES, "Deliryo",
        )
    except Exception as e:
        logger.error(f"Deliryo Apollo FAILED: {e}", exc_info=True)
        results["deliryo_apollo_error"] = str(e)

    # Google Sheets export
    try:
        results["archistruct_sheet"] = await export_to_sheets(
            ARCHISTRUCT_PROJECT_ID, ARCHISTRUCT_COMPANY_ID, "ArchiStruct",
        )
    except Exception as e:
        logger.error(f"ArchiStruct export FAILED: {e}", exc_info=True)
        results["archistruct_export_error"] = str(e)

    try:
        results["deliryo_sheet"] = await export_to_sheets(
            DELIRYO_PROJECT_ID, deliryo_company_id, "Deliryo",
        )
    except Exception as e:
        logger.error(f"Deliryo export FAILED: {e}", exc_info=True)
        results["deliryo_export_error"] = str(e)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("=" * 70)
    logger.info("RETRY COMPLETE")
    logger.info(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
    logger.info("=" * 70)

    with open("/scripts/retry_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())
