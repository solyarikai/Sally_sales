#!/usr/bin/env python3
"""Gather companies for 4 remaining cities via Apollo API.
Then scrape websites and analyze with GPT-4o-mini V8.
Max 100 credits per city."""
import sys
import asyncio
import json
import hashlib
import time
import logging

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.WARNING)

# Only the 4 remaining cities
CITIES = {
    'Doha': 'Doha, Qatar',
    'Jeddah': 'Jeddah, Saudi Arabia',
    'Berlin': 'Berlin, Germany',
    'Amsterdam': 'Amsterdam, Netherlands',
}

KEYWORDS_BY_PRIORITY = [
    'digital agency', 'creative agency', 'marketing agency', 'design agency',
    'branding agency', 'PR agency', 'media agency',
    'web design', 'video production', 'animation studio', 'production house',
    'SEO agency', 'content agency',
    'software development', 'app development', 'mobile development', 'software house',
    'IT services', 'SaaS', 'tech startup', 'consulting firm', 'game studio',
    'cybersecurity', 'cloud consulting', 'DevOps', 'fintech', 'e-commerce',
    'data analytics', 'AI company',
]

SIZES = ['1,10', '11,50', '51,200']
MAX_CREDITS_PER_CITY = 100
PER_PAGE = 100


async def gather_city(city_name, city_location):
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.models.gathering import GatheringRun, CompanySourceLink
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from app.services.domain_service import normalize_domain
    from sqlalchemy import select
    from datetime import datetime, timezone

    credits_used = 0
    all_companies = []

    print(f"\n{'='*60}")
    print(f"  GATHERING: {city_name} (max {MAX_CREDITS_PER_CITY} credits)")
    print(f"{'='*60}")

    for kw in KEYWORDS_BY_PRIORITY:
        if credits_used >= MAX_CREDITS_PER_CITY:
            print(f"  Budget exhausted at {credits_used} credits")
            break

        r = await apollo_service.search_organizations(
            keyword_tags=[kw], locations=[city_location],
            num_employees_ranges=SIZES,
            page=1, per_page=PER_PAGE
        )
        credits_used += 1

        if not r:
            print(f"  {kw}: API failed")
            continue

        orgs = r.get('organizations', [])
        total = r.get('pagination', {}).get('total_entries', 0)
        total_pages = r.get('pagination', {}).get('total_pages', 0)

        for org in orgs:
            domain = org.get('primary_domain', '') or org.get('website_url', '')
            if domain:
                all_companies.append({
                    'domain': domain, 'name': org.get('name', ''),
                    'employees': org.get('estimated_num_employees'),
                    'industry': org.get('industry', ''),
                    'city': org.get('city', ''), 'country': org.get('country', ''),
                    'linkedin_url': org.get('linkedin_url', ''),
                    'raw_apollo': org, '_keyword': kw,
                })

        print(f"  {kw}: {total} total, {len(orgs)} p1, credits={credits_used}")

        # Paginate P1/P2 keywords if >100 results
        remaining_budget = MAX_CREDITS_PER_CITY - credits_used
        kw_idx = KEYWORDS_BY_PRIORITY.index(kw)
        if kw_idx < 13 and total > 100 and remaining_budget > 0:
            max_extra_pages = min(remaining_budget, 5, total_pages - 1)
            for page in range(2, max_extra_pages + 2):
                r2 = await apollo_service.search_organizations(
                    keyword_tags=[kw], locations=[city_location],
                    num_employees_ranges=SIZES,
                    page=page, per_page=PER_PAGE
                )
                credits_used += 1
                if r2:
                    for org in r2.get('organizations', []):
                        domain = org.get('primary_domain', '') or org.get('website_url', '')
                        if domain:
                            all_companies.append({
                                'domain': domain, 'name': org.get('name', ''),
                                'employees': org.get('estimated_num_employees'),
                                'industry': org.get('industry', ''),
                                'city': org.get('city', ''), 'country': org.get('country', ''),
                                'linkedin_url': org.get('linkedin_url', ''),
                                'raw_apollo': org, '_keyword': kw,
                            })
                    print(f"    p{page}: +{len(r2.get('organizations', []))}, credits={credits_used}")
                if not r2 or len(r2.get('organizations', [])) < PER_PAGE:
                    break

    # Dedup
    from app.services.domain_service import normalize_domain
    seen = set()
    unique = []
    for c in all_companies:
        d = normalize_domain(c.get('domain', ''))
        if d and d not in seen:
            seen.add(d)
            c['domain'] = d
            unique.append(c)

    print(f"\n  {city_name}: {len(all_companies)} raw -> {len(unique)} unique, {credits_used} credits")

    # Save to DB
    async with async_session_maker() as s:
        filters = {
            'location': city_location,
            'keywords': KEYWORDS_BY_PRIORITY,
            'organization_num_employees_ranges': SIZES,
            'per_page': PER_PAGE,
            'max_credits': MAX_CREDITS_PER_CITY,
        }
        fh = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()

        run = GatheringRun(
            project_id=9, company_id=1,
            source_type='apollo.companies.api', source_subtype='smart_gather',
            source_label=f'Apollo API - {city_name} (Phase 2)',
            filters=filters, filter_hash=fh,
            status='completed', current_phase='scraped',
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            raw_results_count=len(all_companies),
            credits_used=credits_used,
            triggered_by='pipeline',
            notes=f'{city_name}: {len(KEYWORDS_BY_PRIORITY)} keywords, {credits_used} credits, {len(unique)} unique companies',
        )
        s.add(run)
        await s.flush()

        new_count = dup_count = 0
        for i, c in enumerate(unique):
            existing = await s.execute(select(DiscoveredCompany).where(
                DiscoveredCompany.company_id == 1, DiscoveredCompany.project_id == 9,
                DiscoveredCompany.domain == c['domain']))
            dc = existing.scalar_one_or_none()
            if dc:
                dup_count += 1
            else:
                dc = DiscoveredCompany(
                    company_id=1, project_id=9, domain=c['domain'], name=c.get('name', ''),
                    url=f"https://{c['domain']}", company_info=c.get('raw_apollo'),
                    status=DiscoveredCompanyStatus.NEW, first_found_by=run.id,
                    linkedin_company_url=c.get('linkedin_url', ''))
                s.add(dc)
                await s.flush()
                new_count += 1

            el = await s.execute(select(CompanySourceLink).where(
                CompanySourceLink.discovered_company_id == dc.id,
                CompanySourceLink.gathering_run_id == run.id))
            if not el.scalar_one_or_none():
                s.add(CompanySourceLink(
                    discovered_company_id=dc.id, gathering_run_id=run.id,
                    source_rank=i+1, source_data=c))

        run.new_companies_count = new_count
        run.duplicate_count = dup_count
        await s.commit()
        print(f"  DB: Run #{run.id}, {new_count} new, {dup_count} dup")

    return {'city': city_name, 'run_id': run.id, 'credits': credits_used, 'unique': len(unique), 'new': new_count}


