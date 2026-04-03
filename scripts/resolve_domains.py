#!/usr/bin/env python3
"""Resolve domains for companies that have LinkedIn URLs but no domain.
Uses Apollo Organization Enrich API (FREE, 0 credits).
Then scrapes resolved websites and analyzes with V5 prompt."""
import sys
import asyncio
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)


async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.services.scraper_service import scraper_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select, update
    from datetime import datetime, timezone

    await init_db()

    async with async_session_maker() as s:
        # Get companies with LinkedIn but no real domain
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.linkedin_company_url, DiscoveredCompany.name)
            .where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.domain.like('%_apollo_%'),
                DiscoveredCompany.linkedin_company_url.isnot(None),
                DiscoveredCompany.linkedin_company_url != '',
            )
            .limit(5000)
        )
        companies = result.all()
        print(f'Resolving domains for {len(companies)} companies via Apollo Org Enrich (FREE)')

        resolved = 0
        failed = 0
        sem = asyncio.Semaphore(5)  # Apollo rate limit

        async def resolve_one(dc_id, linkedin_url, name):
            nonlocal resolved, failed
            async with sem:
                try:
                    # Extract LinkedIn company slug
                    slug = linkedin_url.rstrip('/').split('/')[-1]
                    if not slug:
                        failed += 1
                        return

                    # Call Apollo org enrich (FREE)
                    org_data = await apollo_service.enrich_organization(linkedin_url=linkedin_url)

                    if org_data and org_data.get('primary_domain'):
                        domain = org_data['primary_domain'].lower().replace('www.', '')
                        await s.execute(
                            update(DiscoveredCompany)
                            .where(DiscoveredCompany.id == dc_id)
                            .values(
                                domain=domain,
                                url=f'https://{domain}',
                                apollo_org_data=org_data,
                            )
                        )
                        resolved += 1
                    else:
                        failed += 1

                except Exception as e:
                    failed += 1

                if (resolved + failed) % 100 == 0:
                    await s.commit()
                    print(f'  Progress: {resolved} resolved, {failed} failed of {resolved + failed}')

        # Process in batches
        batch_size = 100
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            tasks = [resolve_one(c.id, c.linkedin_company_url, c.name) for c in batch]
            await asyncio.gather(*tasks)
            await s.commit()

        await s.commit()
        print(f'\nDONE: {resolved} resolved, {failed} failed out of {len(companies)}')


if __name__ == "__main__":
    asyncio.run(main())
