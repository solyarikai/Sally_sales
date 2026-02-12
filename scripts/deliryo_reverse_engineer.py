"""
Deliryo Reverse-Engineer Apollo Filters
========================================
Call Apollo /organizations/enrich for ALL Deliryo targets (FREE, no credits).
Store industry, keywords, country, etc. and extract patterns for better search filters.
Then update discovered_companies with Apollo org data.
"""
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("deliryo_re")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROJECT_ID = 18


async def enrich_org_by_domain(client, api_key: str, domain: str) -> Optional[Dict]:
    """Call Apollo /organizations/enrich (FREE endpoint)."""
    try:
        resp = await client.post(
            "https://api.apollo.io/api/v1/organizations/enrich",
            json={"domain": domain},
            headers={"Content-Type": "application/json", "X-Api-Key": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("organization")
        return None
    except Exception as e:
        logger.error(f"Enrich failed for {domain}: {e}")
        return None


async def main():
    import httpx
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select, text

    APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "9yIx2mZegixXHeDf6mWVqA")

    logger.info("=" * 60)
    logger.info("DELIRYO REVERSE-ENGINEER APOLLO FILTERS")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Get all target domains
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        targets = list(result.scalars().all())
        logger.info(f"Found {len(targets)} target companies")

        # Enrich all via Apollo (FREE)
        industries = Counter()
        keywords_counter = Counter()
        countries = Counter()
        employee_ranges = Counter()
        enriched_count = 0
        all_orgs = []

        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(5)  # 5 concurrent

            async def enrich_one(dc: DiscoveredCompany):
                nonlocal enriched_count
                async with semaphore:
                    org = await enrich_org_by_domain(client, APOLLO_API_KEY, dc.domain)
                    if org and org.get("name"):
                        enriched_count += 1
                        all_orgs.append({"domain": dc.domain, "org": org})

                        # Collect patterns
                        if org.get("industry"):
                            industries[org["industry"]] += 1
                        for kw in (org.get("keywords") or []):
                            keywords_counter[kw] += 1
                        if org.get("country"):
                            countries[org["country"]] += 1
                        emp = org.get("estimated_num_employees")
                        if emp:
                            if emp <= 10: employee_ranges["1-10"] += 1
                            elif emp <= 50: employee_ranges["11-50"] += 1
                            elif emp <= 200: employee_ranges["51-200"] += 1
                            elif emp <= 1000: employee_ranges["201-1000"] += 1
                            else: employee_ranges["1000+"] += 1

                        # Update DC with Apollo org data
                        if not dc.company_info:
                            dc.company_info = {}
                        apollo_data = {
                            "apollo_name": org.get("name"),
                            "apollo_industry": org.get("industry"),
                            "apollo_keywords": org.get("keywords", []),
                            "apollo_country": org.get("country"),
                            "apollo_city": org.get("city"),
                            "apollo_employees": org.get("estimated_num_employees"),
                            "apollo_annual_revenue": org.get("annual_revenue"),
                            "apollo_founded_year": org.get("founded_year"),
                            "apollo_linkedin_url": org.get("linkedin_url"),
                            "apollo_short_description": org.get("short_description"),
                        }
                        dc.company_info = {**(dc.company_info or {}), **apollo_data}

                    await asyncio.sleep(0.1)  # Be nice to API

            # Run all in parallel (5 at a time)
            tasks = [enrich_one(dc) for dc in targets]
            await asyncio.gather(*tasks, return_exceptions=True)

        await session.commit()

        # Print patterns
        logger.info(f"\n{'='*60}")
        logger.info(f"REVERSE-ENGINEERED APOLLO FILTERS")
        logger.info(f"{'='*60}")
        logger.info(f"Targets enriched by Apollo: {enriched_count}/{len(targets)}")

        logger.info(f"\n--- TOP INDUSTRIES ---")
        for ind, cnt in industries.most_common(20):
            logger.info(f"  {ind}: {cnt}")

        logger.info(f"\n--- TOP KEYWORDS ---")
        for kw, cnt in keywords_counter.most_common(30):
            logger.info(f"  {kw}: {cnt}")

        logger.info(f"\n--- TOP COUNTRIES ---")
        for country, cnt in countries.most_common(20):
            logger.info(f"  {country}: {cnt}")

        logger.info(f"\n--- EMPLOYEE RANGES ---")
        for rng, cnt in employee_ranges.most_common():
            logger.info(f"  {rng}: {cnt}")

        # Store patterns in ProjectSearchKnowledge (same as Yandex query data)
        from app.models.domain import ProjectSearchKnowledge
        from sqlalchemy import select as sa_select

        knowledge_result = await session.execute(
            sa_select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == PROJECT_ID
            )
        )
        knowledge = knowledge_result.scalar_one_or_none()
        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=PROJECT_ID)
            session.add(knowledge)

        # Store Apollo reverse-engineered filters as industry_keywords
        apollo_filters = {
            "apollo_industries": industries.most_common(30),
            "apollo_keywords": keywords_counter.most_common(50),
            "apollo_countries": countries.most_common(20),
            "apollo_employee_ranges": dict(employee_ranges),
            "apollo_enriched_targets": enriched_count,
            "apollo_total_targets": len(targets),
        }
        # Merge with existing industry_keywords (may have Yandex data)
        existing = knowledge.industry_keywords or []
        if isinstance(existing, list):
            existing = {"yandex_patterns": existing}
        existing["apollo_patterns"] = apollo_filters
        knowledge.industry_keywords = existing
        knowledge.total_targets_found = len(targets)

        await session.commit()
        logger.info(f"\nStored Apollo patterns in ProjectSearchKnowledge (project_id={PROJECT_ID})")

        # Save full data to file as backup
        output = {
            "enriched_count": enriched_count,
            "total_targets": len(targets),
            "industries": industries.most_common(30),
            "keywords": keywords_counter.most_common(50),
            "countries": countries.most_common(20),
            "employee_ranges": dict(employee_ranges),
            "orgs": all_orgs,
        }
        with open("/scripts/deliryo_apollo_patterns.json", "w") as f:
            json.dump(output, f, indent=2, default=str)
        logger.info(f"Saved full data to /scripts/deliryo_apollo_patterns.json")


if __name__ == "__main__":
    asyncio.run(main())
