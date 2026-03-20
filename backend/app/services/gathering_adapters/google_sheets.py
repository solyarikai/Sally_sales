"""
Google Sheets adapter — import companies from a Google Spreadsheet.

Uses the system's Google Service Account (same as Google Drive integration).
The service account already has access to shared folders. No "Anyone with link" needed
if the sheet is in the shared Google Drive folder.

Fallback: if service account can't access the sheet, tries public CSV export URL.
"""
import csv
import io
import logging
import re
from typing import Optional, Callable, List, Dict
from pydantic import BaseModel, Field

from .base import GatheringAdapter, EstimateResult, GatheringResult

logger = logging.getLogger(__name__)

SHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def extract_sheet_id(url_or_id: str) -> str:
    """Extract sheet ID from URL or return as-is if already an ID."""
    match = SHEET_ID_PATTERN.search(url_or_id)
    if match:
        return match.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{20,}$", url_or_id):
        return url_or_id
    raise ValueError(f"Cannot extract Google Sheet ID from: {url_or_id}")


class GoogleSheetsFilters(BaseModel):
    """Filters for Google Sheets import."""
    sheet_url: str = Field(..., description="Google Sheet URL or ID")
    tab_name: Optional[str] = Field(None, description="Tab/sheet name (e.g. 'Sheet1'). If not set, uses first tab.")
    gid: int = Field(default=0, description="Tab index (used only if tab_name not set)")
    column_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "domain": "domain",
            "name": "company",
        },
        description="Map sheet columns to standard fields. Keys: domain, name, linkedin_url, employees, industry, city, country, email, title",
    )
    skip_rows: int = Field(default=0, description="Skip N rows after header")
    source_description: str = Field(default="Google Sheets import")

    class Config:
        extra = "allow"


