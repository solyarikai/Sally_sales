"""
Apollo People API adapter — searches people using Apollo.io API.

Two modes:
1. Domain-based: provide organization_domains → search people at specific companies
2. Broad search: provide organization_locations + q_organization_keyword_tags + person_titles
   → search people across all matching companies (no domains needed)

FREE step only: /mixed_people/api_search returns names + titles + LinkedIn URLs.
Does NOT call /people/bulk_match (email reveal = costs credits).
Emails are found later via FindyMail at Checkpoint 3 (standard pipeline flow).
"""
import asyncio
import logging
from typing import Optional, Callable, List, Dict, Any

from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class ApolloPeopleAPIFilters(BaseModel):
    """Filters for Apollo People search via API (free, no email reveal)."""
    organization_domains: List[str] = Field(
        default_factory=list,
        description="Company domains to search people for (domain-based mode).",
    )
    person_titles: List[str] = Field(
        default_factory=list,
        description="Job title keywords to filter by e.g. ['CEO', 'founder', 'head of buying']",
    )
    q_organization_keyword_tags: List[str] = Field(
        default_factory=list,
        description="Organization keyword tags for broad search e.g. ['software development', 'IT services']",
    )
    organization_locations: List[str] = Field(
        default_factory=list,
        description="Organization locations for broad search e.g. ['Poland', 'Romania']",
    )
    person_locations: List[str] = Field(
        default_factory=list,
        description="WHERE the person is located e.g. ['Mexico', 'Colombia', 'Brazil'] — use for corridor discovery.",
    )
    organization_num_employees_ranges: List[str] = Field(
        default_factory=list,
        description="Employee count ranges e.g. ['11,50', '51,200']",
    )
    max_people_per_domain: int = Field(
        default=5, ge=1, le=10,
        description="Max people to return per domain (domain-based mode only).",
    )
    max_pages: int = Field(
        default=50, ge=1, le=500,
        description="Max pages for broad search (100 people per page, max 500 pages = 50,000 people).",
    )

    class Config:
        extra = "allow"


