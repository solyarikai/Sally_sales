"""
Clay Service — TAM export pipeline + webhook push integration.

Pipeline: ICP text → GPT maps to Clay filters → Puppeteer searches Clay →
Creates table → Reads data via API → Exports to Google Sheets.
No credits spent (exports companies without emails).

Strategy for >5000 results: splits by country/geo, runs multiple searches,
merges and deduplicates results.
"""
import asyncio
import csv
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
CLAY_PEOPLE_SCRIPT = CLAY_SCRIPT_DIR / "clay_people_search.js"
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
    """Map ICP text to Clay search filters using Gemini 2.5 Pro (fallback: GPT-4o-mini)."""
    api_key = settings.OPENAI_API_KEY

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

CRITICAL: The first line of the ICP is the PRIMARY segment description. If "Project context (secondary)" is included, it's just background — the PRIMARY segment takes absolute priority. Map filters for the PRIMARY segment only.

Available filter fields:
{json.dumps(filter_schema, indent=2)}

Rules:
- Use description_keywords for THE MOST SPECIFIC niche terms that uniquely identify these companies. Generic terms alone are useless — use multi-word phrases.
- Be specific with industries (LinkedIn-style taxonomy). Use narrow industries, not broad ones.
- Use description_keywords_exclude to filter out wrong companies (competitors, agencies, unrelated).
- industries_exclude is critical — exclude industries that might match keywords but are wrong.
- Only include filters clearly specified or strongly implied by the ICP.
- If the ICP mentions geographic restrictions, include country_names.
- Output ONLY valid JSON, no explanation.

Example 1 — "payroll":
{{"industries":["Human Resources Services","IT Services and IT Consulting","Financial Services"],"industries_exclude":["Staffing and Recruiting","Insurance","Banking"],"description_keywords":["payroll software","payroll processing","salary payments","wage management","employee payroll","payroll solution","payroll platform"],"description_keywords_exclude":["recruitment","staffing agency","temp agency"],"sizes":["11-50","51-200","201-500","501-1000"]}}

