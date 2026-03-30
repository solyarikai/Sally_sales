#!/usr/bin/env python3
"""Analyze companies that have scraped_text but no reasoning (never GPT-analyzed)."""
import sys
import asyncio
import logging
import time

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

PROMPT_V8 = """Analyze this company website. Is this a SERVICE BUSINESS that delivers projects using freelancers or remote contractors?

=== WHAT WE'RE LOOKING FOR ===
Companies that DO CLIENT WORK (agencies, studios, consultancies) and likely hire freelancers to deliver it.
NOT product companies. NOT platforms. NOT tools. SERVICE businesses.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===

SAAS / PRODUCT COMPANIES:
- Company sells a software product, tool, platform, or app = NOT_A_MATCH
- "Sign up", "Start free trial", "Pricing plans", "API documentation" = product company = NOT_A_MATCH
- Cybersecurity TOOLS, chatbot platforms, analytics dashboards = NOT_A_MATCH
- EXCEPTION: if the company ALSO provides consulting/implementation services alongside their product, it's OK

SOLO / ONE PERSON:
- Only ONE person visible on entire website = NOT_A_MATCH
- "Fractional CxO", personal brand, solo advisor, blogger = NOT_A_MATCH

TEMPLATE / PLACEHOLDER SITES:
- Generic template, no real portfolio, "Lorem ipsum" = NOT_A_MATCH

COMPETITORS (they provide WORKERS):
- Staffing, recruitment, outsourcing, EOR/PEO, HR tech = NOT_A_MATCH

GOVERNMENT CONTRACTORS:
- Companies primarily serving government = NOT_A_MATCH

HARDWARE / PHYSICAL:
- IT hardware, construction, real estate, restaurants, hotels = NOT_A_MATCH

HOLDING / INVESTMENT / COMPANY FORMATION / LEGAL = NOT_A_MATCH

MARKETPLACE / AGGREGATOR / JOB BOARD / DIRECTORY = NOT_A_MATCH

=== IF NOT EXCLUDED — assign segment ===

DIGITAL_AGENCY, CREATIVE_STUDIO, SOFTWARE_HOUSE, IT_SERVICES, MARKETING_AGENCY,
TECH_STARTUP, MEDIA_PRODUCTION, GAME_STUDIO, CONSULTING_FIRM, ECOMMERCE_COMPANY

=== OUTPUT (valid JSON) ===

{"segment": "CAPS_LOCKED or NOT_A_MATCH", "is_target": true/false, "reasoning": "Does [what] as a service.", "company_info": {"name": "from website", "description": "what they do", "location": "if found"}}

CRITICAL: When in doubt -> NOT_A_MATCH."""


async def main():
    from app.db import async_session_maker, init_db
    from app.models.pipeline import DiscoveredCompany
    from app.services.company_search_service import company_search_service
    from sqlalchemy import select, update, or_
    from datetime import datetime, timezone

    await init_db()

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
    print(f"ANALYZE: {total} companies with scraped text but no GPT analysis")

    if total == 0:
        print("Nothing to analyze!")
        return

    analyzed = 0
    targets = 0
    errors = 0
    start_time = time.time()

    sem = asyncio.Semaphore(25)

    async def analyze_one(company):
        nonlocal analyzed, targets, errors
        async with sem:
            try:
                result = await company_search_service.analyze_company(
                    content=company.scraped_text[:15000],
                    target_segments="Service businesses that hire freelancers",
                    domain=company.domain,
                    is_html=False,
                    custom_system_prompt=PROMPT_V8,
                )
                if result and isinstance(result, dict):
                    is_target = result.get('is_target', False)
                    segment = result.get('segment', 'NOT_A_MATCH')
                    reasoning = result.get('reasoning', '')
                    name = ''
                    if result.get('company_info'):
                        name = result['company_info'].get('name', '')

                    async with async_session_maker() as s:
                        vals = dict(
                            is_target=is_target,
                            reasoning=reasoning,
                            updated_at=datetime.now(timezone.utc),
                        )
                        if is_target:
                            vals['matched_segment'] = segment
                        if name:
                            vals['name'] = name
                        await s.execute(
                            update(DiscoveredCompany)
                            .where(DiscoveredCompany.id == company.id)
                            .values(**vals)
                        )
                        await s.commit()

                    analyzed += 1
                    if is_target:
                        targets += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {e}")

            if (analyzed + errors) % 100 == 0:
                rate = analyzed / max(1, time.time() - start_time) * 60
                print(f"  Progress: {analyzed}/{total} | Targets: {targets} | Errors: {errors} | Rate: {rate:.0f}/min")

    # Process in batches of 200
    for i in range(0, total, 200):
        batch = companies[i:i+200]
        await asyncio.gather(*[analyze_one(c) for c in batch])

    elapsed = time.time() - start_time
    print(f"\nDONE in {elapsed/60:.1f}min: {analyzed} analyzed, {targets} NEW targets found, {errors} errors")
    print(f"Target rate: {targets/max(1,analyzed)*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
