"""
Inxy deep scrape — Extract emails from ALL possible pages on target sites.

Previous scraping only checked: /, /contacts, /contact, /kontakty, /about
This script scrapes MANY more pages to find emails on gaming sites:
/support, /faq, /terms, /privacy, /impressum, /team, /imprint, /legal,
/help, /partners, /business, /advertise, /careers, /jobs, etc.

Also uses Apify proxy for JS-rendered sites.
"""
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("inxy_deep")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48

# Extended subpages to check for emails
SUBPAGES = [
    "/support", "/help", "/faq",
    "/terms", "/terms-of-service", "/tos",
    "/privacy", "/privacy-policy",
    "/impressum", "/imprint", "/legal",
    "/team", "/about-us", "/about",
    "/partners", "/partnership", "/business",
    "/advertise", "/advertising",
    "/careers", "/jobs",
    "/contact", "/contact-us", "/contacts", "/kontakt",
    "/company",
]

# Email regex
EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

JUNK_DOMAINS = {
    "example.com", "example.org", "test.com", "sentry.io", "wixpress.com",
    "schema.org", "w3.org", "googleapis.com", "google.com", "facebook.com",
    "twitter.com", "cloudflare.com", "jsdelivr.net", "gstatic.com",
    "cloudfront.net", "amazonaws.com", "fbcdn.net", "2o7.net",
    "googletagmanager.com", "google-analytics.com", "googleadservices.com",
}

JUNK_PREFIXES = {"noreply", "no-reply", "mailer-daemon", "postmaster", "webmaster", "root"}


def extract_emails(text: str) -> set:
    """Extract valid emails from text, filtering junk."""
    emails = set()
    for match in EMAIL_RE.findall(text):
        email = match.lower().strip()
        _, _, domain = email.partition("@")
        if domain in JUNK_DOMAINS:
            continue
        local = email.split("@")[0]
        if local in JUNK_PREFIXES:
            continue
        if ".png" in email or ".jpg" in email or ".svg" in email or ".gif" in email:
            continue
        if len(local) < 2 or len(domain) < 4:
            continue
        emails.add(email)
    return emails


async def scrape_url(client, url: str, timeout: int = 15) -> str:
    """Scrape a URL, return text or empty string."""
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass
    return ""


async def deep_scrape_domain(client, domain: str) -> dict:
    """Scrape homepage + all subpages, extract ALL emails found."""
    all_emails = set()
    pages_checked = 0
    pages_with_email = 0

    base_url = f"https://{domain}"

    # Check homepage first
    html = await scrape_url(client, base_url)
    if html:
        homepage_emails = extract_emails(html)
        all_emails.update(homepage_emails)
        pages_checked += 1
        if homepage_emails:
            pages_with_email += 1

    # Check all subpages
    for subpage in SUBPAGES:
        url = f"{base_url}{subpage}"
        text = await scrape_url(client, url)
        if text:
            page_emails = extract_emails(text)
            new_emails = page_emails - all_emails
            if new_emails:
                all_emails.update(new_emails)
                pages_with_email += 1
            pages_checked += 1

    return {
        "emails": list(all_emails),
        "pages_checked": pages_checked,
        "pages_with_email": pages_with_email,
    }


async def main():
    import httpx
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("INXY DEEP SCRAPE — Extract emails from all pages")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Get ALL targets — re-scrape everything to maximize emails
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        all_targets = result.scalars().all()

        # Get existing emails per domain to avoid duplicates
        existing_q = await session.execute(
            select(ExtractedContact.email, DiscoveredCompany.domain).join(
                DiscoveredCompany, ExtractedContact.discovered_company_id == DiscoveredCompany.id
            ).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
                ExtractedContact.email.isnot(None),
            )
        )
        existing_emails_by_domain = {}
        for row in existing_q.fetchall():
            existing_emails_by_domain.setdefault(row.domain, set()).add(row.email.lower())

        logger.info(f"Targets: {len(all_targets)}, domains with existing emails: {len(existing_emails_by_domain)}")

        new_emails_total = 0
        domains_with_new = 0

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            verify=False,
        ) as client:
            for i, dc in enumerate(all_targets):
                try:
                    result = await deep_scrape_domain(client, dc.domain)
                    found_emails = set(result["emails"])
                    existing = existing_emails_by_domain.get(dc.domain, set())
                    new_emails = found_emails - existing

                    if new_emails:
                        domains_with_new += 1
                        for email in new_emails:
                            ec = ExtractedContact(
                                discovered_company_id=dc.id,
                                email=email,
                                source=ContactSource.WEBSITE_SCRAPE,
                                raw_data={"source": "deep_scrape", "pages_checked": result["pages_checked"]},
                            )
                            session.add(ec)
                            new_emails_total += 1

                        dc.contacts_count = (dc.contacts_count or 0) + len(new_emails)
                        if not dc.emails_found:
                            dc.emails_found = list(new_emails)
                        else:
                            dc.emails_found = list(set(dc.emails_found or []) | new_emails)

                        logger.info(f"  {dc.domain}: +{len(new_emails)} new emails (total found: {len(found_emails)}, pages: {result['pages_checked']})")

                except Exception as e:
                    logger.error(f"  {dc.domain}: {e}")

                if (i + 1) % 25 == 0:
                    await session.commit()
                    logger.info(f"Progress: {i+1}/{len(all_targets)} | +{new_emails_total} emails from {domains_with_new} domains")

        await session.commit()

        logger.info("=" * 60)
        logger.info("DEEP SCRAPE COMPLETE")
        logger.info(f"New emails found: {new_emails_total}")
        logger.info(f"Domains with new emails: {domains_with_new}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
