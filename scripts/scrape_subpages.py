"""
Scrape contact/about/team subpages for Deliryo targets with zero contacts.
Uses Crona API for JS-rendered scraping, then GPT contact extraction.

Run on Hetzner:
docker run -d --name scrape-subpages --network repo_default \
  -v ~/magnum-opus-project/repo/backend:/app \
  -v ~/magnum-opus-project/repo/scripts:/scripts \
  -e DATABASE_URL=... -e OPENAI_API_KEY=... -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \
  python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/scrape_subpages.py'
"""
import asyncio
import json
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Subpage paths to try, ordered by yield from test run
# /contacts recovered 8/20 in test; /contact, /about, /kontakty are backup
SUBPAGE_PATHS = [
    "/contacts",
    "/contact",
    "/kontakty",       # Russian transliteration
    "/about",
]

PROJECT_ID = 18
COMPANY_ID = 1
BATCH_SIZE = 50  # Crona batch size
TEST_LIMIT = None  # Full run — all 654 zero-contact targets


async def get_zero_contact_domains():
    """Load all target domains with zero contacts."""
    from app.db import async_session_maker
    from sqlalchemy import text as sql_text

    async with async_session_maker() as session:
        result = await session.execute(sql_text("""
            SELECT dc.id, dc.domain, dc.name
            FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true AND dc.contacts_count = 0
            ORDER BY dc.confidence DESC
        """), {"pid": PROJECT_ID})
        rows = result.fetchall()
        logger.info(f"Found {len(rows)} zero-contact targets")
        return [(r.id, r.domain, r.name) for r in rows]


async def scrape_subpages_batch(domains_with_paths: list[tuple[str, str]]) -> dict[str, str]:
    """Scrape a batch of (domain, full_url) pairs via Crona. Returns {domain: text}."""
    from app.services.crona_service import crona_service

    # Crona accepts full URLs, returns keys as url stripped of https://
    urls = [url for _, url in domains_with_paths]
    # Build reverse map: "domain.com/contacts" -> "domain.com"
    url_to_domain = {}
    for domain, url in domains_with_paths:
        key = url.replace("https://", "").replace("http://", "").rstrip("/")
        url_to_domain[key] = domain
        url_to_domain[url] = domain  # also map full URL

    try:
        results = await crona_service.scrape_domains(urls)
        # Map back to original base domains
        output = {}
        for returned_key, text in results.items():
            clean_key = returned_key.replace("https://", "").replace("http://", "").rstrip("/")
            domain = url_to_domain.get(clean_key) or url_to_domain.get(returned_key)
            if not domain:
                # Try stripping path
                domain = clean_key.split("/")[0]
            if text and len(text.strip()) > 50:
                if domain in output:
                    output[domain] += "\n\n---SUBPAGE---\n\n" + text
                else:
                    output[domain] = text
        return output
    except Exception as e:
        logger.error(f"Crona batch scrape failed: {e}")
        return {}


async def extract_contacts_from_text(domain: str, text: str) -> list[dict]:
    """Extract contacts using GPT-4o-mini."""
    from app.services.contact_extraction_service import contact_extraction_service

    contacts = await contact_extraction_service.extract_contacts_from_html(domain, text)
    # Also try regex fallback
    regex_emails = contact_extraction_service.extract_emails_regex(text)
    regex_phones = contact_extraction_service.extract_phones_regex(text)

    # Merge regex findings not already in GPT results
    gpt_emails = {c.get("email", "").lower() for c in contacts if c.get("email")}
    for email in regex_emails:
        if email.lower() not in gpt_emails:
            contacts.append({
                "email": email,
                "phone": None,
                "first_name": None,
                "last_name": None,
                "job_title": None,
                "confidence": 0.4,
                "is_generic": any(email.lower().startswith(p) for p in [
                    "info@", "support@", "contact@", "hello@", "office@", "mail@",
                ]),
            })

    return contacts


