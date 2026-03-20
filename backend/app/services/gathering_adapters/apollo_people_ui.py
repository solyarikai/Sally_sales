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
    strategy: str = Field(default="all", description="'A' (keywords), 'B' (seniority), 'domains' (by domain list), or 'all'")
    max_pages: int = Field(default=10, ge=1, le=100)
    city: Optional[str] = None
    organization_domains: List[str] = Field(default_factory=list, description="Company domains to search people for. Batched in groups of 30.")
    batch_size: int = Field(default=30, ge=5, le=50, description="Number of domains per Apollo search batch")

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

        if validated.organization_domains:
            # Domain-based search: batch domains, each batch yields ~25*max_pages results
            n_batches = (len(validated.organization_domains) + validated.batch_size - 1) // validated.batch_size
            estimated = n_batches * validated.max_pages * 25
            return EstimateResult(
                estimated_companies=min(estimated, 20000),
                estimated_credits=0,
                notes=f"Puppeteer scrape across {len(validated.organization_domains)} domains "
                      f"({n_batches} batches of {validated.batch_size}), "
                      f"max {validated.max_pages} pages/batch. Free (no Apollo credits).",
            )

        # Legacy: broad search estimation
        estimated = validated.max_pages * 25
        cities = 1 if validated.city else 3
        if validated.strategy.upper() == "A":
            estimated *= 80
        elif validated.strategy.upper() == "B":
            estimated *= len(validated.person_seniorities or ["founder", "c_suite", "owner"]) * len(validated.organization_num_employees_ranges or ["1,10", "11,50", "51,100"])
        else:
            estimated *= cities * 40

        return EstimateResult(
            estimated_companies=min(estimated, 20000),
            estimated_credits=0,
            notes=f"Puppeteer scrape, strategy={validated.strategy}, max_pages={validated.max_pages}. Free (no Apollo credits).",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = ApolloPeopleUIFilters(**filters)

        # Domain-based search: use apollo_scraper.js with batched URLs
        if validated.organization_domains:
            return await self._execute_domain_search(validated, on_progress)

        # Legacy: broad keyword/seniority search via apollo_god_search.js
        return await self._execute_legacy_search(validated, on_progress)

    async def _execute_domain_search(self, validated: ApolloPeopleUIFilters, on_progress: Optional[Callable] = None) -> GatheringResult:
        """Search Apollo People tab filtered by specific company domains."""
        from urllib.parse import quote

        scraper_script = SCRIPT_PATH.parent.parent / "scripts" / "apollo_scraper.js"
        if not scraper_script.exists():
            return GatheringResult(error_message=f"Script not found: {scraper_script}")

        domains = validated.organization_domains
        titles = validated.person_titles
        batch_size = validated.batch_size
        max_pages = validated.max_pages

        # Batch domains
        batches = [domains[i:i + batch_size] for i in range(0, len(domains), batch_size)]
        logger.info(f"Apollo People domain search: {len(domains)} domains, {len(batches)} batches, titles={titles}")

        all_people = []
        errors = []

        for batch_idx, batch_domains in enumerate(batches):
            # Build Apollo People search URL with organizationDomains[] + personTitles[]
            url = "https://app.apollo.io/#/people?finderViewId=5b8050d050a0710001ca27c1"
            for d in batch_domains:
                url += f"&organizationDomains[]={quote(d)}"
            for t in titles:
                url += f"&personTitles[]={quote(t)}"

            # Use a temp file for this batch's output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, prefix=f'apollo_batch{batch_idx}_') as tf:
                output_file = tf.name

            args = ["node", str(scraper_script), "--url", url, "--max-pages", str(max_pages), "--output", output_file]

            try:
                if on_progress:
                    await on_progress(f"Batch {batch_idx + 1}/{len(batches)}: {len(batch_domains)} domains")

                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(scraper_script.parent.parent),
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

                if proc.returncode != 0:
                    err_msg = stderr.decode()[:500]
                    logger.warning(f"Batch {batch_idx + 1} failed (rc={proc.returncode}): {err_msg}")
                    errors.append(f"Batch {batch_idx + 1}: {err_msg}")
                    continue

                # Read batch results
                if Path(output_file).exists():
                    with open(output_file) as f:
                        batch_people = json.load(f)
                    all_people.extend(batch_people)
                    logger.info(f"Batch {batch_idx + 1}/{len(batches)}: {len(batch_people)} people")

            except asyncio.TimeoutError:
                logger.warning(f"Batch {batch_idx + 1} timed out")
                errors.append(f"Batch {batch_idx + 1}: timeout")
            except Exception as e:
                logger.warning(f"Batch {batch_idx + 1} error: {e}")
                errors.append(f"Batch {batch_idx + 1}: {str(e)}")
            finally:
                try:
                    Path(output_file).unlink(missing_ok=True)
                except Exception:
                    pass

            # Rate limit between batches
            await asyncio.sleep(3)

        # Deduplicate by name+company
        seen = set()
        unique_people = []
        for p in all_people:
            key = f"{p.get('name', '')}|||{p.get('company', '')}".lower()
            if key not in seen:
                seen.add(key)
                unique_people.append(p)

        # Convert people to company records for the pipeline
        domain_map = {}
        for person in unique_people:
            company = person.get("company", "")
            if company and company not in domain_map:
                domain_map[company] = {
                    "domain": "",
                    "name": company,
                    "people_found": [],
                    "raw_apollo": {},
                }
            if company:
                domain_map[company]["people_found"].append(person)

        companies = list(domain_map.values())

        logger.info(f"Apollo People domain search: {len(unique_people)} unique people across {len(companies)} companies")

        return GatheringResult(
            companies=companies,
            raw_results_count=len(unique_people),
            metadata={
                "strategy": "domains",
                "total_domains": len(domains),
                "total_batches": len(batches),
                "errors": errors,
                "people": unique_people,
            },
        )

    async def _execute_legacy_search(self, validated: ApolloPeopleUIFilters, on_progress: Optional[Callable] = None) -> GatheringResult:
        """Legacy: broad keyword/seniority search via apollo_god_search.js."""
        if not SCRIPT_PATH.exists():
            return GatheringResult(error_message=f"Script not found: {SCRIPT_PATH}")

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
