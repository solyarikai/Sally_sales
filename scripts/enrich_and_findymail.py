#!/usr/bin/env python3
"""
Step 1: Re-enrich companies with 1-2 contacts (broader titles) via Apollo
Step 2: FindyMail verification for unverified emails
Tracks email_source in company_info: 'apollo' or 'findymail'
"""
import sys, asyncio, logging, time, json
sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

TITLES_BROAD = [
    'CEO', 'Founder', 'Co-Founder', 'Owner', 'COO', 'CFO',
    'Managing Director', 'Head of Finance', 'VP Operations',
    'VP Marketing', 'Director', 'Partner', 'General Manager',
    'Head of Operations', 'Chief Revenue Officer',
]
MAX_APOLLO_CREDITS = 1300  # Save some for safety


async def step1_apollo_fill():
    """Fill companies with 1-2 contacts to 3."""
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone

    await init_db()

    # Get companies with 1-2 contacts
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.contacts_count.in_([1, 2]),
            )
        )
        targets = result.scalars().all()

    total = len(targets)
    print(f"\n=== STEP 1: Apollo fill {total} companies (1-2 contacts) to 3 ===")

    enriched = found = 0
    sem = asyncio.Semaphore(3)

    async def fill(dc):
        nonlocal enriched, found
        if apollo_service.credits_used >= MAX_APOLLO_CREDITS:
            return
        async with sem:
            try:
                existing = (dc.company_info or {}).get('contacts', [])
                need = 3 - len(existing)
                if need <= 0:
                    return

                people = await apollo_service.enrich_by_domain(
                    domain=dc.domain, limit=3 + len(existing), titles=TITLES_BROAD,
                )
                if not people:
                    return

                existing_emails = {c.get('email', '').lower() for c in existing if c.get('email')}
                new_contacts = []
                for p in people:
                    email = (p.get('email') or '').lower()
                    if email and email not in existing_emails:
                        new_contacts.append({
                            'name': f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
                            'email': p.get('email', ''),
                            'title': p.get('job_title', ''),
                            'linkedin_url': p.get('linkedin_url', ''),
                            'is_verified': p.get('is_verified', False),
                            'email_source': 'apollo',
                        })
                        if len(new_contacts) >= need:
                            break

                if new_contacts:
                    # Tag existing contacts with source
                    for c in existing:
                        if 'email_source' not in c:
                            c['email_source'] = 'apollo'

                    async with async_session_maker() as s:
                        dc2 = await s.get(DiscoveredCompany, dc.id)
                        info = dc2.company_info or {}
                        info['contacts'] = existing + new_contacts
                        info['contacts_updated_at'] = datetime.now(timezone.utc).isoformat()
                        dc2.company_info = info
                        dc2.contacts_count = len(existing) + len(new_contacts)
                        flag_modified(dc2, 'company_info')
                        await s.commit()
                    found += len(new_contacts)
                    enriched += 1

                await asyncio.sleep(0.4)
            except Exception:
                pass

            if (enriched) % 50 == 0 and enriched > 0:
                print(f"  Apollo: {enriched}/{total} | +{found} contacts | {apollo_service.credits_used} credits")

    for i in range(0, total, 30):
        if apollo_service.credits_used >= MAX_APOLLO_CREDITS:
            print(f"  Apollo budget hit: {apollo_service.credits_used}")
            break
        batch = targets[i:i+30]
        await asyncio.gather(*[fill(t) for t in batch])

    print(f"  Apollo DONE: {enriched} companies filled, +{found} new contacts, {apollo_service.credits_used} credits")
    return found


async def step2_findymail():
    """Verify unverified emails via FindyMail."""
    from app.db import async_session_maker, init_db
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone
    import httpx

    await init_db()

    # Get FindyMail API key
    from app.core.config import settings
    findymail_key = settings.FINDYMAIL_API_KEY
    if not findymail_key:
        print("FindyMail API key not configured!")
        return

    # Get companies with contacts but no verified email
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.contacts_count > 0,
            )
        )
        all_targets = result.scalars().all()

    # Filter to those with unverified emails only
    candidates = []
    for dc in all_targets:
        info = dc.company_info or {}
        contacts = info.get('contacts', [])
        has_verified = any(c.get('is_verified') for c in contacts)
        if not has_verified and contacts:
            candidates.append(dc)

    total = len(candidates)
    print(f"\n=== STEP 2: FindyMail verify {total} companies with unverified emails ===")

    verified = found_new = errors = 0
    sem = asyncio.Semaphore(5)

    async def verify(dc):
        nonlocal verified, found_new, errors
        async with sem:
            info = dc.company_info or {}
            contacts = info.get('contacts', [])
            updated = False

            for contact in contacts:
                email = contact.get('email', '')
                name = contact.get('name', '')
                if not name or contact.get('is_verified'):
                    continue

                # Try FindyMail email finder by name + domain
                first_name = name.split()[0] if name else ''
                last_name = name.split()[-1] if name and len(name.split()) > 1 else ''

                if not first_name or not last_name:
                    continue

                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            'https://app.findymail.com/api/search/mail',
                            headers={'Authorization': f'Bearer {findymail_key}', 'Content-Type': 'application/json'},
                            json={'first_name': first_name, 'last_name': last_name, 'domain': dc.domain}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            found_email = data.get('email') or data.get('contact', {}).get('email')
                            if found_email:
                                contact['email'] = found_email
                                contact['is_verified'] = True
                                contact['email_source'] = 'findymail'
                                updated = True
                                found_new += 1
                        elif resp.status_code == 429:
                            await asyncio.sleep(5)
                except Exception:
                    errors += 1

            if updated:
                async with async_session_maker() as s:
                    dc2 = await s.get(DiscoveredCompany, dc.id)
                    dc2.company_info = info
                    flag_modified(dc2, 'company_info')
                    await s.commit()
                verified += 1

            if (verified + errors) % 50 == 0 and (verified + errors) > 0:
                print(f"  FindyMail: {verified}/{total} verified | {found_new} emails found | {errors} errors")

    for i in range(0, total, 30):
        batch = candidates[i:i+30]
        await asyncio.gather(*[verify(t) for t in batch])

    print(f"  FindyMail DONE: {verified} companies verified, {found_new} emails found, {errors} errors")


async def main():
    t0 = time.time()
    await step1_apollo_fill()
    await step2_findymail()
    print(f"\n=== ALL DONE in {(time.time()-t0)/60:.1f}min ===")


if __name__ == "__main__":
    asyncio.run(main())
