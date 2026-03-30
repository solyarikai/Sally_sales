#!/usr/bin/env python3
"""Scrape 7,537 real-domain companies that were never properly analyzed.
Then run GPT-4o-mini V8 analysis on all newly scraped."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

COMMIT_EVERY = 25
FLUSH_INTERVAL = 30


async def scrape_phase():
    from app.db import async_session_maker, init_db
    from app.services.scraper_service import scraper_service
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select, update, not_, or_
    from datetime import datetime, timezone

    await init_db()

    # Get real-domain companies with no reasoning (never properly analyzed)
    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.scraped_text.is_(None),
                or_(DiscoveredCompany.reasoning.is_(None), DiscoveredCompany.reasoning == ''),
                not_(DiscoveredCompany.domain.like('%_apollo_%')),
                DiscoveredCompany.domain.isnot(None),
                DiscoveredCompany.domain != '',
            )
        )
        companies = result.all()

    total = len(companies)
    print(f"SCRAPE PHASE: {total} companies with real domains, never analyzed")

    if total == 0:
        print("Nothing to scrape!")
        return 0

    urls = [{'row_id': c.id, 'url': f'https://{c.domain}'} for c in companies]

    success_count = 0
    fail_count = 0
    batch_buffer = []
    last_flush = time.time()
    start_time = time.time()

    async def flush_buffer():
        nonlocal success_count, batch_buffer, last_flush
        if not batch_buffer:
            return
        async with async_session_maker() as s:
            for r in batch_buffer:
                await s.execute(
                    update(DiscoveredCompany)
                    .where(DiscoveredCompany.id == r['row_id'])
                    .values(
                        scraped_text=r['text'][:50000],
                        scraped_at=datetime.now(timezone.utc),
                    )
                )
            await s.commit()
            success_count += len(batch_buffer)
            rate = success_count / max(1, time.time() - start_time) * 60
            print(f"  Scraped: {success_count}/{total} | Failed: {fail_count} | Rate: {rate:.0f}/min")
            batch_buffer.clear()
            last_flush = time.time()

    async def on_result(result):
        nonlocal batch_buffer, fail_count
        if result.get('success') and result.get('text'):
            batch_buffer.append(result)
        else:
            fail_count += 1

        if len(batch_buffer) >= COMMIT_EVERY or (time.time() - last_flush > FLUSH_INTERVAL and batch_buffer):
            await flush_buffer()

    await scraper_service.scrape_batch(
        urls, timeout=15, max_concurrent=50, delay_between_requests=0.05,
        on_result=on_result,
    )

    await flush_buffer()

    elapsed = time.time() - start_time
    print(f"SCRAPE DONE in {elapsed/60:.1f}min: {success_count} succeeded, {fail_count} failed out of {total}")
    return success_count


async def analyze_phase():
    """Run GPT-4o-mini V8 on all companies that now have scraped_text but no reasoning."""
    from app.db import async_session_maker, init_db
    from app.models.pipeline import DiscoveredCompany
    from app.services.company_search_service import company_search_service
    from sqlalchemy import select, update, or_
    from datetime import datetime, timezone
    import json

    await init_db()

    PROMPT_V8 = """Analyze this company website. Is this a SERVICE BUSINESS that delivers projects using freelancers or remote contractors?

=== WHAT WE'RE LOOKING FOR ===
Companies that DO CLIENT WORK (agencies, studios, consultancies) and likely hire freelancers to deliver it.
NOT product companies. NOT platforms. NOT tools. SERVICE businesses.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

SAAS / PRODUCT COMPANIES:
- Company sells a software product, tool, platform, or app = NOT_A_MATCH
- "Sign up", "Start free trial", "Pricing plans", "API documentation" = product company = NOT_A_MATCH
- Cybersecurity TOOLS, chatbot platforms, analytics dashboards = NOT_A_MATCH
- Ad networks, push notification platforms, media buying tools = NOT_A_MATCH
- EXCEPTION: if the company ALSO provides consulting/implementation services alongside their product, it's OK

