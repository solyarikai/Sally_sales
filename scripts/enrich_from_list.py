#!/usr/bin/env python3
"""Enrich targets from a pre-computed list file. Simple, no complex queries."""
import sys, asyncio, logging, time
sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

TITLES = ['CEO','Founder','Co-Founder','Owner','COO','CFO','Managing Director','Head of Finance','VP Operations']
MAX_CREDITS = 2000
LIST_FILE = '/tmp/nonus_targets.txt'

async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone

    await init_db()

    targets = []
    with open(LIST_FILE) as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) == 2:
                targets.append((int(parts[0]), parts[1]))

    total = len(targets)
    print(f"Enriching {total} non-US targets (budget: {MAX_CREDITS} credits)")

    found = enriched = errors = 0
    start = time.time()
    sem = asyncio.Semaphore(3)

    async def do(cid, domain):
        nonlocal found, enriched, errors
        if apollo_service.credits_used >= MAX_CREDITS:
            return
        async with sem:
            try:
                people = await apollo_service.enrich_by_domain(domain=domain, limit=3, titles=TITLES)
                if people:
                    contacts = [{'name': f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
                                 'email': p.get('email',''), 'title': p.get('job_title',''),
                                 'linkedin_url': p.get('linkedin_url',''),
                                 'is_verified': p.get('is_verified', False)} for p in people[:3]]
                    async with async_session_maker() as s:
                        dc = await s.get(DiscoveredCompany, cid)
                        info = dc.company_info or {}
                        info['contacts'] = contacts
                        info['contacts_found_at'] = datetime.now(timezone.utc).isoformat()
                        dc.company_info = info
                        dc.contacts_count = len(contacts)
                        flag_modified(dc, 'company_info')
                        await s.commit()
                    found += len(contacts)
                    enriched += 1
                await asyncio.sleep(0.4)
            except Exception as e:
                errors += 1
                if errors <= 3: print(f"  Err: {e}")
            if (enriched + errors) % 50 == 0 and (enriched + errors) > 0:
                print(f"  {enriched}/{total} | {found} contacts | {apollo_service.credits_used} credits | {errors} err")

    for i in range(0, total, 30):
        if apollo_service.credits_used >= MAX_CREDITS:
            print(f"  Budget hit: {apollo_service.credits_used}")
            break
        batch = targets[i:i+30]
        await asyncio.gather(*[do(c, d) for c, d in batch])

    print(f"\nDONE {enriched}/{total} enriched | {found} contacts | {apollo_service.credits_used} credits | {time.time()-start:.0f}s | {errors} err")

if __name__ == "__main__":
    asyncio.run(main())
