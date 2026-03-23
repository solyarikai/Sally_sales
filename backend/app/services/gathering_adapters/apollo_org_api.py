"""
Apollo Organization API adapter — wraps apollo_service.search_organizations().
Simplest adapter: direct API call, no Puppeteer, no browser automation.
"""
import logging
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class ApolloOrgAPIFilters(BaseModel):
    """Filters for Apollo Organization Search API."""
    q_organization_keyword_tags: List[str] = Field(default_factory=list, description="Keywords to search organizations")
    organization_locations: List[str] = Field(default_factory=list, description="Location strings e.g. 'United Arab Emirates'")
    organization_num_employees_ranges: List[str] = Field(default_factory=list, description="Size ranges e.g. '1,10', '11,50'")
    organization_latest_funding_stage_cd: List[str] = Field(default_factory=list, description="Funding stages e.g. 'seed', 'series_a', 'series_b'")
    max_pages: int = Field(default=5, ge=1, le=100)
    per_page: int = Field(default=25, ge=1, le=100)

    class Config:
        extra = "allow"


class ApolloOrgAPIAdapter(GatheringAdapter):
    source_type = "apollo.companies.api"
    source_label = "Apollo Organization Search (API)"
    filter_model = ApolloOrgAPIFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ApolloOrgAPIFilters(**raw_filters).model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ApolloOrgAPIFilters(**filters)
        estimated = validated.max_pages * validated.per_page
        return EstimateResult(
            estimated_companies=estimated,
            estimated_credits=0,
            estimated_cost_usd=0.0,
            notes=f"Up to {estimated} orgs across {validated.max_pages} pages. Organization search is free.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        from app.services.apollo_service import apollo_service

        validated = ApolloOrgAPIFilters(**filters)
        all_companies = []
        total_pages = 0

        for page in range(1, validated.max_pages + 1):
            try:
                result = await apollo_service.search_organizations(
                    keyword_tags=validated.q_organization_keyword_tags,
                    locations=validated.organization_locations,
                    num_employees_ranges=validated.organization_num_employees_ranges,
                    latest_funding_stages=validated.organization_latest_funding_stage_cd or None,
                    page=page,
                    per_page=validated.per_page,
                )

                orgs = result.get("organizations", [])
                if not orgs:
                    break

                for org in orgs:
                    company = {
                        "domain": org.get("primary_domain", ""),
                        "name": org.get("name", ""),
                        "linkedin_url": org.get("linkedin_url", ""),
                        "employees": org.get("estimated_num_employees"),
                        "industry": org.get("industry", ""),
                        "city": org.get("city", ""),
                        "country": org.get("country", ""),
                        "raw_apollo": org,
                    }
                    if company["domain"]:
                        all_companies.append(company)

                total_pages += 1
                if on_progress:
                    on_progress({"page": page, "companies_so_far": len(all_companies)})

                if len(orgs) < validated.per_page:
                    break

            except Exception as e:
                logger.error(f"Apollo org search page {page} failed: {e}")
                return GatheringResult(
                    companies=all_companies,
                    raw_results_count=len(all_companies),
                    error_message=str(e),
                )

        logger.info(f"Apollo org API: {len(all_companies)} companies from {total_pages} pages")
        return GatheringResult(
            companies=all_companies,
            raw_results_count=len(all_companies),
            metadata={"pages_fetched": total_pages},
        )


# Self-register
from . import register_adapter  # noqa: E402
register_adapter(ApolloOrgAPIAdapter)
