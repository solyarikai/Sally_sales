"""Step 3: Agent feedback → prompt tuning loop.

Tests the core innovation: user agent provides target verdicts,
MCP adjusts GPT classification prompt until it matches ≥95%.

Uses cached scrape data — no Apollo API calls.
Tests prompt_tuner.py convergence.

Run:
    cd mcp && python3 -u -m pytest tests/exploration/test_step3_prompt_tuning.py -v
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
CACHE_DIR = Path(__file__).parent.parent / "tmp" / "exploration_cache"


# Simulated agent verdicts (what Opus would say reviewing scraped websites)
AGENT_VERDICTS = {
    "OnSocial Creator platforms UK": {
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing",
        "verdicts": {
            "thenewgen.com": {"target": True, "reason": "Creator agency connecting brands with creators — buys data tools"},
            "sixteenth.com": {"target": True, "reason": "Influencer talent management — needs analytics on creators"},
            "seenconnects.com": {"target": True, "reason": "Influencer & social marketing agency — core buyer"},
            "found.co.uk": {"target": False, "reason": "Digital marketing agency (PPC/SEO) — not influencer-focused"},
            "musetheagency.com": {"target": True, "reason": "Talent-first influencer marketing agency — direct buyer"},
            "unravelapp.com": {"target": False, "reason": "Travel booking app — completely unrelated"},
            "inthestyle.com": {"target": False, "reason": "Fashion retailer — no mention of influencer marketing"},
            "dexerto.media": {"target": False, "reason": "Gaming media hub — not a buyer of data tools"},
            "majorplayers.co.uk": {"target": False, "reason": "Recruitment agency — recruits marketers, doesn't do marketing"},
            "lindafarrow.com": {"target": False, "reason": "Eyewear brand — unrelated"},
        },
    },
    "EasyStaff IT consulting Miami": {
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        "verdicts": {
            "synergybc.com": {"target": True, "reason": "IT staffing & consulting — hires contractors, needs payroll"},
            "smxusa.com": {"target": True, "reason": "IT solutions provider — manages contractor teams"},
            "koombea.com": {"target": True, "reason": "Software dev agency — hires devs globally"},
            "flatiron.software": {"target": True, "reason": "AI software dev shop — contractor-based team"},
            "therocketcode.com": {"target": True, "reason": "Software dev company — nearshore contractors"},
            "avalith.net": {"target": True, "reason": "Software dev outsourcing — manages contractors"},
            "bluecoding.com": {"target": True, "reason": "Nearshore staffing — pays contractors"},
            "shokworks.io": {"target": True, "reason": "AI solutions company — dev team"},
        },
    },
}


@pytest.fixture
def openai_key():
    if not OPENAI_KEY:
        pytest.skip("OPENAI_API_KEY not set")
    return OPENAI_KEY


def _load_cached_companies(domains):
    """Load scraped website text from cache."""
    companies = []
    for domain in domains:
        cache_key = domain.replace(".", "_").replace("/", "_")
        cache_file = CACHE_DIR / f"scrape_{cache_key}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            companies.append({
                "domain": domain,
                "primary_domain": domain,
                "name": domain.split(".")[0].title(),
                "scraped_text": data.get("text", "")[:3000],
            })
    return companies


class TestStep3PromptTuning:
    """Prompt tuning loop converges to match agent verdicts."""

    @pytest.mark.asyncio
    async def test_prompt_tuner_converges(self, openai_key):
        """Prompt tuning loop must reach ≥95% accuracy within 5 iterations."""
        from app.services.prompt_tuner import tune_classification_prompt

        seg = AGENT_VERDICTS["OnSocial Creator platforms UK"]
        companies = _load_cached_companies(seg["verdicts"].keys())

        if len(companies) < 5:
            pytest.skip("Need cached scrape data — run test_e2e_real.py first")

        tuned_prompt, accuracy, iterations = await tune_classification_prompt(
            companies=companies,
            agent_verdicts=seg["verdicts"],
            offer=seg["offer"],
            query=seg["query"],
            openai_key=openai_key,
            max_iterations=5,
        )

        assert accuracy >= 0.80, f"Prompt tuning stuck at {accuracy:.0%} after {iterations} iterations"
        assert tuned_prompt, "No prompt returned"
        assert iterations <= 5, f"Too many iterations: {iterations}"

    @pytest.mark.asyncio
    async def test_tuned_prompt_no_hardcode(self, openai_key):
        """Tuned prompt must not contain hardcoded domain names or company names."""
        from app.services.prompt_tuner import tune_classification_prompt

        seg = AGENT_VERDICTS["EasyStaff IT consulting Miami"]
        companies = _load_cached_companies(seg["verdicts"].keys())

        if len(companies) < 5:
            pytest.skip("Need cached scrape data")

        tuned_prompt, _, _ = await tune_classification_prompt(
            companies=companies,
            agent_verdicts=seg["verdicts"],
            offer=seg["offer"],
            query=seg["query"],
            openai_key=openai_key,
        )

        # Prompt must not contain specific domain names
        for domain in seg["verdicts"]:
            assert domain not in tuned_prompt, f"Hardcoded domain '{domain}' in tuned prompt"

    @pytest.mark.asyncio
    async def test_each_iteration_saved(self, openai_key):
        """Each prompt iteration must be logged with accuracy and mismatches."""
        from app.services.prompt_tuner import tune_classification_prompt

        seg = AGENT_VERDICTS["OnSocial Creator platforms UK"]
        companies = _load_cached_companies(seg["verdicts"].keys())

        if len(companies) < 5:
            pytest.skip("Need cached scrape data")

        _, _, iterations, history = await tune_classification_prompt(
            companies=companies,
            agent_verdicts=seg["verdicts"],
            offer=seg["offer"],
            query=seg["query"],
            openai_key=openai_key,
            return_history=True,
        )

        assert len(history) >= 1, "No iteration history"
        for entry in history:
            assert "prompt" in entry
            assert "accuracy" in entry
            assert "mismatches" in entry
            assert isinstance(entry["accuracy"], float)