class GoogleSheetsAdapter(GatheringAdapter):
    source_type = "google_sheets.companies.manual"
    source_label = "Google Sheets Import"
    filter_model = GoogleSheetsFilters

    async def validate(self, raw_filters: dict) -> dict:
        validated = GoogleSheetsFilters(**raw_filters)
        extract_sheet_id(validated.sheet_url)
        return validated.model_dump()

    async def estimate(self, filters: dict) -> EstimateResult:
        return EstimateResult(
            estimated_companies=0,
            notes="Free import. Uses Google Service Account for access. Execute to see results.",
        )

    async def execute(self, filters: dict, on_progress: Optional[Callable] = None) -> GatheringResult:
        validated = GoogleSheetsFilters(**filters)
        sheet_id = extract_sheet_id(validated.sheet_url)

        # Try 1: Use Google Service Account (same as Google Drive integration)
        rows = await self._read_via_service_account(sheet_id, validated.tab_name)

        # Try 2: Fall back to public CSV export
        if rows is None:
            logger.info(f"Service account can't access sheet {sheet_id}, trying public CSV export")
            rows = await self._read_via_csv_export(sheet_id, validated.gid)

        if rows is None:
            return GatheringResult(
                error_message=(
                    f"Cannot access Google Sheet. Either:\n"
                    f"1. Share the sheet with the service account (check GET /api/contacts/sheet-config for the email), or\n"
                    f"2. Move it to the shared Google Drive folder, or\n"
                    f"3. Set sharing to 'Anyone with link can view'"
                )
            )

        if not rows:
            return GatheringResult(error_message="Sheet is empty")

        # First row = headers
        headers = rows[0]
        mapping = validated.column_mapping
        if mapping == {"domain": "domain", "name": "company"}:
            mapping = self._auto_detect_mapping(headers)
            logger.info(f"Auto-detected column mapping: {mapping}")

        # Build header index
        header_index = {h.strip().lower(): i for i, h in enumerate(headers)}

        companies = []
        rows_processed = 0

        for row in rows[1:]:  # skip header
            rows_processed += 1
            if rows_processed <= validated.skip_rows:
                continue

            company = {}
            for target_field, col_name in mapping.items():
                col_lower = col_name.strip().lower()
                if col_lower in header_index:
                    idx = header_index[col_lower]
                    if idx < len(row):
                        val = str(row[idx]).strip()
                        if val:
                            company[target_field] = val

            domain = company.get("domain", "")
            name = company.get("name", "")

            # Extract domain from email if no domain column
            if not domain and company.get("email"):
                email = company["email"]
                if "@" in email:
                    domain = email.split("@")[1].lower()
                    company["domain"] = domain

            # Extract domain from website field
            if not domain and company.get("website"):
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(company["website"] if "://" in company["website"] else f"https://{company['website']}")
                    domain = parsed.netloc.lower().replace("www.", "")
                    company["domain"] = domain
                except Exception:
                    pass

            if domain or name:
                company["_sheet_row"] = rows_processed + 1  # 1-indexed including header
                companies.append(company)

            if on_progress and rows_processed % 50 == 0:
                on_progress({"rows_processed": rows_processed, "companies_so_far": len(companies)})

        logger.info(f"Google Sheets: {len(companies)} companies from {rows_processed} rows (sheet={sheet_id})")
        return GatheringResult(
            companies=companies,
            raw_results_count=len(companies),
            metadata={
                "sheet_id": sheet_id,
                "tab": validated.tab_name or f"gid={validated.gid}",
                "total_rows": rows_processed,
                "mapping_used": mapping,
            },
        )

    async def _read_via_service_account(self, sheet_id: str, tab_name: Optional[str]) -> Optional[List[list]]:
        """Read sheet via Google Sheets API using the system service account."""
        try:
            from app.services.google_sheets_service import google_sheets_service

            if not google_sheets_service.is_configured():
                logger.warning("Google Sheets service not configured")
                return None

            range_name = f"'{tab_name}'" if tab_name else "Sheet1"
            result = google_sheets_service.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name,
            ).execute()

            rows = result.get("values", [])
            if rows:
                logger.info(f"Read {len(rows)} rows via service account from sheet {sheet_id}")
                return rows
            return []

        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                logger.warning(f"Sheet {sheet_id} not found via service account")
            elif "403" in error_str or "permission" in error_str.lower():
                logger.warning(f"Sheet {sheet_id} not shared with service account")
            else:
                logger.warning(f"Service account read failed for {sheet_id}: {e}")
            return None

    async def _read_via_csv_export(self, sheet_id: str, gid: int) -> Optional[List[list]]:
        """Fallback: read sheet via public CSV export URL."""
        try:
            import httpx
            export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(export_url)
                resp.raise_for_status()
                content = resp.text

            if not content.strip():
                return []

            reader = csv.reader(io.StringIO(content))
            return list(reader)

        except Exception as e:
            logger.warning(f"CSV export failed for sheet {sheet_id}: {e}")
            return None

    @staticmethod
    def _auto_detect_mapping(headers: List[str]) -> Dict[str, str]:
        """Auto-detect column mapping from header names."""
        mapping = {}
        lower_headers = {h.strip().lower(): h for h in headers if h.strip()}

        detect_rules = {
            "domain": ["domain", "website", "url", "site", "company domain", "company_domain", "web"],
            "name": ["name", "company", "company name", "company_name", "organization", "org"],
            "linkedin_url": ["linkedin", "linkedin_url", "linkedin url", "li_url", "company linkedin"],
            "employees": ["employees", "employee count", "employee_count", "size", "headcount", "# employees"],
            "industry": ["industry", "sector", "vertical"],
            "country": ["country", "location", "geo", "geography"],
            "city": ["city"],
            "email": ["email", "work email", "work_email", "contact email"],
            "website": ["website", "url", "web"],
        }

        for target_field, candidates in detect_rules.items():
            for candidate in candidates:
                if candidate in lower_headers:
                    mapping[target_field] = lower_headers[candidate]
                    break

        return mapping


from . import register_adapter  # noqa: E402
register_adapter(GoogleSheetsAdapter)
