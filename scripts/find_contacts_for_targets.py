#!/usr/bin/env python3
"""Find up to 3 decision-maker contacts per target company via Apollo People UI scraper.

Uses apollo_scraper.js with organizationDomains[] filter.
Batches 30 domains at a time. Saves to extracted_contacts table.
Zero Apollo credits — Puppeteer UI scraping only.
"""
import sys
import os
import json
import asyncio
import tempfile
import logging
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

SCRAPER_SCRIPT = Path('/app/../scripts/apollo_scraper.js')
if not SCRAPER_SCRIPT.exists():
    SCRAPER_SCRIPT = Path(os.path.dirname(__file__)) / 'apollo_scraper.js'

# Priority roles for EasyStaff — decision makers who manage freelancer payments
TARGET_TITLES = [
    'CEO', 'Founder', 'Co-Founder', 'Managing Director',
    'COO', 'CFO', 'CTO', 'CMO',
    'VP Operations', 'VP Finance', 'Head of Operations',
    'Director', 'General Manager',
    'HR Director', 'Head of HR', 'People Operations',
]

BATCH_SIZE = 30  # Apollo supports up to ~30 domains per search URL
MAX_PAGES = 3    # 3 pages × 25 results = up to 75 people per batch


async def scrape_batch(batch_domains, batch_idx, total_batches):
    """Scrape Apollo People for a batch of domains."""

    # Build Apollo People search URL
    url = "https://app.apollo.io/#/people?finderViewId=5b8050d050a0710001ca27c1"
    for d in batch_domains:
        url += f"&organizationDomains[]={quote(d)}"
    for t in TARGET_TITLES[:8]:  # Top 8 titles to keep URL manageable
        url += f"&personTitles[]={quote(t)}"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, prefix=f'contacts_batch{batch_idx}_') as tf:
        output_file = tf.name

    args = ["node", str(SCRAPER_SCRIPT), "--url", url, "--max-pages", str(MAX_PAGES), "--output", output_file]

    try:
        logger.info(f"Batch {batch_idx+1}/{total_batches}: {len(batch_domains)} domains")
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRAPER_SCRIPT.parent.parent),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode != 0:
            logger.warning(f"Batch {batch_idx+1} failed: {stderr.decode()[:200]}")
            return []

        if Path(output_file).exists():
            with open(output_file) as f:
                people = json.load(f)
            logger.info(f"Batch {batch_idx+1}: {len(people)} contacts found")
            return people
        return []

    except asyncio.TimeoutError:
        logger.warning(f"Batch {batch_idx+1} timed out")
        return []
    except Exception as e:
        logger.warning(f"Batch {batch_idx+1} error: {e}")
        return []
    finally:
        try:
            Path(output_file).unlink(missing_ok=True)
        except:
            pass


async def main():
    from app.db import async_session_maker, init_db
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from app.models.gathering import GatheringRun
    from sqlalchemy import select, update

    await init_db()

    # Get target domains
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.contacts_count == 0,
                DiscoveredCompany.domain.notlike('%_apollo_%'),
                DiscoveredCompany.domain.isnot(None),
            )
        )
        targets = result.all()

    logger.info(f"Finding contacts for {len(targets)} target companies")

    domains = [t.domain for t in targets]
    domain_to_id = {t.domain: t.id for t in targets}

    # Batch domains
    batches = [domains[i:i+BATCH_SIZE] for i in range(0, len(domains), BATCH_SIZE)]

    all_people = []
    for i, batch in enumerate(batches):
        people = await scrape_batch(batch, i, len(batches))
        all_people.extend(people)
        # Rate limit between batches
        await asyncio.sleep(5)

    logger.info(f"Total contacts found: {len(all_people)}")

    # Save to database
    async with async_session_maker() as s:
        saved = 0
        for person in all_people:
            company = person.get('company', '')
            domain = ''

            # Match person to target domain
            for d in domains:
                if d.lower() in company.lower() or company.lower() in d.lower():
                    domain = d
                    break

            # Also try matching by email domain
            email = person.get('email', '')
            if not domain and email and '@' in email:
                email_domain = email.split('@')[1].lower()
                if email_domain in domain_to_id:
                    domain = email_domain

            if not domain:
                continue

            dc_id = domain_to_id.get(domain)
            if not dc_id:
                continue

            # Check for existing contact
            name = person.get('name', '')
            existing = await s.execute(
                select(ExtractedContact).where(
                    ExtractedContact.discovered_company_id == dc_id,
                    ExtractedContact.first_name == name.split(' ')[0] if name else '',
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Check max 3 contacts per company
            count_result = await s.execute(
                select(ExtractedContact).where(
                    ExtractedContact.discovered_company_id == dc_id
                )
            )
            if len(count_result.scalars().all()) >= 3:
                continue

            parts = name.split(' ', 1)
            contact = ExtractedContact(
                discovered_company_id=dc_id,
                first_name=parts[0] if parts else '',
                last_name=parts[1] if len(parts) > 1 else '',
                job_title=person.get('title', ''),
                email=email if email and 'email_not_unlocked' not in email else None,
                linkedin_url=person.get('linkedin_url', ''),
                source=ContactSource.APOLLO,
                raw_data=person,
            )
            s.add(contact)
            saved += 1

            if saved % 50 == 0:
                await s.commit()
                logger.info(f"Saved {saved} contacts")

        # Update contacts_count on discovered companies
        for domain, dc_id in domain_to_id.items():
            count = await s.execute(
                select(ExtractedContact).where(ExtractedContact.discovered_company_id == dc_id)
            )
            contacts = count.scalars().all()
            if contacts:
                await s.execute(
                    update(DiscoveredCompany).where(DiscoveredCompany.id == dc_id)
                    .values(contacts_count=len(contacts))
                )

        await s.commit()
        logger.info(f"DONE: {saved} contacts saved for {len(targets)} target companies")


if __name__ == "__main__":
    asyncio.run(main())
