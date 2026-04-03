"""
CSV Import adapter — import companies from a CSV file or URL.
"""
import csv
import io
import logging
from typing import Optional, Callable, List, Dict
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)


class CSVImportFilters(BaseModel):
    """Filters for CSV import."""
    file_url: Optional[str] = None
    file_content: Optional[str] = None
    column_mapping: Dict[str, str] = Field(
        default_factory=lambda: {"domain": "domain", "name": "name"},
        description="Map CSV columns to standard fields: domain, name, linkedin_url, employees, industry, etc.",
    )
    skip_header: bool = True

    class Config:
        extra = "allow"


class CSVImportAdapter(GatheringAdapter):
    source_type = "csv.companies.manual"
    source_label = "CSV Import"
    filter_model = CSVImportFilters

    async def validate(self, raw_filters: dict) -> dict:
        validated = CSVImportFilters(**raw_filters)
        if not validated.file_url and not validated.file_content:
            raise ValueError("Either file_url or file_content is required")
        return validated.model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        validated = CSVImportFilters(**filters)
        if validated.file_content:
            lines = validated.file_content.strip().split("\n")
            count = len(lines) - (1 if validated.skip_header else 0)
        else:
            count = 0
        return EstimateResult(
            estimated_companies=max(count, 0),
            notes="CSV import is free. Exact count depends on file content.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = CSVImportFilters(**filters)
        content = validated.file_content

        if validated.file_url and not content:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(validated.file_url)
                resp.raise_for_status()
                content = resp.text

        if not content:
            return GatheringResult(error_message="No CSV content available")

        mapping = validated.column_mapping
        reader = csv.DictReader(io.StringIO(content))
        companies = []

        for i, row in enumerate(reader):
            company = {}
            for target_field, csv_column in mapping.items():
                if csv_column in row:
                    company[target_field] = row[csv_column].strip()
            if company.get("domain"):
                companies.append(company)
            if on_progress and i % 100 == 0:
                on_progress({"rows_processed": i, "companies_so_far": len(companies)})

        logger.info(f"CSV import: {len(companies)} companies from {i + 1} rows")
        return GatheringResult(
            companies=companies,
            raw_results_count=len(companies),
        )


from . import register_adapter  # noqa: E402
register_adapter(CSVImportAdapter)
