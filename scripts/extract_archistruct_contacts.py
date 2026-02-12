"""Extract contacts for Archistruct target companies (project 24).

Steps:
1. Get target DiscoveredCompanies (is_target=True)
2. Scrape missing websites via Crona
3. GPT + regex contact extraction
4. Apollo enrichment (max 20 credits)

Run inside Docker:
  docker run -d --name archistruct-contacts \
    --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... -e APOLLO_API_KEY=... \
    -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/extract_archistruct_contacts.py'
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("archistruct_contacts")

PROJECT_ID = 24
COMPANY_ID = 1
APOLLO_MAX_CREDITS = 20
APOLLO_MAX_PEOPLE = 3
CRONA_BATCH_SIZE = 50


async def main():
    from sqlalchemy import select, func
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany, ExtractedContact
    from app.services.pipeline_service import pipeline_service
    from app.services.crona_service import crona_service
    from app.services.apollo_service import apollo_service
    from datetime import datetime

    async with async_session_maker() as session:
        # 1. Get target companies
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.company_id == COMPANY_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        targets = result.scalars().all()
        logger.info(f"Found {len(targets)} target companies for project {PROJECT_ID}")

        if not targets:
            logger.warning("No targets found, exiting")
            return

        # 2. Scrape missing websites via Crona
        to_scrape = [dc for dc in targets if not dc.scraped_html and not dc.scraped_text]
        logger.info(f"Need to scrape {len(to_scrape)} domains (already scraped: {len(targets) - len(to_scrape)})")

        if to_scrape and crona_service.is_configured:
            for batch_start in range(0, len(to_scrape), CRONA_BATCH_SIZE):
                batch = to_scrape[batch_start:batch_start + CRONA_BATCH_SIZE]
                domains = [dc.domain for dc in batch]
                logger.info(f"Crona batch {batch_start // CRONA_BATCH_SIZE + 1}: scraping {len(domains)} domains...")

                scraped = await crona_service.scrape_domains(domains, timeout=180)

                for dc in batch:
                    text = scraped.get(dc.domain)
                    if text:
                        dc.scraped_html = text[:50000]
                        dc.scraped_text = text[:50000]
                        dc.scraped_at = datetime.utcnow()

                await session.commit()
                logger.info(f"Crona batch done: {sum(1 for v in scraped.values() if v)}/{len(domains)} success")
        elif to_scrape:
            logger.warning("Crona not configured, skipping website scraping")

        # 3. GPT + regex contact extraction
        target_ids = [dc.id for dc in targets]
        logger.info(f"Running contact extraction on {len(target_ids)} targets...")

        extract_stats = await pipeline_service.extract_contacts_batch(
            session, target_ids, company_id=COMPANY_ID
        )
        logger.info(f"Contact extraction: {extract_stats}")

        # 4. Apollo enrichment (capped)
        apollo_service.reset_credits()
        logger.info(f"Running Apollo enrichment (max {APOLLO_MAX_CREDITS} credits, max {APOLLO_MAX_PEOPLE} people/domain)...")

        apollo_stats = await pipeline_service.enrich_apollo_batch(
            session, target_ids, company_id=COMPANY_ID,
            max_people=APOLLO_MAX_PEOPLE, max_credits=APOLLO_MAX_CREDITS,
        )
        logger.info(f"Apollo enrichment: {apollo_stats}")

        # 5. Summary
        contact_count = await session.execute(
            select(func.count()).select_from(ExtractedContact)
            .join(DiscoveredCompany)
            .where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.company_id == COMPANY_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        total_contacts = contact_count.scalar() or 0

        email_count = await session.execute(
            select(func.count()).select_from(ExtractedContact)
            .join(DiscoveredCompany)
            .where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.company_id == COMPANY_ID,
                DiscoveredCompany.is_target == True,
                ExtractedContact.email.isnot(None),
            )
        )
        total_emails = email_count.scalar() or 0

        logger.info("=" * 60)
        logger.info(f"SUMMARY — Archistruct Contact Extraction (project {PROJECT_ID})")
        logger.info(f"  Targets processed: {len(targets)}")
        logger.info(f"  Crona scrapes: {crona_service.credits_used} credits")
        logger.info(f"  Website contacts: {extract_stats.get('contacts_found', 0)} (GPT + regex)")
        logger.info(f"  Apollo people: {apollo_stats.get('people_found', 0)} (credits: {apollo_stats.get('credits_used', 0)})")
        logger.info(f"  Total extracted contacts: {total_contacts}")
        logger.info(f"  Contacts with email: {total_emails}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