class ApolloPeopleAPIAdapter(GatheringAdapter):
    source_type = "apollo.people.api"
    source_label = "Apollo People Search (API, free)"
    filter_model = ApolloPeopleAPIFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ApolloPeopleAPIFilters(**raw_filters).model_dump()

    def _is_broad_search(self, validated: ApolloPeopleAPIFilters) -> bool:
        """Broad search = no domains, has locations/keywords/person_locations."""
        return (
            not validated.organization_domains
            and (
                validated.organization_locations
                or validated.q_organization_keyword_tags
                or validated.person_locations
            )
        )

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloPeopleAPIFilters(**filters)

        if self._is_broad_search(validated):
            estimated_people = validated.max_pages * 100
            locations = ", ".join(validated.organization_locations[:5])
            if len(validated.organization_locations) > 5:
                locations += f" +{len(validated.organization_locations) - 5} more"
            return EstimateResult(
                estimated_companies=0,
                estimated_credits=0,
                estimated_cost_usd=0.0,
                notes=(
                    f"Apollo API broad people search (FREE, no credits). "
                    f"Locations: {locations}. "
                    f"Up to {validated.max_pages} pages × 100 = {estimated_people} people max. "
                    f"Titles: {', '.join(validated.person_titles[:5])}."
                ),
            )

        n = len(validated.organization_domains)
        estimated_people = n * validated.max_people_per_domain
        return EstimateResult(
            estimated_companies=n,
            estimated_credits=0,
            estimated_cost_usd=0.0,
            notes=(
                f"Apollo API free search across {n} domains, "
                f"up to {validated.max_people_per_domain} people each "
                f"(~{estimated_people} total). "
                f"No credits — search only, no email reveal."
            ),
        )

    async def execute(
        self,
        filters: dict,
        on_progress: Optional[Callable] = None,
    ) -> GatheringResult:
        from app.services.apollo_service import apollo_service

        validated = ApolloPeopleAPIFilters(**filters)

        if not apollo_service.is_configured():
            return GatheringResult(error_message="Apollo API key not configured")

        if self._is_broad_search(validated):
            return await self._execute_broad(validated, on_progress)
        elif validated.organization_domains:
            return await self._execute_by_domains(validated, on_progress)
        else:
            return GatheringResult(
                error_message="Provide either organization_domains (domain mode) or "
                "organization_locations + q_organization_keyword_tags (broad mode)"
            )

    async def _execute_broad(
        self,
        validated: ApolloPeopleAPIFilters,
        on_progress: Optional[Callable] = None,
    ) -> GatheringResult:
        """Broad search — find people by location + keywords + titles. FREE."""
        from app.services.apollo_service import apollo_service

        all_people: List[Dict[str, Any]] = []
        errors: List[str] = []

        for page in range(1, validated.max_pages + 1):
            try:
                if on_progress and page % 5 == 1:
                    await on_progress(
                        f"Broad search page {page}/{validated.max_pages}, "
                        f"{len(all_people)} people so far"
                    )

                data = await apollo_service.search_people_broad(
                    person_titles=validated.person_titles or None,
                    person_locations=validated.person_locations or None,
                    organization_keyword_tags=validated.q_organization_keyword_tags or None,
                    organization_locations=validated.organization_locations or None,
                    organization_num_employees_ranges=validated.organization_num_employees_ranges or None,
                    page=page,
                    per_page=100,
                )
                if not data:
                    logger.warning(f"Broad search page {page} returned None, stopping")
                    break

                people = data.get("people", [])
                if not people:
                    logger.info(f"Broad search page {page} empty, done. Total: {len(all_people)}")
                    break

                for p in people:
                    org = p.get("organization") or {}
                    domain = (org.get("website_url") or "").replace("http://www.", "").replace("https://www.", "").replace("http://", "").replace("https://", "").rstrip("/").lower()
                    all_people.append({
                        "apollo_id": p.get("id", ""),
                        "first_name": p.get("first_name", ""),
                        "last_name": p.get("last_name", ""),
                        "title": p.get("title", ""),
                        "company": org.get("name", ""),
                        "linkedin_url": p.get("linkedin_url", ""),
                        "domain": domain,
                        "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "email": "",
                        "raw": p,
                    })

                logger.info(f"Broad search page {page}: {len(people)} people, total {len(all_people)}")

            except Exception as e:
                logger.warning(f"Broad search page {page} failed: {e}")
                errors.append(f"page {page}: {str(e)}")

            await asyncio.sleep(apollo_service.RATE_LIMIT_INTERVAL)

        # Group people by domain into company records
        domain_map: Dict[str, dict] = {}
        for person in all_people:
            d = person["domain"]
            if not d:
                continue
            if d not in domain_map:
                domain_map[d] = {
                    "domain": d,
                    "name": person.get("company") or d,
                    "people_found": [],
                    "raw_apollo": {},
                }
            domain_map[d]["people_found"].append(person)

        companies = list(domain_map.values())
        logger.info(
            f"Apollo People API broad search: {len(all_people)} people across "
            f"{len(companies)} companies ({len(errors)} errors)"
        )

        return GatheringResult(
            companies=companies,
            raw_results_count=len(all_people),
            metadata={
                "strategy": "broad_search",
                "pages_fetched": min(len(all_people) // 100 + 1, validated.max_pages),
                "errors": errors,
                "people": all_people,
            },
        )

    async def _execute_by_domains(
        self,
        validated: ApolloPeopleAPIFilters,
        on_progress: Optional[Callable] = None,
    ) -> GatheringResult:
        """Domain-based search — find people at specific companies. FREE."""
        from app.services.apollo_service import apollo_service

        domains = validated.organization_domains
        titles = validated.person_titles or None
        per_domain = validated.max_people_per_domain

        all_people: List[Dict[str, Any]] = []
        errors: List[str] = []

        for i, domain in enumerate(domains):
            try:
                if on_progress:
                    await on_progress(f"Domain {i + 1}/{len(domains)}: {domain}")

                people = await apollo_service.search_people_by_domain(
                    domain=domain,
                    limit=per_domain,
                    titles=titles,
                )
                for p in people:
                    all_people.append({
                        **p,
                        "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "email": "",
                    })

            except Exception as e:
                logger.warning(f"Apollo API search failed for {domain}: {e}")
                errors.append(f"{domain}: {str(e)}")

            await asyncio.sleep(apollo_service.RATE_LIMIT_INTERVAL)

        # Group people by domain into company records
        domain_map: Dict[str, dict] = {}
        for person in all_people:
            d = person["domain"]
            if d not in domain_map:
                domain_map[d] = {
                    "domain": d,
                    "name": person.get("company") or d,
                    "people_found": [],
                    "raw_apollo": {},
                }
            domain_map[d]["people_found"].append(person)

        companies = list(domain_map.values())
        logger.info(
            f"Apollo People API: {len(all_people)} people across {len(companies)} domains "
            f"({len(errors)} errors)"
        )

        return GatheringResult(
            companies=companies,
            raw_results_count=len(all_people),
            metadata={
                "strategy": "domain_search",
                "total_domains": len(domains),
                "errors": errors,
                "people": all_people,
            },
        )


from . import register_adapter  # noqa: E402
register_adapter(ApolloPeopleAPIAdapter)
