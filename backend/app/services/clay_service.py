"""
Clay Service — TAM export pipeline + webhook push integration.

Pipeline: ICP text → GPT maps to Clay filters → Puppeteer searches Clay →
Creates table → Reads data via API → Exports to Google Sheets.
No credits spent (exports companies without emails).

Strategy for >5000 results: splits by country/geo, runs multiple searches,
merges and deduplicates results.
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Path to the Node.js Clay automation script
CLAY_SCRIPT_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "clay"
CLAY_TAM_SCRIPT = CLAY_SCRIPT_DIR / "clay_tam_export.js"
CLAY_EXPORTS_DIR = CLAY_SCRIPT_DIR / "exports"

# Clay export limit per search
CLAY_EXPORT_LIMIT = 5000

# Geo split strategy for large TAMs — split into regional batches
GEO_SPLITS = [
    {"label": "North America", "countries": ["United States", "Canada", "Mexico"]},
    {"label": "Europe West", "countries": ["United Kingdom", "Germany", "France", "Netherlands", "Spain", "Italy", "Switzerland", "Belgium", "Austria", "Sweden", "Denmark", "Norway", "Finland", "Ireland", "Portugal"]},
    {"label": "Europe East", "countries": ["Poland", "Czech Republic", "Romania", "Hungary", "Bulgaria", "Croatia", "Slovakia", "Serbia", "Ukraine", "Lithuania", "Latvia", "Estonia"]},
    {"label": "Asia Pacific", "countries": ["Japan", "South Korea", "Australia", "New Zealand", "Singapore", "India", "China", "Hong Kong", "Taiwan", "Thailand", "Indonesia", "Malaysia", "Philippines", "Vietnam"]},
    {"label": "LATAM", "countries": ["Brazil", "Argentina", "Colombia", "Chile", "Peru"]},
    {"label": "Middle East & Africa", "countries": ["United Arab Emirates", "Israel", "Saudi Arabia", "Turkey", "South Africa", "Nigeria", "Egypt"]},
    {"label": "Rest of World", "countries": []},  # No country filter = catch remaining
]


async def map_icp_to_clay_filters(icp_text: str) -> Dict[str, Any]:
    """Map ICP text to Clay search filters using GPT-4o-mini."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    filter_schema = {
        "industries": "Clay industry tags, e.g. ['Online gaming', 'E-commerce']",
        "industries_exclude": "Industries to exclude",
        "sizes": "Company size ranges, e.g. ['1-10', '11-50', '51-200']",
        "types": "Company types, e.g. ['Privately held']",
        "country_names": "Countries to include",
        "country_names_exclude": "Countries to exclude",
        "annual_revenues": "Revenue ranges",
        "description_keywords": "Keywords in company description",
        "description_keywords_exclude": "Keywords to exclude",
        "minimum_member_count": "Min employees (number)",
        "maximum_member_count": "Max employees (number)",
    }

    system_prompt = f"""You are a Clay.com search filter expert. Given an ICP description, output a JSON object with Clay search filters.

Available filter fields:
{json.dumps(filter_schema, indent=2)}

Rules:
- Use description_keywords for niche-specific terms
- Be specific with industries (LinkedIn-style taxonomy)
- Only include filters clearly specified or strongly implied by the ICP
- Output ONLY valid JSON, no explanation

Example for "SaaS companies in US, 50-200 employees":
{{"industries":["Software development","SaaS"],"sizes":["51-200"],"country_names":["United States"],"description_keywords":["software","SaaS","platform"]}}"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Map this ICP to Clay search filters:\n\n{icp_text}"},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data["choices"][0]["message"]["content"])


def estimate_geo_splits(filters: Dict[str, Any], estimated_total: int) -> List[Dict[str, Any]]:
    """Determine if we need to split by geo and return split configs.

    If estimated_total > CLAY_EXPORT_LIMIT, split by geographic regions.
    Each split gets the same base filters + a country filter.
    """
    if estimated_total <= CLAY_EXPORT_LIMIT:
        return [{"label": "All", "filters": filters}]

    splits = []
    base_filters = {k: v for k, v in filters.items() if k != "country_names"}

    for geo in GEO_SPLITS:
        split_filters = {**base_filters}
        if geo["countries"]:
            split_filters["country_names"] = geo["countries"]
        splits.append({"label": geo["label"], "filters": split_filters})

    return splits


class ClayService:
    """Clay TAM export and webhook push service."""

    def __init__(self):
        self.api_key = settings.CLAY_API_KEY
        self.domains_pushed: int = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def run_tam_export(
        self,
        icp_text: str,
        project_id: Optional[int] = None,
        max_results: int = 5000,
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Run full TAM export pipeline.

        1. Maps ICP to Clay filters via GPT
        2. Runs Puppeteer Clay automation
        3. Returns company data

        Returns dict with {filters, companies, credits_spent, table_id}.
        """
        # Step 1: Map ICP to filters
        logger.info(f"Clay TAM: mapping ICP to filters...")
        filters = await map_icp_to_clay_filters(icp_text)
        logger.info(f"Clay TAM: filters = {json.dumps(filters)}")

        # Step 2: Run Node.js Puppeteer script
        if not CLAY_TAM_SCRIPT.exists():
            raise FileNotFoundError(f"Clay TAM script not found: {CLAY_TAM_SCRIPT}")

        # Write filters to temp file for the script
        CLAY_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filters_file = CLAY_EXPORTS_DIR / "filters_input.json"
        filters_file.write_text(json.dumps(filters, indent=2))

        args = ["node", str(CLAY_TAM_SCRIPT)]
        if test_mode:
            args.append("--test")
        else:
            args.append(icp_text)

        env = {**os.environ, "OPENAI_API_KEY": settings.OPENAI_API_KEY or ""}
        logger.info(f"Clay TAM: running Puppeteer script...")

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(CLAY_SCRIPT_DIR),
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        log_output = stdout.decode("utf-8", errors="replace")
        logger.info(f"Clay TAM script output:\n{log_output[-2000:]}")

        if proc.returncode != 0:
            logger.error(f"Clay TAM script failed: {stderr.decode('utf-8', errors='replace')[-500:]}")

        # Step 3: Read results
        companies_file = CLAY_EXPORTS_DIR / "tam_companies.json"
        results_file = CLAY_EXPORTS_DIR / "tam_results.json"

        companies = []
        if companies_file.exists():
            companies = json.loads(companies_file.read_text())

        result_meta = {}
        if results_file.exists():
            result_meta = json.loads(results_file.read_text())

        credits_before = result_meta.get("creditsBefore", {}).get("basic", 0)
        credits_after = result_meta.get("creditsAfter", {}).get("basic", 0)
        credits_spent = credits_before - credits_after

        return {
            "filters": filters,
            "companies": companies,
            "total": len(companies),
            "credits_spent": credits_spent,
            "table_id": result_meta.get("tableId"),
            "table_url": result_meta.get("tableUrl"),
        }

    async def export_to_google_sheets(
        self,
        companies: List[Dict[str, Any]],
        sheet_title: str = "Clay TAM Export",
        project_id: Optional[int] = None,
        debug_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create Google Sheet on Shared Drive with company data + debug tab. Returns sheet URL."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds_file = "/app/google-credentials.json"
        if not os.path.exists(creds_file):
            creds_file = str(Path(__file__).parent.parent.parent.parent / "google-credentials.json")
            if not os.path.exists(creds_file):
                raise FileNotFoundError("Google credentials not found")

        shared_drive_id = os.environ.get("SHARED_DRIVE_ID", "0AEvTjlJFlWnZUk9PVA")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        drive_service = build("drive", "v3", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)

        # Create sheet on Shared Drive
        file_metadata = {
            "name": sheet_title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [shared_drive_id],
        }
        sheet_file = drive_service.files().create(
            body=file_metadata, fields="id", supportsAllDrives=True,
        ).execute()
        spreadsheet_id = sheet_file["id"]
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        # Make publicly readable
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()

        # Rename Sheet1
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"updateSheetProperties": {
                "properties": {"sheetId": 0, "title": "Companies"}, "fields": "title",
            }}]},
        ).execute()

        # Write company data
        columns = ["Name", "Domain", "Description", "Primary Industry", "Size", "Type", "Location", "Country", "LinkedIn URL"]
        available_cols = [c for c in columns if any(c in co for co in companies[:10])] if companies else columns
        if companies and not available_cols:
            available_cols = list(companies[0].keys())

        rows = [available_cols]
        for company in companies:
            rows.append([str(company.get(col, ""))[:500] for col in available_cols])

        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range="Companies!A1",
            valueInputOption="RAW", body={"values": rows},
        ).execute()

        # Debug tab
        if debug_meta:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": "Debug Info"}}}]},
            ).execute()

            debug_rows = [["Parameter", "Value"]]
            for k, v in debug_meta.items():
                debug_rows.append([str(k), json.dumps(v) if isinstance(v, (list, dict)) else str(v)])

            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range="Debug Info!A1",
                valueInputOption="RAW", body={"values": debug_rows},
            ).execute()

        logger.info(f"Clay TAM: exported {len(companies)} companies to {sheet_url}")
        return sheet_url

    async def push_domains_to_table(
        self,
        webhook_url: str,
        domains: List[str],
        extra_data: Optional[Dict[str, Any]] = None,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """Push domains to a Clay table via webhook URL."""
        stats = {"pushed": 0, "errors": 0, "total": len(domains)}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            rows = []
            for domain in batch:
                row = {"domain": domain, "url": f"https://{domain}"}
                if extra_data:
                    row.update(extra_data)
                rows.append(row)

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(webhook_url, json=rows, headers=headers)
                    resp.raise_for_status()
                    stats["pushed"] += len(batch)
                    self.domains_pushed += len(batch)
                    logger.info(f"Clay: pushed {len(batch)} domains (total: {stats['pushed']}/{stats['total']})")
            except Exception as e:
                logger.error(f"Clay webhook push failed for batch {i//batch_size}: {e}")
                stats["errors"] += len(batch)

        return stats


# Module-level singleton
clay_service = ClayService()
