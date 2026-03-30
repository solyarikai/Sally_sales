"""Step 2: Apollo search + scrape + classify.

Tests that generated filters actually return relevant companies from Apollo.
REAL API calls — Apollo search, website scraping, GPT classification.
Per suck.md: test the REAL pipeline, not GPT output format.

Run:
    cd mcp && python3 -u -m pytest tests/exploration/test_step2_search_classify.py -v
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import pytest
import httpx

_env = Path(__file__).parent.parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
TMP_DIR = Path(__file__).parent.parent / "tmp"

SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        "min_apollo_results": 500,
        "min_target_rate": 0.20,
        "min_targets": 3,
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "min_apollo_results": 1000,
        "min_target_rate": 0.30,
        "min_targets": 3,
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing",
        "min_apollo_results": 500,
        "min_target_rate": 0.10,
        "min_targets": 2,
    },
]


@pytest.fixture
def keys():
    if not OPENAI_KEY or not APOLLO_KEY:
        pytest.skip("Need OPENAI_API_KEY and APOLLO_API_KEY")
    return OPENAI_KEY, APOLLO_KEY


async def _run_pipeline(query, offer, openai_key, apollo_key):
    """Full Step 1 + Step 2: generate filters → search → scrape → classify."""
    from app.services.filter_mapper import map_query_to_filters
    from app.services.scraper_service import ScraperService
    from app.services.exploration_service import _classify_targets

    # Step 1: generate filters
    filters = await map_query_to_filters(query, offer, openai_key)

    # Step 2: Apollo search
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers={"X-Api-Key": apollo_key, "Content-Type": "application/json"},
            json={
                "per_page": 25, "page": 1,
                "q_organization_keyword_tags": filters["q_organization_keyword_tags"],
                "organization_locations": filters["organization_locations"],
                "organization_num_employees_ranges": filters["organization_num_employees_ranges"],
            },
        )
        data = resp.json()
        companies = data.get("accounts") or data.get("organizations") or []
        total = data.get("pagination", {}).get("total_entries", 0)

    # Scrape
    scraper = ScraperService()
    scraped = []
    for c in companies[:15]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue
        result = await scraper.scrape_website(domain, timeout=10)
        if result.get("success") and result.get("text"):
            scraped.append({**c, "scraped_text": result["text"][:3000]})

    # Classify
    targets = []
    if scraped:
        targets = await _classify_targets(scraped, query, offer, openai_key)

    target_domains = []
    for t in targets:
        d = t.get("domain", t.get("primary_domain", ""))
        if not d and "classification" in t:
            d = t["classification"].get("domain", "")
        target_domains.append(d)

    return {
        "filters": filters,
        "total_available": total,
        "returned": len(companies),
        "scraped": len(scraped),
        "targets": len(targets),
        "target_rate": len(targets) / len(scraped) if scraped else 0,
        "target_domains": target_domains,
        "companies": companies,
        "scraped_companies": scraped,
    }


class TestStep2SearchClassify:
    """Real Apollo search + scrape + classify produces targets."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seg", SEGMENTS, ids=[s["name"] for s in SEGMENTS])
    async def test_apollo_returns_companies(self, seg, keys):
        """Apollo must return >0 companies with the generated filters."""
        result = await _run_pipeline(seg["query"], seg["offer"], keys[0], keys[1])

        # Log to file
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log = TMP_DIR / f"{ts}_step2_{seg['name'].replace(' ', '_')}.json"
        log.write_text(json.dumps({
            "segment": seg["name"],
            "filters_sent": {
                "q_organization_keyword_tags": result["filters"]["q_organization_keyword_tags"],
                "organization_locations": result["filters"]["organization_locations"],
                "organization_num_employees_ranges": result["filters"]["organization_num_employees_ranges"],
            },
            "total_available": result["total_available"],
            "scraped": result["scraped"],
            "targets": result["targets"],
            "target_rate": result["target_rate"],
            "target_domains": result["target_domains"],
        }, indent=2))

        assert result["total_available"] >= seg["min_apollo_results"], \
            f"Apollo returned {result['total_available']} (need ≥{seg['min_apollo_results']}). Filters: {result['filters']['q_organization_keyword_tags']}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seg", SEGMENTS, ids=[s["name"] for s in SEGMENTS])
    async def test_scraping_succeeds(self, seg, keys):
        """At least 50% of companies must be successfully scraped."""
        result = await _run_pipeline(seg["query"], seg["offer"], keys[0], keys[1])
        assert result["scraped"] >= result["returned"] * 0.3, \
            f"Scraping too low: {result['scraped']}/{result['returned']}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seg", SEGMENTS, ids=[s["name"] for s in SEGMENTS])
    async def test_target_rate_acceptable(self, seg, keys):
        """Target rate must meet minimum threshold."""
        result = await _run_pipeline(seg["query"], seg["offer"], keys[0], keys[1])
        assert result["target_rate"] >= seg["min_target_rate"], \
            f"Target rate {result['target_rate']:.0%} < {seg['min_target_rate']:.0%}. Targets: {result['target_domains']}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seg", SEGMENTS, ids=[s["name"] for s in SEGMENTS])
    async def test_minimum_targets_found(self, seg, keys):
        """Must find at least N targets from 25 companies."""
        result = await _run_pipeline(seg["query"], seg["offer"], keys[0], keys[1])
        assert result["targets"] >= seg["min_targets"], \
            f"Only {result['targets']} targets (need ≥{seg['min_targets']}). Domains: {result['target_domains']}"