async def scrape_new_companies(run_ids):
    """Scrape websites for companies from specified runs."""
    from app.db import async_session_maker
    from app.services.scraper_service import scraper_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select, update, not_
    from datetime import datetime, timezone

    async with async_session_maker() as s:
        result = await s.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == 9,
                DiscoveredCompany.first_found_by.in_(run_ids),
                DiscoveredCompany.scraped_text.is_(None),
                not_(DiscoveredCompany.domain.like('%_apollo_%')),
                DiscoveredCompany.domain.isnot(None),
                DiscoveredCompany.domain != '',
            )
        )
        companies = result.all()

    total = len(companies)
    if total == 0:
        print("No companies to scrape!")
        return 0

    print(f"\nSCRAPING {total} new companies from 4 cities...")
    urls = [{'row_id': c.id, 'url': f'https://{c.domain}'} for c in companies]

    success_count = 0
    batch_buffer = []
    start_time = time.time()
    last_flush = time.time()

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
            print(f"  Scraped: {success_count}/{total} | Rate: {rate:.0f}/min")
            batch_buffer.clear()
            last_flush = time.time()

    async def on_result(result):
        nonlocal batch_buffer
        if result.get('success') and result.get('text'):
            batch_buffer.append(result)
        if len(batch_buffer) >= 25 or (time.time() - last_flush > 30 and batch_buffer):
            await flush_buffer()

    await scraper_service.scrape_batch(
        urls, timeout=15, max_concurrent=50, delay_between_requests=0.05,
        on_result=on_result,
    )
    await flush_buffer()

    elapsed = time.time() - start_time
    print(f"SCRAPE DONE in {elapsed/60:.1f}min: {success_count}/{total} succeeded")
    return success_count


