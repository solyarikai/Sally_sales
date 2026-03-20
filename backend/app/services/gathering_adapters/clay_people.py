"""
Clay People adapter — wraps clay_service.run_people_search().
"""
import logging
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class ClayPeopleFilters(BaseModel):
    """Filters for Clay People search."""
    domains: List[str] = Field(default_factory=list, description="Company domains to search people for")
    use_titles: bool = False
    job_title: Optional[str] = None
    name: Optional[str] = None
    countries: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)
    schools: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class ClayPeopleAdapter(GatheringAdapter):
    source_type = "clay.people.emulator"
    source_label = "Clay People Search (Puppeteer)"
    filter_model = ClayPeopleFilters

    async def validate(self, raw_filters: dict) -> dict:
        validated = ClayPeopleFilters(**raw_filters)
        if not validated.domains:
            raise ValueError("domains list is required for Clay people search")
        return validated.model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ClayPeopleFilters(**filters)
        # ~5-10 people per domain
        estimated = len(validated.domains) * 7
        return EstimateResult(
            estimated_companies=estimated,
            estimated_credits=len(validated.domains),
            estimated_cost_usd=len(validated.domains) * 0.01,
            notes=f"Clay people search across {len(validated.domains)} domains.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        from app.services.clay_service import clay_service

        validated = ClayPeopleFilters(**filters)

        try:
            result = await clay_service.run_people_search(
                domains=validated.domains,
                use_titles=validated.use_titles,
                job_title=validated.job_title,
                name=validated.name,
                countries=validated.countries,
                cities=validated.cities,
                schools=validated.schools,
                languages=validated.languages,
                on_progress=on_progress,
            )

            people = result.get("people", [])
            # Group people by company domain → company records
            domain_map = {}
            for person in people:
                domain = person.get("company_domain", "") or person.get("domain", "")
                if domain and domain not in domain_map:
                    domain_map[domain] = {
                        "domain": domain.lower(),
                        "name": person.get("company_name", ""),
                        "people_found": [],
                        "raw_clay": person,
                    }
                if domain:
                    domain_map[domain]["people_found"].append({
                        "name": person.get("name", ""),
                        "title": person.get("title", ""),
                        "email": person.get("email", ""),
                        "linkedin_url": person.get("linkedin_url", ""),
                    })

            companies = list(domain_map.values())
            logger.info(f"Clay people: {len(people)} people across {len(companies)} companies")
            return GatheringResult(
                companies=companies,
                raw_results_count=len(people),
                credits_used=len(validated.domains),
                metadata={"table_url": result.get("table_url"), "total_people": len(people)},
            )

        except Exception as e:
            logger.error(f"Clay people failed: {e}")
            return GatheringResult(error_message=str(e))


from . import register_adapter  # noqa: E402
register_adapter(ClayPeopleAdapter)
