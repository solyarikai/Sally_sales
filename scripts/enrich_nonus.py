#!/usr/bin/env python3
"""Enrich non-US targets without contacts. Budget: ~2,100 credits."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

TITLES = ['CEO', 'Founder', 'Co-Founder', 'Owner', 'COO', 'CFO', 'Managing Director', 'Head of Finance', 'VP Operations']
MAX_CONTACTS = 3
MAX_CREDITS = 2000

US_RUNS = []  # Will exclude US cities by run notes

async def main():
    from app.db import async_session_maker, init_db
    from app.services.apollo_service import apollo_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import text
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime, timezone

    await init_db()

    async with async_session_maker() as s:
        result = await s.execute(text("""
            SELECT dc.id, dc.domain, dc.matched_segment
            FROM discovered_companies dc
            WHERE dc.id IN (
              SELECT DISTINCT dc2.id FROM discovered_companies dc2
              JOIN company_source_links csl ON csl.discovered_company_id = dc2.id
              JOIN gathering_runs gr ON csl.gathering_run_id = gr.id
            WHERE dc.project_id = 9 AND dc.is_target = true
              AND (dc.in_active_campaign IS NULL OR dc.in_active_campaign = false)
              AND dc.company_info::text NOT LIKE '%contacts%'
              AND gr.notes NOT LIKE '%Miami%' AND gr.notes NOT LIKE '%New York%'
              AND gr.notes NOT LIKE '%Los Angeles%' AND gr.notes NOT LIKE '%Austin%'
              AND gr.notes NOT LIKE '%San Francisco%' AND gr.notes NOT LIKE '%Chicago%'
              AND gr.notes NOT LIKE '%Boston%' AND gr.notes NOT LIKE '%Seattle%'
              AND gr.notes NOT LIKE '%Denver%' AND gr.notes NOT LIKE '%Portland%'
              AND gr.notes NOT LIKE '%NYC%' AND gr.notes NOT LIKE '%LA %'
            )
            ORDER BY CASE dc.matched_segment
              WHEN 'DIGITAL_AGENCY' THEN 1
              WHEN 'MARKETING_AGENCY' THEN 2
              WHEN 'CREATIVE_STUDIO' THEN 3
              WHEN 'MEDIA_PRODUCTION' THEN 4
              WHEN 'SOFTWARE_HOUSE' THEN 5
              ELSE 6 END
        """))
        targets = result.all()

    total = len(targets)
    print(f"Enriching {total} non-US targets (budget: {MAX_CREDITS} credits)")

    found_total = 0
    enriched = 0
    errors = 0
    start_time = time.time()
    sem = asyncio.Semaphore(3)

    async def find_for(cid, domain):
        nonlocal found_total, enriched, errors
        if apollo_service.credits_used >= MAX_CREDITS:
            return
        async with sem:
            try:
                people = await apollo_service.enrich_by_domain(domain=domain, limit=MAX_CONTACTS, titles=TITLES)
                if people:
                    contacts = [{'name': f"{p.get('first_name','')} {p.get('last_name','')}".strip(),
                                 'email': p.get('email',''), 'title': p.get('job_title',''),
                                 'linkedin_url': p.get('linkedin_url',''),
                                 'is_verified': p.get('is_verified', False)}
                                for p in people[:MAX_CONTACTS]]
                    async with async_session_maker() as s:
                        dc = await s.get(DiscoveredCompany, cid)
                        info = dc.company_info or {}
                        info['contacts'] = contacts
                        info['contacts_found_at'] = datetime.now(timezone.utc).isoformat()
                        dc.company_info = info
                        flag_modified(dc, 'company_info')
                        await s.commit()
                    found_total += len(contacts)
                    enriched += 1
                await asyncio.sleep(0.4)
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {e}")
            if (enriched + errors) % 50 == 0 and (enriched + errors) > 0:
                print(f"  {enriched}/{total} | {found_total} contacts | Credits: {apollo_service.credits_used}/{MAX_CREDITS}")

    for i in range(0, total, 30):
        if apollo_service.credits_used >= MAX_CREDITS:
            print(f"  Budget hit at {apollo_service.credits_used} credits")
            break
        batch = targets[i:i+30]
        await asyncio.gather(*[find_for(t.id, t.domain) for t in batch])

    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed/60:.1f}min: {enriched} enriched, {found_total} contacts, {apollo_service.credits_used} credits, {errors} errors")


if __name__ == "__main__":
    asyncio.run(main())