Example 2 — "Companies selling gaming skins and virtual items":
{{"industries":["Computer Games","Internet Marketplace Platforms"],"industries_exclude":["Gambling Facilities and Casinos","Staffing and Recruiting"],"description_keywords":["skin trading","virtual items","loot box","case opening","game marketplace","CS2","CSGO"],"description_keywords_exclude":["casino","betting","slot","recruitment"],"sizes":["1-10","11-50","51-200","201-500"]}}"""

    # Use Gemini 2.5 Pro for better ICP understanding, fallback to GPT-4o-mini
    gemini_key = settings.GEMINI_API_KEY
    if gemini_key:
        model = settings.GEMINI_MODEL or "gemini-2.5-pro"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}",
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\nMap this ICP to Clay search filters:\n\n{icp_text}"}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

    # Fallback: GPT-4o-mini
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
        on_progress: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run full TAM export pipeline.

        1. Maps ICP to Clay filters via GPT
        2. Runs Puppeteer Clay automation
        3. Returns company data

        Returns dict with {filters, companies, credits_spent, table_id}.
        on_progress: optional async callback(message: str) for live status updates.
        """
        async def _emit(msg: str):
            if on_progress:
                try:
                    await on_progress(msg)
                except Exception:
                    pass

        # Step 1: Map ICP to filters
        await _emit("AI mapping ICP description to search filters...")
        logger.info(f"Clay TAM: mapping ICP to filters...")
        filters = await map_icp_to_clay_filters(icp_text)
        logger.info(f"Clay TAM: filters = {json.dumps(filters)}")
        await _emit("Filters mapped. Starting search engine...")

        # Step 2: Run Node.js Puppeteer script
        if not CLAY_TAM_SCRIPT.exists():
            raise FileNotFoundError(f"Clay TAM script not found: {CLAY_TAM_SCRIPT}")

        # Write filters to temp file for the script
        CLAY_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filters_file = CLAY_EXPORTS_DIR / "filters_input.json"
        filters_file.write_text(json.dumps(filters, indent=2))

        # Remove stale output files so we don't accidentally read old data
        for stale in ("tam_companies.json", "tam_results.json", "tam_table_meta.json"):
            stale_path = CLAY_EXPORTS_DIR / stale
            if stale_path.exists():
                stale_path.unlink()

        args = ["node", str(CLAY_TAM_SCRIPT), "--headless", "--auto"]
        if test_mode:
            args.append("--test")
        else:
            args.append(icp_text)

        env = {
            **os.environ,
            "OPENAI_API_KEY": settings.OPENAI_API_KEY or "",
            "PUPPETEER_SKIP_CHROMIUM_DOWNLOAD": "true",
            "PUPPETEER_EXECUTABLE_PATH": os.environ.get("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium"),
            "CHROME_PATH": os.environ.get("CHROME_PATH", "/usr/bin/chromium"),
        }
        logger.info(f"Clay TAM: running Puppeteer script...")

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(CLAY_SCRIPT_DIR),
            env=env,
        )

        # Drain stderr concurrently to prevent pipe deadlock
        stderr_chunks_tam: list[bytes] = []

        async def _drain_stderr_tam():
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks_tam.append(chunk)

        stderr_task_tam = asyncio.create_task(_drain_stderr_tam())

        # Stream stdout line-by-line for live progress
        log_lines: list[str] = []
        _STEP_MAP = {
            "[3] Validating": "Connecting to search engine...",
            "Session valid": "Connected. Checking quota...",
            "[4] Opening Find": "Opening company search...",
            "[5] Applying filters": "Applying search filters...",
            "Location:": None,  # skip, too noisy
            "[6] Opening Continue": "Saving results...",
            "Found:": None,  # dropdown option found
            "[7] Handling enrichment": "Extracting company data...",
            "Table ID:": "Results ready. Fetching data...",
            "Reading table": "Reading company records...",
            "Record IDs:": None,  # sub-detail
            "Batch ": None,  # sub-detail
            "CREDITS SPENT": None,  # handled separately
        }
        try:
            assert proc.stdout is not None
            while True:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=600)
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                log_lines.append(line)
                for prefix, msg in _STEP_MAP.items():
                    if prefix in line and msg:
                        await _emit(msg)
                        break
        except asyncio.TimeoutError:
            proc.kill()

        await stderr_task_tam
        stderr_data = b"".join(stderr_chunks_tam)
        await proc.wait()

        log_output = "\n".join(log_lines)
        logger.info(f"Clay TAM script output:\n{log_output[-2000:]}")

        if proc.returncode != 0:
            stderr_text = stderr_data.decode('utf-8', errors='replace')[-500:]
            logger.error(f"Clay TAM script failed (rc={proc.returncode}): {stderr_text}")

        # Step 3: Read results
        companies_file = CLAY_EXPORTS_DIR / "tam_companies.json"
        results_file = CLAY_EXPORTS_DIR / "tam_results.json"

        companies = []
        if companies_file.exists():
            companies = json.loads(companies_file.read_text())
        else:
            logger.error("Clay TAM: tam_companies.json not found — Puppeteer failed to read table records")

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

    async def run_people_search(
        self,
        domains: List[str],
        project_id: Optional[int] = None,
        on_progress: Optional[Any] = None,
        use_titles: bool = False,
        countries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run Clay People search via Puppeteer.

        Writes domains to a temp CSV, runs clay_people_search.js --domains-file,
        reads output JSON/CSV. Returns dict with:
          - "people": list of normalized person dicts
          - "table_url": Clay table URL if available, else None
        on_progress: optional async callback(message: str) for live status updates.
        use_titles: if True, pass --titles flag to filter for decision-makers only.
        countries: if provided, write to filters_input.json for location filtering.
        """
        async def _emit(msg: str):
            if on_progress:
                try:
                    await on_progress(msg)
                except Exception:
                    pass

        if not CLAY_PEOPLE_SCRIPT.exists():
            raise FileNotFoundError(f"Clay People script not found: {CLAY_PEOPLE_SCRIPT}")

        CLAY_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # Clean stale output files to prevent data contamination between runs
        for stale in CLAY_EXPORTS_DIR.glob("people_*.json"):
            try:
                stale.unlink()
                logger.info(f"Clay People: cleaned stale file {stale.name}")
            except Exception:
                pass

        # Write domains to temp CSV for the script
        domains_file = CLAY_EXPORTS_DIR / f"domains_input_{project_id or 'tmp'}.csv"
        domains_file.write_text("\n".join(domains))
        logger.info(f"Clay People: wrote {len(domains)} domains to {domains_file}")
        await _emit(f"Starting contact search engine ({len(domains)} companies)...")

        # Run Puppeteer script
        args = [
            "node", str(CLAY_PEOPLE_SCRIPT),
            "--headless", "--auto",
            "--domains-file", str(domains_file),
        ]
        if use_titles:
            args.append("--titles")

        if countries:
            args.extend(["--countries", ",".join(countries)])
            logger.info(f"Clay People: country filter = {countries}")

        env = {
            **os.environ,
            "PUPPETEER_SKIP_CHROMIUM_DOWNLOAD": "true",
            "PUPPETEER_EXECUTABLE_PATH": os.environ.get("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium"),
            "CHROME_PATH": os.environ.get("CHROME_PATH", "/usr/bin/chromium"),
        }
        logger.info("Clay People: running Puppeteer script...")

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(CLAY_SCRIPT_DIR),
            env=env,
        )

        # Drain stderr concurrently to prevent pipe deadlock.
        # If stderr buffer fills up while we read stdout line-by-line,
        # the subprocess blocks on stderr write → deadlock.
        stderr_chunks: list[bytes] = []

        async def _drain_stderr():
            assert proc.stderr is not None
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        stderr_task = asyncio.create_task(_drain_stderr())

        # Stream stdout line-by-line for live progress
        log_lines: list[str] = []
        _STEP_MAP = {
            "Session valid": "Connected.",
            "Selected People tab": "Searching contacts...",
            "Applying filters": "Applying filters...",
            "Typing": None,  # domain typing progress
            "Job titles:": "Setting role filters...",
            "company domains": None,  # will handle typed X/Y below
            "Continue dropdown": "Saving results...",
            "Create table": "Extracting contact data...",
            "Table ID:": "Results ready.",
            "Waiting for table": "Waiting for data to load...",
            "CSV export": None,  # sub-detail
            "reading via browser": "Reading contact records...",
            "Record IDs:": None,
            "Saved": None,  # handled by result count
        }
        typed_last_emitted = 0
        try:
            assert proc.stdout is not None
            while True:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=900)
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                log_lines.append(line)
                # Emit domain typing progress every 100
                if "Typed " in line and "/" in line:
                    try:
                        parts = line.split("Typed ")[1].split("/")
                        typed_n = int(parts[0])
                        if typed_n - typed_last_emitted >= 100:
                            total_n = parts[1].split()[0]
                            await _emit(f"Typing company domains... {typed_n}/{total_n}")
                            typed_last_emitted = typed_n
                    except (IndexError, ValueError):
                        pass
                    continue
                for prefix, msg in _STEP_MAP.items():
                    if prefix in line and msg:
                        await _emit(msg)
                        break
        except asyncio.TimeoutError:
            proc.kill()

        await stderr_task
        stderr_data = b"".join(stderr_chunks)
        await proc.wait()

        log_output = "\n".join(log_lines)
        logger.info(f"Clay People script output:\n{log_output[-3000:]}")

        if proc.returncode != 0:
            err_output = stderr_data.decode("utf-8", errors="replace")[-500:]
            logger.error(f"Clay People script failed (exit {proc.returncode}): {err_output}")

        # Read results — script saves to people_*.json or downloads CSV
        people = []

        # Check for JSON outputs first (fallback API read)
        results_file = CLAY_EXPORTS_DIR / "people_search_results.json"
        if results_file.exists():
            meta = json.loads(results_file.read_text())
            for search in meta.get("searches", []):
                json_path = search.get("jsonPath")
                if json_path and os.path.exists(json_path):
                    batch = json.loads(Path(json_path).read_text())
                    people.extend(batch)

        # Check for JSON batch files (people_batch_1.json, people_all.json, etc.)
        if not people:
            for f in sorted(CLAY_EXPORTS_DIR.glob("people_*.json")):
                if f.name == "people_search_results.json":
                    continue
                try:
                    batch = json.loads(f.read_text())
                    if isinstance(batch, list):
                        people.extend(batch)
                except Exception as e:
                    logger.warning(f"Failed to read {f}: {e}")

        # Check downloads dir for CSV
        downloads_dir = CLAY_EXPORTS_DIR / "downloads"
        if not people and downloads_dir.exists():
            for csv_file in sorted(downloads_dir.glob("*.csv")):
                try:
                    with open(csv_file, "r", encoding="utf-8") as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            people.append(dict(row))
                except Exception as e:
                    logger.warning(f"Failed to read CSV {csv_file}: {e}")

        # Normalize field names to our standard
        normalized = []
        for p in people:
            person = {
                "name": p.get("Full Name") or p.get("Name") or p.get("name") or "",
                "first_name": p.get("First Name") or p.get("first_name") or "",
                "last_name": p.get("Last Name") or p.get("last_name") or "",
                "email": p.get("Email") or p.get("email") or p.get("Work Email") or None,
                "title": p.get("Job Title") or p.get("Title") or p.get("title") or "",
                "company": p.get("Company Name") or p.get("Company") or p.get("company") or p.get("Organization") or "",
                "company_domain": (
                    p.get("Company Domain") or p.get("company_domain") or p.get("Domain") or p.get("domain") or ""
                ).strip().lower().replace("www.", ""),
                "location": p.get("Location") or p.get("location") or p.get("City") or "",
                "linkedin_url": p.get("LinkedIn Profile") or p.get("LinkedIn URL") or p.get("linkedin_url") or p.get("LinkedIn") or None,
                "phone": p.get("Phone") or p.get("phone") or None,
            }
            # Also copy domain to "domain" key for the handler
            person["domain"] = person["company_domain"]
            if person["name"]:  # Skip empty records
                normalized.append(person)

        # Diagnostic: log domain coverage
        _domains_found = set()
        _domains_empty = 0
        for p in normalized:
            d = p.get("company_domain", "")
            if d:
                _domains_found.add(d)
            else:
                _domains_empty += 1
        _searched = set(d.strip().lower().replace("www.", "") for d in domains if d.strip())
        _matched = _domains_found & _searched
        _unmatched = _domains_found - _searched
        logger.info(
            f"Clay People: {len(people)} raw → {len(normalized)} normalized, "
            f"{len(_domains_found)} unique domains found (of {len(_searched)} searched), "
            f"{len(_matched)} matched, {len(_unmatched)} unmatched, {_domains_empty} empty-domain"
        )
        if _unmatched:
            logger.info(f"Clay People: unmatched domains sample: {list(_unmatched)[:10]}")

        # Extract table URL from results metadata if available
        table_url = None
        if results_file.exists():
            try:
                meta = json.loads(results_file.read_text())
                for search in meta.get("searches", []):
                    table_id = search.get("tableId")
                    if table_id:
                        table_url = f"https://app.clay.com/workspaces/889252/tables/{table_id}"
                        break
            except Exception:
                pass

        return {
            "people": normalized,
            "table_url": table_url,
        }

    async def export_people_to_sheets(
        self,
        people: List[Dict[str, Any]],
        sheet_title: str = "Clay Contacts Export",
        project_id: Optional[int] = None,
    ) -> str:
        """Export contacts to Google Sheet. Returns sheet URL."""
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
                "properties": {"sheetId": 0, "title": "Contacts"}, "fields": "title",
            }}]},
        ).execute()

        # Write contact data
        columns = [
            "Name", "Email", "Title", "Company", "Domain",
            "Location", "LinkedIn URL", "Phone",
            "Role Priority", "Decision Maker",
        ]
        field_map = {
            "Name": "name", "Email": "email", "Title": "title",
            "Company": "company", "Domain": "company_domain",
            "Location": "location", "LinkedIn URL": "linkedin_url",
            "Phone": "phone", "Role Priority": "_role_priority",
            "Decision Maker": "_is_decision_maker",
        }

        rows = [columns]
        for person in people:
            row = []
            for col in columns:
                val = person.get(field_map[col], "")
                if val is None:
                    val = ""
                elif isinstance(val, bool):
                    val = "Yes" if val else "No"
                row.append(str(val)[:500])
            rows.append(row)

        # Write in batches of 5000 rows
        for i in range(0, len(rows), 5000):
            batch = rows[i:i + 5000]
            start_row = i + 1 if i > 0 else 1
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Contacts!A{start_row}",
                valueInputOption="RAW",
                body={"values": batch},
            ).execute()

        logger.info(f"Clay People: exported {len(people)} contacts to {sheet_url}")
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
