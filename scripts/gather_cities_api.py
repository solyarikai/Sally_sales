#!/usr/bin/env python3
"""Gather companies for all cities via Apollo API — smart credit allocation.
Max 100 credits per city. Prioritize high-target-rate keywords.
All results saved to pipeline DB via gathering_service."""
import sys
import asyncio
import json
import hashlib

sys.path.insert(0, '/app')

# Priority keywords — ordered by expected target rate (highest first)
KEYWORDS_BY_PRIORITY = [
    # P1: Direct ICP (10-15% target rate)
    'digital agency', 'creative agency', 'marketing agency', 'design agency',
    'branding agency', 'PR agency', 'media agency',
    # P2: Adjacent (5-10%)
    'web design', 'video production', 'animation studio', 'production house',
    'SEO agency', 'content agency',
    # P3: Tech services (3-5%)
    'software development', 'app development', 'mobile development', 'software house',
    # P4: Broader tech (2-4%)
    'IT services', 'SaaS', 'tech startup', 'consulting firm', 'game studio',
    # P5: Fill (1-2%)
    'cybersecurity', 'cloud consulting', 'DevOps', 'fintech', 'e-commerce',
    'data analytics', 'AI company',
]

CITIES = {
    'Miami': 'Miami, Florida, United States',
    'Riyadh': 'Riyadh, Saudi Arabia',
    'London': 'London, England, United Kingdom',
    'Singapore': 'Singapore',
    'Sydney': 'Sydney, New South Wales, Australia',
    'Austin': 'Austin, Texas, United States',
    'Doha': 'Doha, Qatar',
    'Jeddah': 'Jeddah, Saudi Arabia',
    'Berlin': 'Berlin, Germany',
    'Amsterdam': 'Amsterdam, Netherlands',
}

SIZES = ['1,10', '11,50', '51,200']
MAX_CREDITS_PER_CITY = 100
PER_PAGE = 100


async def gather_city(city_name, city_location):
    """Gather companies for one city. Max 100 credits."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.models.gathering import GatheringRun, CompanySourceLink
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from app.services.domain_service import normalize_domain
    from sqlalchemy import select
    from datetime import datetime, timezone

    credits_used = 0
    total_companies = 0
    all_companies = []

    print(f"\n=== {city_name} (max {MAX_CREDITS_PER_CITY} credits) ===")

    for kw in KEYWORDS_BY_PRIORITY:
        if credits_used >= MAX_CREDITS_PER_CITY:
            print(f"  Budget exhausted at {credits_used} credits")
            break

        # Page 1: always fetch (discover volume)
        r = await apollo_service.search_organizations(
            keyword_tags=[kw], locations=[city_location],
            num_employees_ranges=SIZES,
            page=1, per_page=PER_PAGE
        )
        credits_used += 1

        if not r:
            print(f"  {kw}: API failed — stopping city")
            break

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

        # Pages 2+: only for high-volume, high-priority keywords
        remaining_budget = MAX_CREDITS_PER_CITY - credits_used
        pages_available = min(total_pages, remaining_budget)

        # Only paginate P1/P2 keywords (first 13) if >100 results
        kw_idx = KEYWORDS_BY_PRIORITY.index(kw)
        if kw_idx < 13 and total > 100 and pages_available > 0:
            max_extra_pages = min(pages_available, 5)  # Max 5 extra pages per keyword
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

    # Dedup by domain
    seen = set()
    unique = []
    for c in all_companies:
        d = normalize_domain(c.get('domain', ''))
        if d and d not in seen:
            seen.add(d)
            c['domain'] = d
            unique.append(c)

    print(f"  {city_name}: {len(all_companies)} raw → {len(unique)} unique, {credits_used} credits spent")

    # Save to DB as a gathering run
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
            source_label=f'Apollo API — {city_name} (smart)',
            filters=filters, filter_hash=fh,
            status='completed', current_phase='gathered',
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            raw_results_count=len(all_companies),
            credits_used=credits_used,
            triggered_by='pipeline',
            notes=f'{city_name}: {len(KEYWORDS_BY_PRIORITY)} keywords, {credits_used} credits, {len(unique)} unique companies',
            raw_output_ref=f'gathered via apollo_filter_research + gather_cities_api',
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

    return {'city': city_name, 'credits': credits_used, 'unique': len(unique), 'new': new_count}


async def main():
    from app.db import init_db
    await init_db()

    results = []
    total_credits = 0

    for city_name, city_location in CITIES.items():
        r = await gather_city(city_name, city_location)
        results.append(r)
        total_credits += r['credits']
        print(f"  Running total: {total_credits} credits spent across {len(results)} cities")

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['city']}: {r['unique']} unique, {r['new']} new, {r['credits']} credits")
    print(f"  TOTAL: {total_credits} credits")


if __name__ == "__main__":
    asyncio.run(main())
