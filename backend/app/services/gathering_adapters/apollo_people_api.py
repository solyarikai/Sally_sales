"""
Apollo People API adapter — searches people by domain using Apollo.io API.

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
        description="Company domains to search people for.",
    )
    person_titles: List[str] = Field(
        default_factory=list,
        description="Job title keywords to filter by e.g. ['CEO', 'founder', 'head of buying']",
    )
    max_people_per_domain: int = Field(
        default=5, ge=1, le=10,
        description="Max people to return per domain (Apollo API max = 10 per page).",
    )

    class Config:
        extra = "allow"


class ApolloPeopleAPIAdapter(GatheringAdapter):
    source_type = "apollo.people.api"
    source_label = "Apollo People Search (API, free)"
    filter_model = ApolloPeopleAPIFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ApolloPeopleAPIFilters(**raw_filters).model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloPeopleAPIFilters(**filters)
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
        domains = validated.organization_domains
        titles = validated.person_titles or None
        per_domain = validated.max_people_per_domain

        if not domains:
            return GatheringResult(error_message="No domains provided")

        if not apollo_service.is_configured():
            return GatheringResult(error_message="Apollo API key not configured")

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
                        "email": "",  # Not revealed at gather phase — FindyMail does this at CP3
                    })

            except Exception as e:
                logger.warning(f"Apollo API search failed for {domain}: {e}")
                errors.append(f"{domain}: {str(e)}")

            # Apollo rate limit: 200 req/min → 0.3s per call is safe
            await asyncio.sleep(0.3)

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
                "strategy": "api_search",
                "total_domains": len(domains),
                "errors": errors,
                "people": all_people,
            },
        )


from . import register_adapter  # noqa: E402
register_adapter(ApolloPeopleAPIAdapter)
