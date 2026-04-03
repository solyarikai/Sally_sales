"""Step 4: Enrich targets → update taxonomy map → verify growth.

Tests that enrichment data flows into the shared keyword map,
embeddings are rebuilt, and subsequent queries benefit from new keywords.

REAL Apollo enrichment API calls.

Run:
    cd mcp && python3 -u -m pytest tests/exploration/test_step4_enrich_map.py -v
"""
import asyncio
import json
import os
import sys
from pathlib import Path

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


@pytest.fixture
def keys():
    if not OPENAI_KEY or not APOLLO_KEY:
        pytest.skip("Need OPENAI_API_KEY and APOLLO_API_KEY")
    return OPENAI_KEY, APOLLO_KEY


async def _enrich_domain(domain, apollo_key):
    """Call Apollo enrichment API for a single domain."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.apollo.io/api/v1/organizations/enrich",
            headers={"X-Api-Key": apollo_key},
            params={"domain": domain},
        )
        data = resp.json()
        return data.get("organization", {})


class TestStep4EnrichMap:
    """Enrichment grows the taxonomy map and embeddings are rebuilt."""

    @pytest.mark.asyncio
    async def test_enrichment_adds_keywords(self, keys):
        """Enriching a company must add its keyword_tags to the shared map."""
        from app.services.taxonomy_service import TaxonomyService

        # Use fresh instance to avoid state from previous tests
        svc = TaxonomyService()
        before = svc.stats()["keywords"]

        org = await _enrich_domain("seenconnects.com", keys[1])
        if not org:
            pytest.skip("Apollo enrichment returned no data")

        new_count = svc.add_from_enrichment(org, "influencer marketing")
        after = svc.stats()["keywords"]

        assert after >= before, f"Keywords didn't grow: {before} → {after}"
        assert new_count >= 0, f"Negative new count: {new_count}"

        # Verify keywords from this company are in the map
        kw_tags = org.get("keywords") or org.get("keyword_tags") or []
        if isinstance(kw_tags, str):
            kw_tags = kw_tags.split(",")
        all_kw = svc.get_all_keywords()
        for kw in kw_tags[:3]:
            kw = kw.strip().lower()
            if len(kw) > 2:
                assert kw in all_kw, f"Keyword '{kw}' from enrichment not in map"

    @pytest.mark.asyncio
    async def test_enrichment_adds_industry(self, keys):
        """Enriching a company must add its industry to the map."""
        from app.services.taxonomy_service import TaxonomyService

        svc = TaxonomyService()
        org = await _enrich_domain("trussardi.com", keys[1])
        if not org:
            pytest.skip("Apollo enrichment returned no data")

        svc.add_from_enrichment(org, "fashion")
        industry = org.get("industry", "")
        if industry:
            assert industry in svc.get_all_industries(), f"Industry '{industry}' not in map"

    @pytest.mark.asyncio
    async def test_embeddings_rebuilt_after_enrichment(self, keys):
        """New keywords from enrichment must get embeddings computed."""
        from app.services.taxonomy_service import TaxonomyService

        svc = TaxonomyService()
        org = await _enrich_domain("musetheagency.com", keys[1])
        if not org:
            pytest.skip("Apollo enrichment returned no data")

        svc.add_from_enrichment(org, "influencer marketing")
        rebuilt = await svc.rebuild_embeddings_if_needed(keys[0])

        stats = svc.stats()
        assert stats["keywords_with_embeddings"] == stats["keywords"], \
            f"Not all keywords have embeddings: {stats['keywords_with_embeddings']}/{stats['keywords']}"

    @pytest.mark.asyncio
    async def test_new_keywords_appear_in_shortlist(self, keys):
        """After enrichment, new keywords must be findable via embedding similarity."""
        from app.services.taxonomy_service import TaxonomyService

        svc = TaxonomyService()
        org = await _enrich_domain("seenconnects.com", keys[1])
        if not org:
            pytest.skip("Apollo enrichment returned no data")

        svc.add_from_enrichment(org, "influencer marketing")
        await svc.rebuild_embeddings_if_needed(keys[0])

        # Query for influencer marketing — should find keywords from seenconnects
        shortlist = await svc.get_keyword_shortlist("influencer marketing agencies", keys[0], top_n=50)
        assert len(shortlist) > 0, "Empty shortlist after enrichment"

        # At least some influencer-related keywords should be in shortlist
        influencer_kw = [k for k in shortlist if "influencer" in k or "social" in k or "marketing" in k]
        assert len(influencer_kw) > 0, f"No influencer keywords in shortlist: {shortlist[:10]}"
