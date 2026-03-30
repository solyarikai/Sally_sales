"""Step 1: User query → Apollo filters.

Tests the filter_mapper: industries + keywords + size + location.
Golden validation from GOLDEN_FILTERS.md.
NO Apollo API calls — only GPT for filter mapping.

Run:
    cd mcp && python3 -u -m pytest tests/exploration/test_step1_filters.py -v
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

_env = Path(__file__).parent.parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Golden validation set — from real E2E test results approved by user
GOLDEN = [
    {
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        "industries_must": ["information technology & services", "management consulting"],
        "industries_bad": ["internet", "information services", "computer software", "computer networking", "computer & network security"],
        "keywords_must_contain": ["it consulting"],  # at least one keyword contains this
        "location_must_contain": "miami",
        "size_must_include": ["11,50", "51,200"],
    },
    {
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "industries_must": ["apparel & fashion", "luxury goods & jewelry"],
        "industries_bad": ["internet", "information services", "information technology & services"],
        "keywords_must_contain": ["fashion"],
        "location_must_contain": "italy",
        "size_must_include": ["51,200"],
    },
    {
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing",
        "industries_must": ["marketing & advertising"],
        "industries_bad": ["internet", "information services", "information technology & services", "computer software"],
        "keywords_must_contain": ["influencer"],
        "location_must_contain": "uk",
        "size_must_include": ["11,50", "51,200"],
    },
]


@pytest.fixture
def openai_key():
    if not OPENAI_KEY:
        pytest.skip("OPENAI_API_KEY not set")
    return OPENAI_KEY


class TestStep1Filters:
    """Golden validation: filter_mapper produces correct Apollo filters."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden", GOLDEN, ids=[g["query"][:30] for g in GOLDEN])
    async def test_industries_correct(self, golden, openai_key):
        """Industries must include all must-haves and exclude all bad ones."""
        from app.services.filter_mapper import map_query_to_filters

        result = await map_query_to_filters(golden["query"], golden["offer"], openai_key)
        industries = [i.lower() for i in result["mapping_details"]["industries_selected"]]

        for must in golden["industries_must"]:
            assert must in industries, f"Missing required industry: {must}. Got: {industries}"

        for bad in golden["industries_bad"]:
            assert bad not in industries, f"Bad industry present: {bad}. Got: {industries}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden", GOLDEN, ids=[g["query"][:30] for g in GOLDEN])
    async def test_keywords_relevant(self, golden, openai_key):
        """Keywords must contain segment-relevant terms from the taxonomy map."""
        from app.services.filter_mapper import map_query_to_filters

        result = await map_query_to_filters(golden["query"], golden["offer"], openai_key)
        keywords = [k.lower() for k in result["mapping_details"]["keywords_selected"]]
        unverified = [k.lower() for k in result["mapping_details"].get("unverified_keywords", [])]
        all_kw = keywords + unverified

        for must_contain in golden["keywords_must_contain"]:
            found = any(must_contain in k for k in all_kw)
            assert found, f"No keyword contains '{must_contain}'. Got: {all_kw}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden", GOLDEN, ids=[g["query"][:30] for g in GOLDEN])
    async def test_location_extracted(self, golden, openai_key):
        """Location must be extracted from query."""
        from app.services.filter_mapper import map_query_to_filters

        result = await map_query_to_filters(golden["query"], golden["offer"], openai_key)
        locations = [l.lower() for l in result["organization_locations"]]
        loc_str = " ".join(locations)

        assert golden["location_must_contain"] in loc_str, \
            f"Location missing '{golden['location_must_contain']}'. Got: {locations}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden", GOLDEN, ids=[g["query"][:30] for g in GOLDEN])
    async def test_size_ranges_valid(self, golden, openai_key):
        """Size ranges must be valid Apollo values and include expected ranges."""
        from app.services.filter_mapper import map_query_to_filters

        VALID = {"1,10", "11,50", "51,200", "201,500", "501,1000", "1001,5000", "5001,10000", "10001,"}
        result = await map_query_to_filters(golden["query"], golden["offer"], openai_key)
        ranges = result["organization_num_employees_ranges"]

        for r in ranges:
            assert r in VALID, f"Invalid range: {r}. Valid: {VALID}"

        for must in golden["size_must_include"]:
            assert must in ranges, f"Missing size range: {must}. Got: {ranges}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("golden", GOLDEN, ids=[g["query"][:30] for g in GOLDEN])
    async def test_all_industries_from_taxonomy(self, golden, openai_key):
        """Every industry in the output must exist in the taxonomy map."""
        from app.services.filter_mapper import map_query_to_filters
        from app.services.taxonomy_service import taxonomy_service

        result = await map_query_to_filters(golden["query"], golden["offer"], openai_key)
        valid = {i.lower() for i in taxonomy_service.get_all_industries()}
        industries = result["mapping_details"]["industries_selected"]

        for ind in industries:
            assert ind.lower() in valid, f"Industry '{ind}' not in taxonomy map ({len(valid)} known)"

    @pytest.mark.asyncio
    async def test_no_hardcoded_values_in_prompt(self, openai_key):
        """Verify the prompt contains no hardcoded segment/industry names."""
        from app.services.filter_mapper import _pick_industries
        import inspect

        source = inspect.getsource(_pick_industries)
        # Should not contain specific industry names as literal strings
        hardcoded = ["IT consulting", "fashion brand", "influencer marketing",
                     "information technology & services", "apparel & fashion",
                     "marketing & advertising"]
        for hc in hardcoded:
            assert hc not in source, f"Hardcoded value '{hc}' found in _pick_industries source"
