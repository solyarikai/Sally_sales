"""
Apollo Companies UI adapter — wraps scripts/apollo_companies_god.js Puppeteer script.
Scrapes Apollo Companies tab with industry tags + keyword search.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "apollo_companies_god.js"


class ApolloCompaniesUIFilters(BaseModel):
    """Filters for Apollo Companies tab (Puppeteer emulator)."""
    organization_locations: List[str] = Field(default_factory=lambda: ["United Arab Emirates"])
    organization_industry_tag_ids: List[str] = Field(default_factory=list)
    q_keywords: Optional[str] = None
    organization_num_employees_ranges: List[str] = Field(
        default_factory=lambda: ["1,10", "11,20", "21,50", "51,100", "101,200"]
    )
    sort_by_field: str = "recommendations_score"
    max_pages: int = Field(default=100, ge=1, le=500)
    test_keyword: Optional[str] = None
    resume: bool = False

    class Config:
        extra = "allow"


class ApolloCompaniesUIAdapter(GatheringAdapter):
    source_type = "apollo.companies.emulator"
    source_label = "Apollo Companies Tab (Puppeteer)"
    filter_model = ApolloCompaniesUIFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ApolloCompaniesUIFilters(**raw_filters).model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloCompaniesUIFilters(**filters)
        # Companies tab shows ~25 per page, up to max_pages
        estimated = validated.max_pages * 25
        return EstimateResult(
            estimated_companies=min(estimated, 25000),
            estimated_credits=0,
            notes=f"Companies tab DOM scrape, max_pages={validated.max_pages}. Free (no credits).",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = ApolloCompaniesUIFilters(**filters)

        if not SCRIPT_PATH.exists():
            return GatheringResult(error_message=f"Script not found: {SCRIPT_PATH}")

        args = ["node", str(SCRIPT_PATH)]
        if validated.max_pages:
            args.extend(["--max-pages", str(validated.max_pages)])
        if validated.test_keyword:
            args.extend(["--test", validated.test_keyword])
        if validated.resume:
            args.append("--resume")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SCRIPT_PATH.parent.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=7200)

            if proc.returncode != 0:
                return GatheringResult(
                    error_message=f"Script failed (rc={proc.returncode}): {stderr.decode()[:2000]}"
                )

            # Read output
            data_dir = SCRIPT_PATH.parent.parent / "easystaff-global" / "data"
            results_file = data_dir / "uae_20k_companies.json"

            companies = []
            if results_file.exists():
                with open(results_file) as f:
                    raw = json.load(f)
                for item in raw:
                    linkedin_url = item.get("linkedin_url", "")
                    companies.append({
                        "domain": "",  # Companies tab often has no domain — needs RESOLVE phase
                        "name": item.get("name", ""),
                        "employees": item.get("employees"),
                        "linkedin_url": linkedin_url,
                        "apollo_id": item.get("id", ""),
                        "sources": item.get("_sources", []),
                        "raw_apollo": item,
                    })

            logger.info(f"Apollo Companies UI: {len(companies)} companies extracted")
            return GatheringResult(
                companies=companies,
                raw_results_count=len(companies),
            )

        except asyncio.TimeoutError:
            return GatheringResult(error_message="Script timed out after 2 hours")
        except Exception as e:
            logger.error(f"Apollo Companies UI failed: {e}")
            return GatheringResult(error_message=str(e))


from . import register_adapter  # noqa: E402
register_adapter(ApolloCompaniesUIAdapter)
