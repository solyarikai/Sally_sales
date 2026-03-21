#!/usr/bin/env python3
"""Research Apollo API filters — find which keywords produce the most results per city.
Each API call = 1 credit, returns up to 100 companies.
Goal: spend minimum credits to find best filter sets."""
import sys
import asyncio
import json

sys.path.insert(0, '/app')

KEYWORDS = [
    'marketing agency', 'digital agency', 'creative agency', 'software development',
    'IT services', 'web design', 'video production', 'SaaS', 'fintech',
    'design agency', 'PR agency', 'media agency', 'app development',
    'consulting firm', 'tech startup', 'animation studio', 'game studio',
    'branding agency', 'SEO agency', 'production house', 'e-commerce',
    'cybersecurity', 'cloud consulting', 'data analytics', 'AI company',
    'mobile development', 'DevOps', 'software house',
]

CITIES = [
    'Miami, Florida, United States',
    'Riyadh, Saudi Arabia',
    'London, England, United Kingdom',
    'Singapore',
    'Sydney, New South Wales, Australia',
    'Austin, Texas, United States',
]

SIZES = ['1,50', '51,200']


async def main():
    from app.services.apollo_service import apollo_service

    all_results = {}
    credits_spent = 0

    for city in CITIES:
        city_short = city.split(',')[0]
        print(f"\n=== {city_short} ===")
        city_results = []

        for kw in KEYWORDS:
            r = await apollo_service.search_organizations(
                keyword_tags=[kw], locations=[city],
                num_employees_ranges=SIZES,
                page=1, per_page=100
            )
            credits_spent += 1

            if r:
                total = r.get('pagination', {}).get('total_entries', 0)
                returned = len(r.get('organizations', []))
                city_results.append({
                    'keyword': kw, 'total': total, 'returned': returned,
                    'pages_needed': (total + 99) // 100,
                })
                print(f"  {kw}: {total} total ({returned} returned)")
            else:
                print(f"  {kw}: API FAILED — stopping to preserve credits")
                break

        city_results.sort(key=lambda x: x['total'], reverse=True)
        all_results[city_short] = city_results

        print(f"\n  TOP 10 for {city_short}:")
        for r in city_results[:10]:
            print(f"    {r['keyword']}: {r['total']} companies ({r['pages_needed']} credits)")

        total_companies = sum(r['total'] for r in city_results)
        total_credits = sum(r['pages_needed'] for r in city_results)
        print(f"  TOTAL: {total_companies} companies available, {total_credits} credits to get all")
        print(f"  Credits spent so far: {credits_spent}")

    # Save results
    with open('/tmp/apollo_filter_research.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n=== DONE === Credits spent: {credits_spent}")
    print(f"Results saved to /tmp/apollo_filter_research.json")


if __name__ == "__main__":
    asyncio.run(main())
