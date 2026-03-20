"""
Apollo People UI adapter — wraps scripts/apollo_god_search.js Puppeteer script.
Executes People tab search with keyword (Strategy A) or seniority (Strategy B) approach.
"""
import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "apollo_god_search.js"


class ApolloPeopleUIFilters(BaseModel):
    """Filters for Apollo People tab (Puppeteer emulator)."""
    person_locations: List[str] = Field(default_factory=list, description="e.g. ['Dubai, United Arab Emirates']")
    person_seniorities: List[str] = Field(default_factory=list, description="e.g. ['founder', 'c_suite', 'owner']")
    organization_num_employees_ranges: List[str] = Field(default_factory=list, description="e.g. ['1,10', '11,50']")
    q_organization_name: Optional[str] = None
    organization_industry_tag_ids: List[str] = Field(default_factory=list)
    person_titles: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    strategy: str = Field(default="all", description="'A' (keywords), 'B' (seniority), or 'all'")
    max_pages: int = Field(default=10, ge=1, le=100)
    city: Optional[str] = None

    class Config:
        extra = "allow"


class ApolloPeopleUIAdapter(GatheringAdapter):
    source_type = "apollo.people.emulator"
    source_label = "Apollo People Search (Puppeteer)"
    filter_model = ApolloPeopleUIFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ApolloPeopleUIFilters(**raw_filters).model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloPeopleUIFilters(**filters)
        # Each page ~25 results, people search is free (no credit cost for viewing)
        estimated = validated.max_pages * 25
        cities = 1 if validated.city else 3
        if validated.strategy.upper() == "A":
            estimated *= 80  # ~80 keyword combos
        elif validated.strategy.upper() == "B":
            estimated *= len(validated.person_seniorities or ["founder", "c_suite", "owner"]) * len(validated.organization_num_employees_ranges or ["1,10", "11,50", "51,100"])
        else:
            estimated *= cities * 40  # rough estimate

        return EstimateResult(
            estimated_companies=min(estimated, 20000),
            estimated_credits=0,
            notes=f"Puppeteer scrape, strategy={validated.strategy}, max_pages={validated.max_pages}. Free (no Apollo credits).",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = ApolloPeopleUIFilters(**filters)

        if not SCRIPT_PATH.exists():
            return GatheringResult(error_message=f"Script not found: {SCRIPT_PATH}")

        # Build command args
        args = ["node", str(SCRIPT_PATH)]
        if validated.strategy and validated.strategy.lower() != "all":
            args.extend(["--strategy", validated.strategy.upper()])
        if validated.max_pages:
            args.extend(["--max-pages", str(validated.max_pages)])
        if validated.city:
            args.extend(["--city", validated.city])

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SCRIPT_PATH.parent.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3600)

            if proc.returncode != 0:
                return GatheringResult(
                    error_message=f"Script failed (rc={proc.returncode}): {stderr.decode()[:2000]}"
                )

            # Read output files
            data_dir = SCRIPT_PATH.parent.parent / "easystaff-global" / "data"
            companies_file = data_dir / "uae_god_search_companies.json"
            people_file = data_dir / "uae_god_search_people.json"

            companies = []
            if companies_file.exists():
                with open(companies_file) as f:
                    raw = json.load(f)
                for item in raw:
                    domain = item.get("domain", "")
                    if domain:
                        # Normalize: strip protocol/paths
                        if "://" in domain:
                            from urllib.parse import urlparse
                            domain = urlparse(domain).netloc or domain
                        companies.append({
                            "domain": domain.lower().replace("www.", ""),
                            "name": item.get("name", ""),
                            "employees": item.get("employees"),
                            "industry": item.get("industry", ""),
                            "city": item.get("city", ""),
                            "country": item.get("country", ""),
                            "linkedin_url": item.get("linkedin_url", ""),
                            "raw_apollo": item,
                        })

            logger.info(f"Apollo People UI: {len(companies)} companies extracted")
            return GatheringResult(
                companies=companies,
                raw_results_count=len(companies),
                metadata={
                    "strategy": validated.strategy,
                    "people_file": str(people_file) if people_file.exists() else None,
                },
            )

        except asyncio.TimeoutError:
            return GatheringResult(error_message="Script timed out after 1 hour")
        except Exception as e:
            logger.error(f"Apollo People UI failed: {e}")
            return GatheringResult(error_message=str(e))


from . import register_adapter  # noqa: E402
register_adapter(ApolloPeopleUIAdapter)
