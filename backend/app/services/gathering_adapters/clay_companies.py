"""
Clay Companies adapter — wraps clay_service.run_tam_export().
Handles 5K limit by internal geo splitting (transparent to pipeline).
"""
import logging
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class ClayCompaniesFilters(BaseModel):
    """Filters for Clay Companies search."""
    industries: List[str] = Field(default_factory=list)
    industries_exclude: List[str] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list, description="e.g. ['1-10', '11-50']")
    types: List[str] = Field(default_factory=list)
    country_names: List[str] = Field(default_factory=list)
    states: List[str] = Field(default_factory=list, description="States/regions within a country, e.g. ['Arkansas', 'Texas']")
    country_names_exclude: List[str] = Field(default_factory=list)
    annual_revenues: List[str] = Field(default_factory=list)
    description_keywords: List[str] = Field(default_factory=list)
    description_keywords_exclude: List[str] = Field(default_factory=list)
    minimum_member_count: Optional[int] = None
    maximum_member_count: Optional[int] = None
    icp_text: Optional[str] = None
    max_results: int = Field(default=5000, ge=1, le=50000)
    save_search_name: Optional[str] = Field(default=None, description="Save search in Clay with this name after export")
    save_filter_types: Optional[List[str]] = Field(default=None, description="Which filter types to include in saved search (e.g. ['industries'])")

    class Config:
        extra = "allow"


class ClayCompaniesAdapter(GatheringAdapter):
    source_type = "clay.companies.emulator"
    source_label = "Clay Companies Search (Puppeteer)"
    filter_model = ClayCompaniesFilters

    async def validate(self, raw_filters: dict) -> dict:
        validated = ClayCompaniesFilters(**raw_filters)
        if not validated.icp_text and not validated.industries and not validated.description_keywords:
            raise ValueError("Provide icp_text, industries, or description_keywords")
        return validated.model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ClayCompaniesFilters(**filters)
        return EstimateResult(
            estimated_companies=validated.max_results,
            estimated_credits=validated.max_results,  # 1 credit per company
            estimated_cost_usd=validated.max_results * 0.01,  # ~$0.01/company
            notes=f"Clay TAM export, max {validated.max_results} companies. 5K limit per geo split.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        from app.services.clay_service import clay_service

        validated = ClayCompaniesFilters(**filters)

        try:
            if validated.icp_text:
                # Free-text ICP: let Clay service map via GPT
                result = await clay_service.run_tam_export(
                    icp_text=validated.icp_text,
                    max_results=validated.max_results,
                    on_progress=on_progress,
                    save_search_name=validated.save_search_name,
                    save_filter_types=validated.save_filter_types,
                )
            else:
                # Structured filters: pass directly to Puppeteer, skip GPT round-trip
                direct_filters = {}
                if validated.industries:
                    direct_filters["industries"] = validated.industries
                if validated.industries_exclude:
                    direct_filters["industries_exclude"] = validated.industries_exclude
                if validated.sizes:
                    direct_filters["sizes"] = validated.sizes
                if validated.types:
                    direct_filters["types"] = validated.types
                if validated.country_names:
                    direct_filters["country_names"] = validated.country_names
                if validated.states:
                    direct_filters["states"] = validated.states
                if validated.country_names_exclude:
                    direct_filters["country_names_exclude"] = validated.country_names_exclude
                if validated.annual_revenues:
                    direct_filters["annual_revenues"] = validated.annual_revenues
                if validated.description_keywords:
                    direct_filters["description_keywords"] = validated.description_keywords
                if validated.description_keywords_exclude:
                    direct_filters["description_keywords_exclude"] = validated.description_keywords_exclude
                if validated.minimum_member_count:
                    direct_filters["minimum_member_count"] = validated.minimum_member_count
                if validated.maximum_member_count:
                    direct_filters["maximum_member_count"] = validated.maximum_member_count

                # Build a descriptive ICP text for logging (Puppeteer still needs it as CLI arg)
                icp_parts = []
                if validated.industries:
                    icp_parts.append(f"Industries: {', '.join(validated.industries)}")
                if validated.country_names:
                    icp_parts.append(f"Countries: {', '.join(validated.country_names)}")
                if validated.states:
                    icp_parts.append(f"States: {', '.join(validated.states)}")
                if validated.sizes:
                    icp_parts.append(f"Sizes: {', '.join(validated.sizes)}")
                icp_text = ". ".join(icp_parts) if icp_parts else "General companies"

                result = await clay_service.run_tam_export(
                    icp_text=icp_text,
                    max_results=validated.max_results,
                    on_progress=on_progress,
                    filters_override=direct_filters,
                    save_search_name=validated.save_search_name,
                    save_filter_types=validated.save_filter_types,
                )

            clay_companies = result.get("companies", [])
            companies = []
            for item in clay_companies:
                # Clay exports use Title Case keys (Domain, Name, etc.)
                # Build a case-insensitive lookup
                ci = {k.lower(): v for k, v in item.items()}
                domain = ci.get("domain", "") or ci.get("website", "")
                if domain:
                    if "://" in domain:
                        from urllib.parse import urlparse
                        domain = urlparse(domain).netloc or domain
                    domain = domain.lower().replace("www.", "")

                companies.append({
                    "domain": domain,
                    "name": ci.get("name", "") or ci.get("company_name", ""),
                    "employees": ci.get("employees") or ci.get("employee_count") or ci.get("size", ""),
                    "industry": ci.get("industry", ""),
                    "city": ci.get("city", ""),
                    "country": ci.get("country", ""),
                    "linkedin_url": ci.get("linkedin_url") or ci.get("linkedin url", ""),
                    "raw_clay": item,
                })

            credits = result.get("credits_spent", len(companies))
            logger.info(f"Clay companies: {len(companies)} companies, {credits} credits")
            return GatheringResult(
                companies=companies,
                raw_results_count=len(companies),
                credits_used=credits,
                cost_usd=credits * 0.01,
                metadata={
                    "table_url": result.get("table_url"),
                    "table_id": result.get("table_id"),
                    "filters_used": result.get("filters"),
                },
            )

        except Exception as e:
            logger.error(f"Clay companies failed: {e}")
            return GatheringResult(error_message=str(e))


from . import register_adapter  # noqa: E402
register_adapter(ClayCompaniesAdapter)