SOLO / ONE PERSON:
- Only ONE person visible on entire website = NOT_A_MATCH
- "Fractional CxO", personal brand, solo advisor, blogger = NOT_A_MATCH

TEMPLATE / PLACEHOLDER SITES:
- Generic template, no real portfolio, "Lorem ipsum" = NOT_A_MATCH
- Domain parked, under construction = NOT_A_MATCH

COMPETITORS (they provide WORKERS):
- Staffing, recruitment, outsourcing, EOR/PEO, HR tech = NOT_A_MATCH

GOVERNMENT CONTRACTORS:
- Companies primarily serving government = NOT_A_MATCH
- Defense, military, security clearance = NOT_A_MATCH

HARDWARE / PHYSICAL:
- IT hardware, construction, real estate, restaurants, hotels = NOT_A_MATCH
- Print/publishing, outdoor advertising = NOT_A_MATCH

HOLDING / INVESTMENT:
- VC, PE, holding companies, M&A advisory = NOT_A_MATCH

COMPANY FORMATION / LEGAL:
- Business setup, visa, PRO services = NOT_A_MATCH

MARKETPLACE / AGGREGATOR:
- Job boards, directories, listing sites, news sites = NOT_A_MATCH

=== IF NOT EXCLUDED — assign segment ===

DIGITAL_AGENCY, CREATIVE_STUDIO, SOFTWARE_HOUSE, IT_SERVICES, MARKETING_AGENCY,
TECH_STARTUP, MEDIA_PRODUCTION, GAME_STUDIO, CONSULTING_FIRM, ECOMMERCE_COMPANY

=== OUTPUT (valid JSON) ===

{"segment": "CAPS_LOCKED or NOT_A_MATCH", "is_target": true/false, "reasoning": "Does [what] as a service.", "company_info": {"name": "from website", "description": "what they do", "location": "if found"}}

CRITICAL: When in doubt -> NOT_A_MATCH."""

    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.scraped_text.isnot(None),
                or_(DiscoveredCompany.reasoning.is_(None), DiscoveredCompany.reasoning == ''),
            )
        )
        companies = result.scalars().all()

    total = len(companies)
    print(f"\nANALYZE PHASE: {total} companies with scraped text but no reasoning")

    if total == 0:
        print("Nothing to analyze!")
        return

    analyzed = 0
    targets = 0
    errors = 0

    sem = asyncio.Semaphore(25)

    async def analyze_one(company):
        nonlocal analyzed, targets, errors
        async with sem:
            try:
                result = await company_search_service.analyze_company(
                    company.scraped_text[:15000],
                    custom_system_prompt=PROMPT_V8,
                )
                if result and isinstance(result, dict):
                    is_target = result.get('is_target', False)
                    segment = result.get('segment', 'NOT_A_MATCH')
                    reasoning = result.get('reasoning', '')

                    async with async_session_maker() as s:
                        await s.execute(
                            update(DiscoveredCompany)
                            .where(DiscoveredCompany.id == company.id)
                            .values(
                                is_target=is_target,
                                matched_segment=segment if is_target else None,
                                reasoning=reasoning,
                                updated_at=datetime.now(timezone.utc),
                            )
                        )
                        await s.commit()

                    analyzed += 1
                    if is_target:
                        targets += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1

            if (analyzed + errors) % 50 == 0:
                print(f"  Analyzed: {analyzed}/{total} | Targets: {targets} | Errors: {errors}")

    # Process in batches of 100
    for i in range(0, total, 100):
        batch = companies[i:i+100]
        await asyncio.gather(*[analyze_one(c) for c in batch])
        print(f"  Batch {i//100 + 1}: {analyzed}/{total} analyzed, {targets} targets, {errors} errors")

    print(f"\nANALYZE DONE: {analyzed} analyzed, {targets} targets found, {errors} errors")


async def main():
    scraped = await scrape_phase()
    await analyze_phase()
    print("\n=== ALL DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
