#!/usr/bin/env python3
"""Find up to 3 C-level contacts per verified target company via Apollo.
Uses enrich_by_domain(domain, limit=3, titles=[...]).
Costs ~1 credit per person found. Stores in company_info.contacts."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

TITLES = [
    'CEO', 'Founder', 'Co-Founder', 'Owner',
    'COO', 'CFO', 'Managing Director',
    'Head of Finance', 'VP Operations', 'VP Finance',
    'General Manager',
]
MAX_CONTACTS = 3


async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone

    await init_db()

    # Get verified targets without contacts
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.is_target == True,
            )
        )
        all_targets = result.scalars().all()

    # Filter out ones that already have contacts
    targets = []
    for t in all_targets:
        info = t.company_info or {}
        if not info.get('contacts'):
            targets.append(t)

    total = len(targets)
    print(f"Finding contacts for {total} verified targets (max {MAX_CONTACTS} per company)")

    found_total = 0
    companies_with_contacts = 0
    errors = 0
    start_time = time.time()

    sem = asyncio.Semaphore(5)  # Conservative rate limiting

    async def find_for(company):
        nonlocal found_total, companies_with_contacts, errors
        async with sem:
            try:
                people = await apollo_service.enrich_by_domain(
                    domain=company.domain,
                    limit=MAX_CONTACTS,
                    titles=TITLES,
                )

                if people:
                    contacts = []
                    for p in people[:MAX_CONTACTS]:
                        contacts.append({
                            'name': f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                            'email': p.get('email', ''),
                            'title': p.get('job_title', ''),
                            'linkedin_url': p.get('linkedin_url', ''),
                            'phone': p.get('phone', ''),
                            'is_verified': p.get('is_verified', False),
                        })

                    async with async_session_maker() as s:
                        dc = await s.get(DiscoveredCompany, company.id)
                        info = dc.company_info or {}
                        info['contacts'] = contacts
                        info['contacts_found_at'] = datetime.now(timezone.utc).isoformat()
                        dc.company_info = info
                        flag_modified(dc, 'company_info')
                        await s.commit()

                    found_total += len(contacts)
                    companies_with_contacts += 1

                await asyncio.sleep(0.3)  # Rate limit

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error for {company.domain}: {e}")

            processed = companies_with_contacts + errors
            if processed % 100 == 0 and processed > 0:
                rate = processed / max(1, time.time() - start_time) * 60
                print(f"  Progress: {processed}/{total} | Contacts: {found_total} | Rate: {rate:.0f}/min | Credits: {apollo_service.credits_used}")

    # Process in batches
    for i in range(0, total, 50):
        batch = targets[i:i+50]
        await asyncio.gather(*[find_for(t) for t in batch])
        rate = (companies_with_contacts + errors) / max(1, time.time() - start_time) * 60
        print(f"  Batch {i//50+1}: {companies_with_contacts}/{total} with contacts | {found_total} total contacts | {rate:.0f}/min | Credits: {apollo_service.credits_used}")

    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed/60:.1f}min")
    print(f"  Companies with contacts: {companies_with_contacts}/{total}")
    print(f"  Total contacts found: {found_total}")
    print(f"  Avg contacts/company: {found_total/max(1,companies_with_contacts):.1f}")
    print(f"  Credits used: {apollo_service.credits_used}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
