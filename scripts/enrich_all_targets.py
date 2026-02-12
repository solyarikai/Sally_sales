"""
Enrich ALL target companies via Apollo (paid plan).
====================================================
- Skips domains already in Smartlead campaigns.
- Uses person ID for bulk_match (not name+domain).
- Exports results to Google Sheets.
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
logger = logging.getLogger("enrich_all")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

SHARE_WITH = ["pn@getsally.io"]


async def get_smartlead_domains(session) -> set:
    """Get all domains that are already in Smartlead campaigns."""
    from sqlalchemy import text
    result = await session.execute(text("""
        SELECT DISTINCT split_part(email, '@', 2) as domain
        FROM contacts
        WHERE smartlead_id IS NOT NULL AND email IS NOT NULL
    """))
    domains = {row.domain for row in result.fetchall()}
    logger.info(f"Smartlead exclusion: {len(domains)} domains already in campaigns")
    return domains


async def enrich_targets():
    """Enrich all target companies that aren't in Smartlead."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Get Smartlead domains to exclude
        smartlead_domains = await get_smartlead_domains(session)

        # Get all targets needing Apollo enrichment
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.apollo_people_count.in_([0, None]),
            ).order_by(DiscoveredCompany.project_id, DiscoveredCompany.confidence.desc())
        )
        all_targets = list(result.scalars().all())

        # Filter out Smartlead domains
        targets = [t for t in all_targets if t.domain not in smartlead_domains]
        skipped = len(all_targets) - len(targets)

        logger.info(f"Targets: {len(all_targets)} total, {skipped} in Smartlead, {len(targets)} to enrich")
        by_project = {}
        for t in targets:
            by_project.setdefault(t.project_id, 0)
            by_project[t.project_id] += 1
        logger.info(f"By project: {by_project}")

        if not targets:
            return {"processed": 0, "skipped": skipped}

        apollo_service.reset_credits()
        stats = {
            "total": len(targets),
            "skipped_smartlead": skipped,
            "processed": 0,
            "people_found": 0,
            "with_email": 0,
            "with_linkedin": 0,
            "no_people": 0,
            "credits_used": 0,
        }

        for dc in targets:
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
            stats["with_linkedin"] += sum(1 for p in people if p.get("linkedin_url"))
            if not people:
                stats["no_people"] += 1

            # Commit every 50 domains
            if stats["processed"] % 50 == 0:
                await session.commit()
                stats["credits_used"] = apollo_service.credits_used
                logger.info(
                    f"Progress: {stats['processed']}/{len(targets)} | "
                    f"people={stats['people_found']} emails={stats['with_email']} "
                    f"linkedin={stats['with_linkedin']} no_people={stats['no_people']} "
                    f"credits={stats['credits_used']}"
                )

        await session.commit()
        stats["credits_used"] = apollo_service.credits_used
        logger.info(f"Apollo enrichment complete: {json.dumps(stats, indent=2)}")
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
            domain_contacts.setdefault(c.domain, []).append(c)

        logger.info(f"{project_name}: {len(target_rows)} targets, contacts for {len(domain_contacts)} domains")

        # One row per contact — company data duplicated for easy reading
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
                str(row.confidence or ""), row.review_status or "",
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
                data.append(company_cols + ["", "", "", "", "", "", "", row.reasoning or ""])

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

    start = datetime.utcnow()
    logger.info("=" * 70)
    logger.info("APOLLO ENRICHMENT (all targets, skip Smartlead)")
    logger.info(f"Time: {start.isoformat()}")
    logger.info("=" * 70)

    results = {}

    # Step 1: Apollo enrichment
    try:
        results["apollo"] = await enrich_targets()
    except Exception as e:
        logger.error(f"Apollo enrichment FAILED: {e}", exc_info=True)
        results["apollo_error"] = str(e)

    # Step 2: Export each project to Google Sheets
    async with async_session_maker() as session:
        rows = await session.execute(text("""
            SELECT DISTINCT dc.project_id, dc.company_id, p.name as project_name
            FROM discovered_companies dc
            JOIN projects p ON p.id = dc.project_id
            WHERE dc.is_target = true
            ORDER BY dc.project_id
        """))
        projects = rows.fetchall()

    for proj in projects:
        try:
            key = f"sheet_{proj.project_name}"
            results[key] = await export_to_sheets(proj.project_id, proj.company_id, proj.project_name)
        except Exception as e:
            logger.error(f"{proj.project_name} export FAILED: {e}", exc_info=True)
            results[f"{proj.project_name}_error"] = str(e)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("=" * 70)
    logger.info("COMPLETE")
    logger.info(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