async def save_contacts(dc_id: int, domain: str, contacts: list[dict]):
    """Save extracted contacts to DB."""
    from app.db import async_session_maker
    from app.models.pipeline import ExtractedContact, ContactSource
    from app.models.domain import ProjectSearchKnowledge
    from app.services.contact_extraction_service import is_valid_email
    from sqlalchemy import select, update

    async with async_session_maker() as session:
        saved = 0
        emails = []
        phones = []

        for c in contacts:
            email = c.get("email")
            if email and not is_valid_email(email):
                continue

            ec = ExtractedContact(
                discovered_company_id=dc_id,
                email=email,
                phone=c.get("phone"),
                first_name=c.get("first_name"),
                last_name=c.get("last_name"),
                job_title=c.get("job_title"),
                source=ContactSource.WEBSITE_SCRAPE,
                is_verified=False,
            )
            session.add(ec)
            saved += 1
            if email:
                emails.append(email)
            if c.get("phone"):
                phones.append(c["phone"])

        if saved > 0:
            # Update discovered company
            from app.models.pipeline import DiscoveredCompany
            result = await session.execute(
                select(DiscoveredCompany).where(DiscoveredCompany.id == dc_id)
            )
            dc = result.scalar_one_or_none()
            if dc:
                dc.contacts_count = (dc.contacts_count or 0) + saved
                dc.emails_found = list(set((dc.emails_found or []) + emails))
                dc.phones_found = list(set((dc.phones_found or []) + phones))

            await session.commit()

        return saved


async def main():
    # Load targets
    targets = await get_zero_contact_domains()
    if TEST_LIMIT:
        targets = targets[:TEST_LIMIT]
        logger.info(f"TEST MODE: limited to {TEST_LIMIT} domains")

    logger.info(f"Processing {len(targets)} zero-contact targets")

    total_contacts_found = 0
    total_domains_with_contacts = 0
    total_domains_processed = 0
    total_crona_credits = 0

    # Process in batches
    # For each batch of domains, try subpages one path at a time
    # Start with /contacts (highest yield), then /about, etc.
    # Skip domain once we find contacts for it
    remaining = {dc_id: (domain, name) for dc_id, domain, name in targets}

    for path_idx, subpage_path in enumerate(SUBPAGE_PATHS):
        if not remaining:
            break

        logger.info(f"\n=== Subpage path: {subpage_path} ({len(remaining)} domains remaining) ===")

        # Build URLs for this subpage path
        domain_list = list(remaining.items())

        for batch_start in range(0, len(domain_list), BATCH_SIZE):
            batch = domain_list[batch_start:batch_start + BATCH_SIZE]
            if not batch:
                break

            # Build (domain, url) pairs
            pairs = []
            dc_id_map = {}
            for dc_id, (domain, name) in batch:
                url = f"https://{domain}{subpage_path}"
                pairs.append((domain, url))
                dc_id_map[domain] = dc_id

            logger.info(f"Scraping {len(pairs)} URLs for {subpage_path} (batch {batch_start // BATCH_SIZE + 1})")
            total_crona_credits += len(pairs)

            # Scrape
            scraped = await scrape_subpages_batch(pairs)
            logger.info(f"Got text for {len(scraped)} / {len(pairs)} domains")

            # Extract contacts from scraped text
            batch_contacts = 0
            batch_domains_with = 0
            for domain, text in scraped.items():
                dc_id = dc_id_map.get(domain)
                if not dc_id:
                    continue

                contacts = await extract_contacts_from_text(domain, text)
                if contacts:
                    saved = await save_contacts(dc_id, domain, contacts)
                    if saved > 0:
                        logger.info(f"  {domain}: {saved} contacts extracted from {subpage_path}")
                        batch_contacts += saved
                        batch_domains_with += 1
                        # Remove from remaining — we got contacts
                        remaining.pop(dc_id, None)

                total_domains_processed += 1

            total_contacts_found += batch_contacts
            total_domains_with_contacts += batch_domains_with
            logger.info(f"Batch result: {batch_contacts} contacts from {batch_domains_with} domains")

            # Small delay between batches
            await asyncio.sleep(2)

        logger.info(f"After {subpage_path}: {len(remaining)} domains still have 0 contacts")

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"SUBPAGE SCRAPING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Domains processed: {total_domains_processed}")
    logger.info(f"Domains with new contacts: {total_domains_with_contacts}")
    logger.info(f"Total contacts extracted: {total_contacts_found}")
    logger.info(f"Crona credits used: {total_crona_credits}")
    logger.info(f"Domains still with 0 contacts: {len(remaining)}")
    logger.info(f"Hit rate: {100 * total_domains_with_contacts / max(len(targets), 1):.1f}%")

    # Log remaining domains
    if remaining and len(remaining) <= 50:
        logger.info(f"\nRemaining zero-contact domains:")
        for dc_id, (domain, name) in remaining.items():
            logger.info(f"  {domain} ({name})")


if __name__ == "__main__":
    asyncio.run(main())
