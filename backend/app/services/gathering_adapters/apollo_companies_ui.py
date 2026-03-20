"""
Apollo Companies UI adapter — wraps scripts/apollo_universal_search.js Puppeteer script.
Scrapes Apollo Companies tab with industry tags + keyword search.

Now uses universal script that accepts parameters for any location/keyword.
"""
import asyncio
import json
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "apollo_universal_search.js"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "gathering-data"


class ApolloCompaniesUIFilters(BaseModel):
    """Filters for Apollo Companies tab (Puppeteer emulator)."""
    organization_locations: List[str] = Field(default_factory=list, description="e.g. ['Poland', 'Romania']")
    organization_industry_tag_ids: List[str] = Field(default_factory=list)
    q_keywords: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords to search, e.g. ['PHP', 'Laravel']")
    organization_num_employees_ranges: List[str] = Field(
        default_factory=lambda: ["11,50", "51,200"]
    )
    sort_by_field: str = "recommendations_score"
    max_pages: int = Field(default=50, ge=1, le=500)
    resume: bool = False

    class Config:
        extra = "allow"


class ApolloCompaniesUIAdapter(GatheringAdapter):
    source_type = "apollo.companies.emulator"
    source_label = "Apollo Companies Tab (Puppeteer)"
    filter_model = ApolloCompaniesUIFilters

    async def validate(self, raw_filters: dict) -> dict:
        # Handle keywords from various formats
        if 'q_keywords' in raw_filters and raw_filters['q_keywords']:
            kw = raw_filters['q_keywords']
            if isinstance(kw, str):
                raw_filters.setdefault('keywords', []).extend(kw.split(','))
            elif isinstance(kw, list):
                raw_filters.setdefault('keywords', []).extend(kw)

        validated = ApolloCompaniesUIFilters(**raw_filters)

        # Require at least one location
        if not validated.organization_locations:
            raise ValueError("organization_locations is required (e.g. ['Poland'])")

        return validated.model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloCompaniesUIFilters(**filters)
        # Companies tab shows ~25 per page, up to max_pages
        # Multiply by number of keyword×size combinations
        num_searches = max(1, len(validated.keywords)) * len(validated.organization_num_employees_ranges)
        estimated = validated.max_pages * 25 * num_searches

        return EstimateResult(
            estimated_companies=min(estimated, 50000),
            estimated_credits=0,
            notes=f"Puppeteer scrape: {validated.organization_locations}, keywords={validated.keywords or 'all'}, max_pages={validated.max_pages}. Free (no credits).",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = ApolloCompaniesUIFilters(**filters)

        if not SCRIPT_PATH.exists():
            return GatheringResult(error_message=f"Script not found: {SCRIPT_PATH}")

        # Build command args
        args = ["node", str(SCRIPT_PATH)]

        # Add locations
        for loc in validated.organization_locations:
            args.extend(["--location", loc])

        # Add keywords
        if validated.keywords:
            args.extend(["--keywords", ",".join(validated.keywords)])

        # Add size ranges
        for size in validated.organization_num_employees_ranges:
            args.extend(["--sizes", size])

        # Max pages
        args.extend(["--max-pages", str(validated.max_pages)])

        # Output directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        args.extend(["--output-dir", str(OUTPUT_DIR)])

        # Generate unique output filename based on filters
        filter_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:8]
        loc_slug = validated.organization_locations[0].lower().replace(" ", "_")[:20] if validated.organization_locations else "unknown"
        output_file = f"{loc_slug}_{filter_hash}_companies.json"
        args.extend(["--output-file", output_file])

        if validated.resume:
            args.append("--resume")

        logger.info(f"Apollo Companies UI: executing {' '.join(args)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SCRIPT_PATH.parent.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=7200)

            stdout_text = stdout.decode()
            stderr_text = stderr.decode()

            logger.info(f"Script stdout: {stdout_text[-500:]}")
            if stderr_text:
                logger.warning(f"Script stderr: {stderr_text[-500:]}")

            if proc.returncode != 0:
                return GatheringResult(
                    error_message=f"Script failed (rc={proc.returncode}): {stderr_text[:2000]}"
                )

            # Read output file
            results_file = OUTPUT_DIR / output_file

            companies = []
            if results_file.exists():
                with open(results_file) as f:
                    raw = json.load(f)
                for item in raw:
                    domain = item.get("domain", "")
                    # Normalize domain
                    if domain:
                        domain = domain.lower().replace("www.", "")

                    companies.append({
                        "domain": domain,
                        "name": item.get("name", ""),
                        "employees": item.get("employees"),
                        "linkedin_url": item.get("linkedin_url", ""),
                        "apollo_id": item.get("id", ""),
                        "raw_apollo": item,
                    })
            else:
                # Try reading from stdout JSON
                try:
                    result = json.loads(stdout_text.strip().split('\n')[-1])
                    if result.get("error"):
                        return GatheringResult(error_message=result["error"])
                except:
                    pass

            logger.info(f"Apollo Companies UI: {len(companies)} companies extracted from {results_file}")
            return GatheringResult(
                companies=companies,
                raw_results_count=len(companies),
                metadata={
                    "locations": validated.organization_locations,
                    "keywords": validated.keywords,
                    "output_file": str(results_file),
                },
            )

        except asyncio.TimeoutError:
            return GatheringResult(error_message="Script timed out after 2 hours")
        except Exception as e:
            logger.error(f"Apollo Companies UI failed: {e}")
            return GatheringResult(error_message=str(e))


from . import register_adapter  # noqa: E402
register_adapter(ApolloCompaniesUIAdapter)
