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
    country_names_exclude: List[str] = Field(default_factory=list)
    annual_revenues: List[str] = Field(default_factory=list)
    description_keywords: List[str] = Field(default_factory=list)
    description_keywords_exclude: List[str] = Field(default_factory=list)
    minimum_member_count: Optional[int] = None
    maximum_member_count: Optional[int] = None
    icp_text: Optional[str] = None
    max_results: int = Field(default=5000, ge=1, le=50000)

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
            # If icp_text provided, Clay service maps it to filters internally
            if validated.icp_text:
                result = await clay_service.run_tam_export(
                    icp_text=validated.icp_text,
                    max_results=validated.max_results,
                    on_progress=on_progress,
                )
            else:
                # Build ICP text from structured filters for the Clay mapper
                icp_parts = []
                if validated.industries:
                    icp_parts.append(f"Industries: {', '.join(validated.industries)}")
                if validated.country_names:
                    icp_parts.append(f"Countries: {', '.join(validated.country_names)}")
                if validated.sizes:
                    icp_parts.append(f"Company sizes: {', '.join(validated.sizes)}")
                if validated.description_keywords:
                    icp_parts.append(f"Keywords: {', '.join(validated.description_keywords)}")
                if validated.minimum_member_count:
                    icp_parts.append(f"Min employees: {validated.minimum_member_count}")
                if validated.maximum_member_count:
                    icp_parts.append(f"Max employees: {validated.maximum_member_count}")

                icp_text = ". ".join(icp_parts) if icp_parts else "General companies"
                result = await clay_service.run_tam_export(
                    icp_text=icp_text,
                    max_results=validated.max_results,
                    on_progress=on_progress,
                )

            clay_companies = result.get("companies", [])
            companies = []
            for item in clay_companies:
                domain = item.get("domain", "") or item.get("website", "")
                if domain:
                    if "://" in domain:
                        from urllib.parse import urlparse
                        domain = urlparse(domain).netloc or domain
                    domain = domain.lower().replace("www.", "")

                companies.append({
                    "domain": domain,
                    "name": item.get("name", "") or item.get("company_name", ""),
                    "employees": item.get("employees") or item.get("employee_count"),
                    "industry": item.get("industry", ""),
                    "city": item.get("city", ""),
                    "country": item.get("country", ""),
                    "linkedin_url": item.get("linkedin_url", ""),
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
