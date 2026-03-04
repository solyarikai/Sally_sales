"""
Segment Classification Pipeline

Classifies contacts into business segments using website scraping (Crona)
and GPT-4o-mini analysis. Stores results in contact.segment and
contact.platform_state.classification.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.services.crona_service import crona_service
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM_PROMPT = """You are a B2B business analyst. Given a company's website content and metadata,
classify it into a business segment and industry.

Respond with ONLY valid JSON:
{
  "business_segment": "one of: SaaS, Fintech, E-commerce, Gaming, Media, Marketplace, Crypto/Web3, HealthTech, EdTech, AgriTech, PropTech, HRTech, LegalTech, Travel, Logistics, IoT, Cybersecurity, AI/ML, Telecom, Energy, Manufacturing, Consulting, Agency, Other",
  "industry": "specific industry like Payment Processing, Creator Economy, Online Retail, etc.",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "confidence": 0.0-1.0
}"""


def _build_classification_prompt(
    company_name: str,
    domain: Optional[str],
    job_title: Optional[str],
    website_text: Optional[str],
) -> str:
    parts = [f"Company: {company_name}"]
    if domain:
        parts.append(f"Website: {domain}")
    if job_title:
        parts.append(f"Contact's role: {job_title}")
    if website_text:
        # Truncate to ~2000 chars to keep token costs low
        truncated = website_text[:2000]
        parts.append(f"\nWebsite content:\n{truncated}")
    else:
        parts.append("\n(No website content available — classify based on company name and domain only)")
    return "\n".join(parts)


async def classify_contacts_for_project(
    session: AsyncSession,
    project_id: int,
    statuses: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Batch classify all contacts for a project.
    Returns progress dict: { total, classified, skipped, errors }
    """
    if statuses is None:
        statuses = ["qualified", "warm", "lead", "touched"]

    # Fetch contacts that need classification
    stmt = select(Contact).where(
        and_(
            Contact.project_id == project_id,
            Contact.status.in_(statuses),
            Contact.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    contacts = list(result.scalars().all())

    if not contacts:
        return {"total": 0, "classified": 0, "skipped": 0, "errors": 0}

    # Collect unique domains for batch scraping
    domain_contacts: Dict[str, List[Contact]] = {}
    no_domain: List[Contact] = []

    for c in contacts:
        domain = c.domain
        if not domain:
            # Try extracting from email
            if c.email and '@' in c.email:
                email_domain = c.email.split('@')[1].lower()
                if email_domain not in ('gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'mail.ru', 'yandex.ru'):
                    domain = email_domain
        if domain:
            domain_contacts.setdefault(domain, []).append(c)
        else:
            no_domain.append(c)

    # Scrape websites via Crona (rate limited: batches of 20)
    scraped: Dict[str, Optional[str]] = {}
    all_domains = list(domain_contacts.keys())

    if all_domains:
        batch_size = 20
        for i in range(0, len(all_domains), batch_size):
            batch = all_domains[i:i + batch_size]
            try:
                batch_results = await crona_service.scrape_domains(batch, timeout=180)
                scraped.update(batch_results)
            except Exception as e:
                logger.error(f"Crona scrape batch failed: {e}")
                for d in batch:
                    scraped[d] = None
            # Rate limit between batches
            if i + batch_size < len(all_domains):
                await asyncio.sleep(2)

    # Classify each contact via GPT-4o-mini
    classified = 0
    skipped = 0
    errors = 0

    async def classify_one(contact: Contact, website_text: Optional[str] = None):
        nonlocal classified, skipped, errors

        company = contact.company_name or contact.domain or ""
        if not company:
            skipped += 1
            return

        prompt = _build_classification_prompt(
            company_name=company,
            domain=contact.domain,
            job_title=contact.job_title,
            website_text=website_text,
        )

        try:
            response = await openai_service.complete(
                prompt=prompt,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=200,
                response_format={"type": "json_object"},
            )

            import json
            data = json.loads(response)

            # Update contact
            contact.segment = data.get("business_segment", "Other")

            # Store full classification in platform_state
            ps = dict(contact.platform_state or {})
            ps["classification"] = {
                "business_segment": data.get("business_segment"),
                "industry": data.get("industry"),
                "keywords": data.get("keywords", []),
                "confidence": data.get("confidence", 0),
                "classified_at": datetime.now(timezone.utc).isoformat(),
            }
            contact.platform_state = ps

            classified += 1

        except Exception as e:
            logger.error(f"Classification failed for contact {contact.id}: {e}")
            errors += 1

    # Process contacts with domains
    tasks = []
    for domain, contacts_list in domain_contacts.items():
        text = scraped.get(domain)
        for c in contacts_list:
            tasks.append(classify_one(c, text))

    # Process contacts without domains
    for c in no_domain:
        tasks.append(classify_one(c, None))

    # Run classifications with concurrency limit
    sem = asyncio.Semaphore(5)

    async def limited(coro):
        async with sem:
            await coro

    await asyncio.gather(*[limited(t) for t in tasks])

    # Commit all changes
    await session.commit()

    return {
        "total": len(contacts),
        "classified": classified,
        "skipped": skipped,
        "errors": errors,
        "domains_scraped": len([d for d, t in scraped.items() if t]),
    }
