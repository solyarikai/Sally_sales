"""Full verification: gather with smart strategy + scrape 20 per segment for Opus review.
Run: docker exec mcp-backend python /app/full_verify_all_segments.py
"""
import asyncio, httpx, sys, json, time, os, random
from datetime import datetime
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from app.services.scraper_service import ScraperService
from sqlalchemy import select

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TMP = "/app/tests/tmp"
os.makedirs(TMP, exist_ok=True)

SEGMENTS = [
    {
        "id": "tfp_fashion_italy",
        "query": "Fashion brands in Italy",
        "offer": "TFP builds branded resale platforms for fashion brands to monetize old stock and returns",
        "target_def": "Fashion BRAND selling own products. NOT: schools, consulting, textile suppliers, magazines, retailers.",
        "strategy": "industry_first",
        "search_params": {
            "organization_industry_tag_ids": ["5567cd82736964540d0b0000"],
            "organization_locations": ["Italy"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
    },
    {
        "id": "es_it_miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff provides payroll and contractor payment for companies hiring internationally",
        "target_def": "IT consulting/services company (11-200 emp). NOT: product companies, SaaS, hardware, recruiters, magazines.",
        "strategy": "keywords_first",
        "search_params": {
            "q_organization_keyword_tags": ["IT consulting", "managed IT services", "IT outsourcing"],
            "organization_locations": ["Miami, Florida, United States"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
    },
    {
        "id": "es_video_london",
        "query": "Video production companies in London",
        "offer": "EasyStaff provides payroll and contractor payment for companies hiring internationally",
        "target_def": "Video/film production company (11-200 emp). NOT: ad agencies, broadcasters, magazines, freelancers.",
        "strategy": "industry_first",
        "search_params": {
            "organization_industry_tag_ids": ["5567cdd37369643b80510000"],  # motion pictures & film → actually entertainment
            "organization_locations": ["London, England, United Kingdom"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
    },
    {
        "id": "es_it_us",
        "query": "IT consulting companies in US",
        "offer": "EasyStaff provides payroll and contractor payment",
        "target_def": "IT consulting/services company. NOT: product companies, SaaS, magazines.",
        "strategy": "keywords_first",
        "search_params": {
            "q_organization_keyword_tags": ["IT consulting", "managed IT services", "software development"],
            "organization_locations": ["United States"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
    },
    {
        "id": "es_video_uk",
        "query": "Video production companies in UK",
        "offer": "EasyStaff provides payroll and contractor payment",
        "target_def": "Video/film production company. NOT: ad agencies, broadcasters, magazines.",
        "strategy": "industry_first",
        "search_params": {
            "organization_industry_tag_ids": ["5567cdd37369643b80510000"],
            "organization_locations": ["United Kingdom"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
        },
    },
    {
        "id": "onsocial_uk",
        "query": "Social media influencer agencies in UK",
        "offer": "OnSocial is an AI-powered social media management platform",
        "target_def": "Influencer/social media agency (1-200 emp). NOT: general marketing, PR, ad agencies, tech platforms, magazines.",
        "strategy": "keywords_first",
        "search_params": {
            "q_organization_keyword_tags": ["influencer marketing", "social media agency", "influencer agency"],
            "organization_locations": ["United Kingdom"],
            "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
        },
    },
]


async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        apollo_row = r.scalar_one_or_none()
        apollo_key = decrypt_value(apollo_row.api_key_encrypted).strip()

        r2 = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apify", MCPIntegrationSetting.user_id == 181))
        apify_row = r2.scalar_one_or_none()
        apify_pw = decrypt_value(apify_row.api_key_encrypted).strip() if apify_row else ""

    scraper = ScraperService(apify_proxy_password=apify_pw)
    hdr = {"X-Api-Key": apollo_key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"

    all_verification = {}

    for seg in SEGMENTS:
        print(f"\n{'='*60}")
        print(f"{seg['id']}: {seg['query']} (strategy: {seg['strategy']})")
        print(f"{'='*60}")

        # Gather page 3 (skip early pages — more diverse companies)
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json={**seg["search_params"], "per_page": 100, "page": 3})
            orgs = resp.json().get("organizations", []) or resp.json().get("accounts", [])
        print(f"  Page 3: {len(orgs)} companies")

        # Pick 20 with domains
        with_domains = [o for o in orgs if o.get("primary_domain")]
        sample = random.sample(with_domains, min(20, len(with_domains)))
        print(f"  Sampling {len(sample)} for scraping...")

        # Scrape all in parallel
        t0 = time.time()
        tasks = [scraper.scrape_website(f"https://{o['primary_domain']}") for o in sample]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - t0
        print(f"  Scraped in {elapsed:.1f}s")

        # Build verification data
        companies = []
        for org, sr in zip(sample, results):
            text = ""
            if isinstance(sr, dict) and sr.get("success"):
                text = sr["text"][:800]
            companies.append({
                "name": org.get("name", "?"),
                "domain": org.get("primary_domain", "?"),
                "industry": org.get("industry"),
                "employees": org.get("estimated_num_employees"),
                "website_text": text,
                "scraped": bool(text),
            })

        scraped_count = sum(1 for c in companies if c["scraped"])
        print(f"  Scraped: {scraped_count}/{len(companies)}")

        all_verification[seg["id"]] = {
            "query": seg["query"],
            "offer": seg["offer"],
            "target_def": seg["target_def"],
            "strategy": seg["strategy"],
            "companies": companies,
        }

        await asyncio.sleep(1)

    # Save everything
    outfile = f"{TMP}/full_verify_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump(all_verification, f, indent=2)
    print(f"\nAll saved to {outfile}")
    print(f"Total companies for Opus verification: {sum(len(v['companies']) for v in all_verification.values())}")

asyncio.run(main())