async def analyze_new_companies(run_ids):
    """GPT-4o-mini V8 analysis on newly scraped companies."""
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany
    from app.services.company_search_service import company_search_service
    from sqlalchemy import select, update, or_
    from datetime import datetime, timezone

    PROMPT_V8 = """Analyze this company website. Is this a SERVICE BUSINESS that delivers projects using freelancers or remote contractors?

=== WHAT WE'RE LOOKING FOR ===
Companies that DO CLIENT WORK (agencies, studios, consultancies) and likely hire freelancers to deliver it.
NOT product companies. NOT platforms. NOT tools. SERVICE businesses.

=== EXCLUSION RULES — if ANY match, output NOT_A_MATCH ===
SAAS / PRODUCT COMPANIES: sells software product/tool/platform = NOT_A_MATCH (unless also provides consulting services)
SOLO / ONE PERSON: only one person visible = NOT_A_MATCH
TEMPLATE / PLACEHOLDER SITES = NOT_A_MATCH
COMPETITORS: staffing, recruitment, outsourcing, EOR/PEO, HR tech = NOT_A_MATCH
GOVERNMENT CONTRACTORS: defense, military, security clearance = NOT_A_MATCH
HARDWARE / PHYSICAL: IT hardware, construction, real estate, restaurants = NOT_A_MATCH
HOLDING / INVESTMENT / COMPANY FORMATION / LEGAL = NOT_A_MATCH
MARKETPLACE / AGGREGATOR / JOB BOARD / DIRECTORY = NOT_A_MATCH

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
                DiscoveredCompany.first_found_by.in_(run_ids),
                DiscoveredCompany.scraped_text.isnot(None),
                or_(DiscoveredCompany.reasoning.is_(None), DiscoveredCompany.reasoning == ''),
            )
        )
        companies = result.scalars().all()

    total = len(companies)
    if total == 0:
        print("No companies to analyze!")
        return 0

    print(f"\nANALYZING {total} companies with GPT-4o-mini V8...")
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

            if (analyzed + errors) % 100 == 0:
                rate = analyzed / max(1, time.time() - start_time) * 60
                print(f"  Analyzed: {analyzed}/{total} | Targets: {targets} | Rate: {rate:.0f}/min")

    for i in range(0, total, 200):
        batch = companies[i:i+200]
        await asyncio.gather(*[analyze_one(c) for c in batch])

    elapsed = time.time() - start_time
    print(f"ANALYSIS DONE in {elapsed/60:.1f}min: {analyzed} analyzed, {targets} targets ({targets/max(1,analyzed)*100:.1f}%), {errors} errors")
    return targets


async def main():
    from app.db import init_db
    await init_db()

    # Phase 1: Gather from Apollo
    results = []
    total_credits = 0
    run_ids = []

    for city_name, city_location in CITIES.items():
        r = await gather_city(city_name, city_location)
        results.append(r)
        total_credits += r['credits']
        run_ids.append(r['run_id'])
        print(f"  Running total: {total_credits} credits across {len(results)} cities")

    print(f"\n{'='*60}")
    print(f"  GATHERING COMPLETE")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['city']}: {r['unique']} unique, {r['new']} new, {r['credits']} credits (run #{r['run_id']})")
    print(f"  TOTAL: {total_credits} credits")

    # Phase 2: Scrape websites
    await scrape_new_companies(run_ids)

    # Phase 3: GPT analysis
    new_targets = await analyze_new_companies(run_ids)

    print(f"\n{'='*60}")
    print(f"  ALL 4 CITIES COMPLETE")
    print(f"  Credits: {total_credits}")
    print(f"  New targets: {new_targets}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
