"""Apollo Organization API adapter — searches companies via Apollo API."""
from typing import Any, Dict, List
from app.services.gathering_adapters.base import BaseGatheringAdapter


class ApolloOrgApiAdapter(BaseGatheringAdapter):
    source_type = "apollo.companies.api"
    description = "Apollo org search API (1 credit per page)"

    def __init__(self, apollo_service=None):
        self._apollo = apollo_service

    def validate_filters(self, filters: Dict[str, Any]) -> tuple[bool, str]:
        if not filters.get("q_organization_keyword_tags") and not filters.get("organization_locations"):
            return False, "Need at least keyword_tags or locations"
        return True, ""

    def estimate_cost(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)
        return {"credits": max_pages, "cost_usd": 0, "max_results": max_pages * per_page}

    async def gather(self, filters: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        if not self._apollo:
            raise ValueError("Apollo service not configured")

        keyword_tags = filters.get("q_organization_keyword_tags", [])
        locations = filters.get("organization_locations")
        num_employees = filters.get("organization_num_employees_ranges")
        funding_stages = filters.get("organization_latest_funding_stage_cd")
        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)

        orgs = await self._apollo.search_organizations_all_pages(
            keyword_tags=keyword_tags,
            locations=locations,
            num_employees_ranges=num_employees,
            latest_funding_stages=funding_stages,
            max_pages=max_pages,
            per_page=per_page,
        )

        results = []
        for org in orgs:
            domain = org.get("primary_domain") or org.get("website_url", "")
            if not domain:
                continue
            results.append({
                "domain": domain,
                "name": org.get("name"),
                "industry": org.get("industry"),
                "employee_count": org.get("estimated_num_employees"),
                "country": org.get("country"),
                "city": org.get("city"),
                "description": org.get("short_description"),
                "linkedin_url": org.get("linkedin_url"),
                "source_data": org,
            })

        return results
