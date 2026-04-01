"""Verify target quality by SCRAPING websites — not guessing from names.
Scrapes 20 random companies per segment, stores text for Opus verification.
Run: docker exec mcp-backend python /app/verify_targets_scraped.py
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

SEGMENTS_FILE = f"{TMP}/all_segments_20260401_003703.json"


async def main():
    # Load previous results
    with open(SEGMENTS_FILE) as f:
        all_segments = json.load(f)

    # Get Apify key
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apify", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        apify_pw = decrypt_value(row.api_key_encrypted).strip() if row else ""

    scraper = ScraperService(apify_proxy_password=apify_pw)

    # For each segment, scrape 20 random companies from industry results
    for seg_id, seg_data in all_segments.items():
        samples = seg_data.get("samples_industry", [])
        # We need domains, not just names — re-fetch from Apollo
        # For now use what we have — names only, but log for Opus verification
        print(f"\n--- {seg_id} ---")
        print(f"Industry top 10: {samples}")
        print(f"Keywords top 10: {seg_data.get('samples_keywords', [])}")

    # Detailed scrape for TFP (primary test case)
    print(f"\n{'='*60}")
    print("SCRAPING TFP FASHION ITALY — 20 companies for verification")
    print(f"{'='*60}")

    # Get Apollo key and fetch fresh page with full data
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        apollo_key = decrypt_value(row.api_key_encrypted).strip()

    hdr = {"X-Api-Key": apollo_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post("https://api.apollo.io/api/v1/mixed_companies/search", headers=hdr, json={
            "organization_industry_tag_ids": ["5567cd82736964540d0b0000"],
            "organization_locations": ["Italy"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
            "per_page": 100, "page": 5,  # Page 5 for diverse companies
        })
        orgs = resp.json().get("organizations", [])

    # Pick 20 random with domains
    with_domains = [o for o in orgs if o.get("primary_domain")]
    sample = random.sample(with_domains, min(20, len(with_domains)))

    # Scrape all 20 in parallel
    print(f"Scraping {len(sample)} companies...")
    t0 = time.time()
    scrape_tasks = [scraper.scrape_website(f"https://{o['primary_domain']}") for o in sample]
    scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    elapsed = time.time() - t0
    print(f"Scraped in {elapsed:.1f}s")

    # Build verification data
    verify_data = []
    for org, sr in zip(sample, scrape_results):
        domain = org.get("primary_domain", "?")
        name = org.get("name", "?")
        website_text = ""
        if isinstance(sr, dict) and sr.get("success"):
            website_text = sr["text"][:1000]

        verify_data.append({
            "name": name,
            "domain": domain,
            "industry": org.get("industry"),
            "employees": org.get("estimated_num_employees"),
            "apollo_description": (org.get("short_description") or "")[:200],
            "website_text": website_text[:500],
            "scrape_success": isinstance(sr, dict) and sr.get("success", False),
        })

    # Save for Opus verification
    outfile = f"{TMP}/verify_tfp_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump(verify_data, f, indent=2)
    print(f"\nSaved {len(verify_data)} companies to {outfile}")
    print(f"Scrape success: {sum(1 for v in verify_data if v['scrape_success'])}/{len(verify_data)}")

    # Print for quick review
    for v in verify_data:
        status = "OK" if v["scrape_success"] else "FAIL"
        text_preview = v["website_text"][:80] if v["website_text"] else "(no text)"
        print(f"  [{status}] {v['name']} ({v['domain']}) — {text_preview}")

asyncio.run(main())
