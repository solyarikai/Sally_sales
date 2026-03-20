"""
Manual adapter — direct domain list input.
"""
import logging
from typing import Optional, Callable, List
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class ManualFilters(BaseModel):
    """Filters for manual domain list input."""
    domains: List[str] = Field(..., min_length=1, description="List of domains to add")
    source_description: str = Field(default="Manual input", description="Where these domains came from")

    class Config:
        extra = "allow"


class ManualAdapter(GatheringAdapter):
    source_type = "manual.companies.manual"
    source_label = "Manual Domain List"
    filter_model = ManualFilters

    async def validate(self, raw_filters: dict) -> dict:
        return ManualFilters(**raw_filters).model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = ManualFilters(**filters)
        return EstimateResult(
            estimated_companies=len(validated.domains),
            notes=f"{len(validated.domains)} domains to import. Free.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = ManualFilters(**filters)
        companies = []

        for domain in validated.domains:
            domain = domain.strip().lower()
            if domain:
                companies.append({"domain": domain, "name": "", "source_description": validated.source_description})

        logger.info(f"Manual import: {len(companies)} domains")
        return GatheringResult(
            companies=companies,
            raw_results_count=len(companies),
        )


from . import register_adapter  # noqa: E402
register_adapter(ManualAdapter)
