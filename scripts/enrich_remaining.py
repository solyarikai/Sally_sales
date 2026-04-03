#!/usr/bin/env python3
"""Enrich remaining targets that don't have contacts yet.
Priority: DIGITAL_AGENCY > MARKETING_AGENCY > CREATIVE_STUDIO > MEDIA_PRODUCTION.
Budget: ~2,100 credits remaining."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

TITLES = [
    'CEO', 'Founder', 'Co-Founder', 'Owner',
    'COO', 'CFO', 'Managing Director',
    'Head of Finance', 'VP Operations',
]
MAX_CONTACTS = 3
MAX_CREDITS = 2000  # Stop before exhausting


async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select, text
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone

    await init_db()

    # Get clean targets without contacts, prioritized by best segments
    async with async_session_maker() as s:
        result = await s.execute(text("""
            SELECT id, domain, matched_segment FROM discovered_companies
            WHERE project_id = 9 AND is_target = true
              AND (in_active_campaign IS NULL OR in_active_campaign = false)
              AND company_info::text NOT LIKE '%contacts%'
            ORDER BY CASE matched_segment
              WHEN 'DIGITAL_AGENCY' THEN 1
              WHEN 'MARKETING_AGENCY' THEN 2
              WHEN 'CREATIVE_STUDIO' THEN 3
              WHEN 'MEDIA_PRODUCTION' THEN 4
              WHEN 'SOFTWARE_HOUSE' THEN 5
              ELSE 6 END,
              id
        """))
        targets = result.all()

    total = len(targets)
    print(f"Enriching {total} remaining targets (budget: {MAX_CREDITS} credits)")

    found_total = 0
    enriched = 0
    errors = 0
    start_time = time.time()

    sem = asyncio.Semaphore(3)  # Conservative to avoid 429s

    async def find_for(company_id, domain):
        nonlocal found_total, enriched, errors
        if apollo_service.credits_used >= MAX_CREDITS:
            return

        async with sem:
            try:
                people = await apollo_service.enrich_by_domain(
                    domain=domain, limit=MAX_CONTACTS, titles=TITLES,
                )
                if people:
                    contacts = [{'name': f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
                                 'email': p.get('email',''), 'title': p.get('job_title',''),
                                 'linkedin_url': p.get('linkedin_url',''),
                                 'is_verified': p.get('is_verified', False)}
                                for p in people[:MAX_CONTACTS]]
                    async with async_session_maker() as s:
                        dc = await s.get(DiscoveredCompany, company_id)
                        info = dc.company_info or {}
                        info['contacts'] = contacts
                        info['contacts_found_at'] = datetime.now(timezone.utc).isoformat()
                        dc.company_info = info
                        flag_modified(dc, 'company_info')
                        await s.commit()
                    found_total += len(contacts)
                    enriched += 1
                await asyncio.sleep(0.4)
            except Exception:
                errors += 1

            if (enriched + errors) % 50 == 0 and (enriched + errors) > 0:
                print(f"  {enriched}/{total} enriched | {found_total} contacts | Credits: {apollo_service.credits_used}/{MAX_CREDITS}")

    for i in range(0, total, 30):
        if apollo_service.credits_used >= MAX_CREDITS:
            print(f"  Budget exhausted at {apollo_service.credits_used} credits")
            break
        batch = targets[i:i+30]
        await asyncio.gather(*[find_for(t.id, t.domain) for t in batch])

    print(f"\nDONE: {enriched} enriched, {found_total} contacts, {apollo_service.credits_used} credits, {errors} errors")


if __name__ == "__main__":
    asyncio.run(main())
