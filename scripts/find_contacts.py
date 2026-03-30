#!/usr/bin/env python3
"""Find up to 3 decision-maker contacts per verified target company via Apollo People Search.
Costs 1 credit per company search. Stores contacts in DB."""
import sys
import asyncio
import json
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

# Priority titles — search in this order, take first 3 found
TITLE_PRIORITIES = [
    'CEO', 'Founder', 'Co-Founder', 'Owner',
    'COO', 'CFO', 'Managing Director',
    'Head of Finance', 'VP Operations', 'VP Finance',
    'Director of Operations', 'Director of Finance',
    'General Manager',
]

MAX_CONTACTS_PER_COMPANY = 3


async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select, update
    from datetime import datetime, timezone

    await init_db()

    # Get all verified target companies that don't have contacts yet
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain, DiscoveredCompany.name).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.domain.isnot(None),
                DiscoveredCompany.domain != '',
            )
        )
        targets = result.all()

    # Filter out companies that already have contacts in company_info
    need_contacts = []
    async with async_session_maker() as s:
        for t in targets:
            dc = await s.get(DiscoveredCompany, t.id)
            info = dc.company_info or {}
            if not info.get('contacts'):
                need_contacts.append(t)

    total = len(need_contacts)
    print(f"Finding contacts for {total} target companies (max {MAX_CONTACTS_PER_COMPANY} per company)")
    print(f"Estimated credits: {total}")

    found_total = 0
    errors = 0
    credits_used = 0
    start_time = time.time()

    sem = asyncio.Semaphore(10)  # Conservative — Apollo rate limits

    async def find_contacts_for(company):
        nonlocal found_total, errors, credits_used
        async with sem:
            try:
                # Search Apollo People by company domain + title keywords
                r = await apollo_service.search_people(
                    organization_domains=[company.domain],
                    person_titles=TITLE_PRIORITIES[:7],  # Top 7 titles
                    page=1, per_page=10
                )
                credits_used += 1

                if not r or not r.get('people'):
                    return

                people = r['people'][:MAX_CONTACTS_PER_COMPANY]
                contacts = []
                for p in people:
                    contact = {
                        'name': f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        'title': p.get('title', ''),
                        'email': p.get('email', ''),
                        'linkedin_url': p.get('linkedin_url', ''),
                        'phone': p.get('phone_numbers', [{}])[0].get('sanitized_number', '') if p.get('phone_numbers') else '',
                        'apollo_id': p.get('id', ''),
                    }
                    contacts.append(contact)

                if contacts:
                    async with async_session_maker() as s:
                        dc = await s.get(DiscoveredCompany, company.id)
                        info = dc.company_info or {}
                        info['contacts'] = contacts
                        info['contacts_found_at'] = datetime.now(timezone.utc).isoformat()
                        dc.company_info = info
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(dc, 'company_info')
                        await s.commit()

                    found_total += len(contacts)

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error for {company.domain}: {e}")

            if (credits_used) % 100 == 0:
                rate = credits_used / max(1, time.time() - start_time) * 60
                print(f"  Progress: {credits_used}/{total} | Contacts found: {found_total} | Rate: {rate:.0f}/min | Errors: {errors}")

    # Process in batches of 50
    for i in range(0, total, 50):
        batch = need_contacts[i:i+50]
        await asyncio.gather(*[find_contacts_for(c) for c in batch])
        rate = credits_used / max(1, time.time() - start_time) * 60
        print(f"  Batch {i//50 + 1}: {credits_used}/{total} credits | {found_total} contacts | {rate:.0f}/min")

    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed/60:.1f}min")
    print(f"  Credits used: {credits_used}")
    print(f"  Contacts found: {found_total}")
    print(f"  Avg contacts per company: {found_total/max(1,credits_used):.1f}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(main())
