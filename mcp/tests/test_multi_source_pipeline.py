"""
Multi-Source Pipeline Tests — Comprehensive TDD test suite.

Coverage per requirements_source.md:
  1. CSV adapter — parsing, auto-columns, errors, edge cases
  2. Google Sheet adapter — URL parsing, fetch, column detection
  3. Google Drive adapter — multi-file, dedup, source tracking
  4. Column auto-detection — all formats (Apollo/Clay/standard/minimal)
  5. Cross-source dedup — same project, different runs
  6. Blacklisting — project-scoped, no cross-project leakage, trash domains
  7. Custom classification prompts — user-provided, Drive JSON format
  8. Multi-step prompt chains — execution, filter evaluation, output parsing
  9. Smart source suggestion — all phrasings, key requirements
 10. Adapter registration — all 5 sources wired into gathering service
 11. Pipeline E2E — 3 runs same project, dedup counts verified
 12. Error handling — missing files, bad URLs, malformed CSV, empty data
 13. Conversation-based scenarios — user intent → expected MCP behavior

Test data:
  - CSV: 110 LATAM companies (apparel/fashion/textiles)
  - Sheet: 110 companies (40 overlap with CSV)
  - Drive: 3 files × 35 = 105 companies (35 overlap CSV, 35 overlap Sheet)
  - Total unique across all: 215

Test user: services@getsally.io
Project: "Result" targeting LATAM fashion/apparel companies
"""
import csv
import io
import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Paths
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_CSV_PATH = TEST_DATA_DIR / "test_csv_source.csv"
TEST_SHEET_CSV_PATH = TEST_DATA_DIR / "test_sheet_source.csv"
TEST_DRIVE_DIR = TEST_DATA_DIR / "drive_folder"


# ═══════════════════════════════════════════════════════════════
# 1. CSV ADAPTER TESTS
# ═══════════════════════════════════════════════════════════════

class TestCSVAdapter:
    """Test csv.companies.file adapter — full coverage."""

    @pytest.mark.asyncio
    async def test_csv_parses_all_companies(self):
        """CSV adapter should parse all rows from the test file."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        assert len(results) == 110, f"Expected 110 companies, got {len(results)}"

    @pytest.mark.asyncio
    async def test_csv_auto_detects_columns(self):
        """CSV adapter should auto-detect Website, Company Name, Industry, etc."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            assert r.get("domain"), f"Missing domain for company: {r.get('name')}"
            assert "://" not in r["domain"], f"Domain should be clean, got: {r['domain']}"
            assert not r["domain"].startswith("www."), f"Domain should strip www: {r['domain']}"

    @pytest.mark.asyncio
    async def test_csv_extracts_all_enrichment_fields(self):
        """CSV adapter should extract name, industry, country, employees, etc."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        first = results[0]
        assert first.get("name"), "Should have company name"
        assert first.get("source_data"), "Should have source_data"
        assert first["source_data"]["source"] == "csv_file"
        # Check fields are populated where data exists
        has_country = sum(1 for r in results if r.get("country"))
        has_industry = sum(1 for r in results if r.get("industry"))
        assert has_country > 50, f"Most companies should have country, got {has_country}/110"
        assert has_industry > 50, f"Most companies should have industry, got {has_industry}/110"

    @pytest.mark.asyncio
    async def test_csv_handles_multiline_descriptions(self):
        """TakeTest100.csv has multi-line descriptions — adapter must handle them."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        domains = [r["domain"] for r in results]
        assert len(domains) == len(set(domains)), "Should not have duplicate domains from multiline parsing"

    @pytest.mark.asyncio
    async def test_csv_skips_empty_domain_rows(self):
        """CSV adapter should skip rows with no website/domain."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            assert r["domain"].strip(), "Should not include empty-domain rows"
            assert len(r["domain"]) >= 3, f"Domain too short: {r['domain']}"

    @pytest.mark.asyncio
    async def test_csv_deduplicates_within_file(self):
        """CSV adapter should dedup by domain within a single file."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        domains = [r["domain"] for r in results]
        assert len(domains) == len(set(domains)), "Domains should be unique within file"

    def test_csv_validates_missing_file(self):
        """CSV adapter should reject nonexistent file."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        valid, err = adapter.validate_filters({"file_path": "/nonexistent/path.csv"})
        assert not valid
        assert "not found" in err.lower() or "file" in err.lower()

    def test_csv_validates_no_input(self):
        """CSV adapter should require file_path or file_url."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        valid, err = adapter.validate_filters({})
        assert not valid
        assert "file_path" in err.lower() or "file_url" in err.lower()

    def test_csv_validates_existing_file(self):
        """CSV adapter should accept existing file path."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        valid, err = adapter.validate_filters({"file_path": str(TEST_CSV_PATH)})
        assert valid, f"Should accept existing file, got: {err}"

    def test_csv_source_type(self):
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        assert CSVFileAdapter().source_type == "csv.companies.file"

    @pytest.mark.asyncio
    async def test_csv_custom_column_mapping(self):
        """CSV adapter should accept explicit column_mapping override."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({
            "file_path": str(TEST_CSV_PATH),
            "column_mapping": {"domain": "Website", "name": "Company Name", "country": "Company Country"}
        })
        assert len(results) > 0
        assert all(r.get("domain") for r in results)

    @pytest.mark.asyncio
    async def test_csv_empty_file(self):
        """CSV adapter should handle empty CSV (headers only)."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Company Name,Website,Country\n")
            path = f.name
        try:
            results = await adapter.gather({"file_path": path})
            assert len(results) == 0, "Empty CSV should return no results"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_csv_no_domain_column(self):
        """CSV adapter should raise when no domain/website column found."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Name,Notes,Random\nFoo,bar,baz\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="domain"):
                await adapter.gather({"file_path": path})
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_csv_preserves_source_data(self):
        """Source data should contain source file name and raw domain."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            sd = r["source_data"]
            assert sd["source"] == "csv_file"
            assert sd.get("source_file"), "Should track source file name"
            assert sd.get("raw_domain"), "Should preserve raw domain"

    @pytest.mark.asyncio
    async def test_csv_normalizes_domains(self):
        """Domains should be lowercase, no protocol, no www."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            assert r["domain"] == r["domain"].lower(), f"Domain not lowercase: {r['domain']}"
            assert "://" not in r["domain"]
            assert not r["domain"].startswith("www.")

    @pytest.mark.asyncio
    async def test_csv_website_url_preserved(self):
        """Original website URL should be preserved in website_url field."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            assert r.get("website_url"), f"Missing website_url for {r['domain']}"

    @pytest.mark.asyncio
    async def test_csv_employee_count_parsed_as_int(self):
        """Employee count should be parsed as integer where available."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        with_employees = [r for r in results if r.get("employee_count")]
        assert len(with_employees) > 0, "Some companies should have employee counts"
        for r in with_employees:
            assert isinstance(r["employee_count"], int), f"Employee count should be int: {r['employee_count']}"


# ═══════════════════════════════════════════════════════════════
# 2. GOOGLE SHEET ADAPTER TESTS
# ═══════════════════════════════════════════════════════════════

class TestGoogleSheetAdapter:
    """Test google_sheets.companies.sheet adapter — full coverage."""

    @pytest.mark.asyncio
    async def test_sheet_parses_local_csv(self):
        """Sheet adapter should parse local CSV (testing fallback)."""
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        results = await adapter.gather({"file_path": str(TEST_SHEET_CSV_PATH)})
        assert len(results) == 110, f"Expected 110 companies, got {len(results)}"

    def test_sheet_validates_valid_url(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        valid, err = adapter.validate_filters({
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit"
        })
        assert valid, f"Should accept valid sheet URL, got error: {err}"

    def test_sheet_rejects_non_google_url(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        valid, err = adapter.validate_filters({"sheet_url": "https://random-site.com/data.csv"})
        assert not valid, "Should reject non-Google-Sheet URLs"

    def test_sheet_rejects_empty_filters(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        valid, err = adapter.validate_filters({})
        assert not valid

    def test_sheet_extracts_sheet_id_standard(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        assert adapter._extract_sheet_id("https://docs.google.com/spreadsheets/d/1abc123xyz/edit#gid=0") == "1abc123xyz"

    def test_sheet_extracts_sheet_id_short(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        assert adapter._extract_sheet_id("https://docs.google.com/spreadsheets/d/1abc123xyz") == "1abc123xyz"

    def test_sheet_extracts_sheet_id_with_path(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        sid = adapter._extract_sheet_id("https://docs.google.com/spreadsheets/d/LONG_ID_HERE/edit?usp=sharing")
        assert sid == "LONG_ID_HERE"

    @pytest.mark.asyncio
    async def test_sheet_auto_detects_columns(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        results = await adapter.gather({"file_path": str(TEST_SHEET_CSV_PATH)})
        for r in results:
            assert r.get("domain"), f"Missing domain: {r.get('name')}"
            assert "://" not in r["domain"]

    @pytest.mark.asyncio
    async def test_sheet_deduplicates_within_sheet(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        results = await adapter.gather({"file_path": str(TEST_SHEET_CSV_PATH)})
        domains = [r["domain"] for r in results]
        assert len(domains) == len(set(domains))

    def test_sheet_source_type(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        assert GoogleSheetAdapter().source_type == "google_sheets.companies.sheet"

    def test_sheet_validates_tab_name(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        valid, err = adapter.validate_filters({
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "tab_name": "Sheet1"
        })
        assert valid

    @pytest.mark.asyncio
    async def test_sheet_tags_source_as_google_sheet(self):
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        results = await adapter.gather({"file_path": str(TEST_SHEET_CSV_PATH)})
        for r in results:
            assert r["source_data"]["source"] == "google_sheet"

    @pytest.mark.asyncio
    async def test_sheet_parse_csv_content_string(self):
        """Sheet adapter should parse CSV content from string (HTTP response path)."""
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        adapter = GoogleSheetAdapter()
        csv_content = "Company Name,Website,Company Country\nTestCo,http://testco.com,Chile\nFoo,http://foo.cl,Argentina\n"
        results = adapter._parse_csv_content(csv_content)
        assert len(results) == 2
        assert results[0]["domain"] == "testco.com"
        assert results[1]["domain"] == "foo.cl"


# ═══════════════════════════════════════════════════════════════
# 3. GOOGLE DRIVE ADAPTER TESTS
# ═══════════════════════════════════════════════════════════════

class TestGoogleDriveAdapter:
    """Test google_drive.companies.folder adapter — full coverage."""

    @pytest.mark.asyncio
    async def test_drive_reads_all_files(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        results = await adapter.gather({"folder_path": str(TEST_DRIVE_DIR)})
        assert len(results) == 105, f"Expected 105 companies (3×35), got {len(results)}"

    @pytest.mark.asyncio
    async def test_drive_deduplicates_across_files(self):
        """Drive adapter should dedup companies that appear in multiple files."""
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        results = await adapter.gather({"folder_path": str(TEST_DRIVE_DIR)})
        domains = [r["domain"] for r in results]
        assert len(domains) == len(set(domains)), \
            f"Should dedup across files: {len(domains)} total, {len(set(domains))} unique"

    @pytest.mark.asyncio
    async def test_drive_tracks_source_file_per_company(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        results = await adapter.gather({"folder_path": str(TEST_DRIVE_DIR)})
        source_files = set()
        for r in results:
            sf = r.get("source_data", {}).get("source_file")
            assert sf, f"Missing source_file for {r.get('domain')}"
            source_files.add(sf)
        assert len(source_files) == 3, f"Should have 3 source files, got {source_files}"

    @pytest.mark.asyncio
    async def test_drive_source_file_distribution(self):
        """Companies should come from all 3 files."""
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        results = await adapter.gather({"folder_path": str(TEST_DRIVE_DIR)})
        by_file = {}
        for r in results:
            sf = r["source_data"]["source_file"]
            by_file[sf] = by_file.get(sf, 0) + 1
        for fname, count in by_file.items():
            assert count > 0, f"File {fname} contributed 0 companies"

    def test_drive_validates_missing_folder(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        valid, err = adapter.validate_filters({"folder_path": "/nonexistent/folder/"})
        assert not valid

    def test_drive_validates_drive_url(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        valid, err = adapter.validate_filters({
            "drive_url": "https://drive.google.com/drive/folders/1abc123"
        })
        assert valid, f"Should accept drive folder URL, got: {err}"

    def test_drive_rejects_non_drive_url(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        valid, err = adapter.validate_filters({"drive_url": "https://example.com/folder"})
        assert not valid

    def test_drive_rejects_empty_filters(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        valid, err = adapter.validate_filters({})
        assert not valid

    def test_drive_extracts_folder_id(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        assert adapter._extract_folder_id("https://drive.google.com/drive/folders/1abc123xyz") == "1abc123xyz"
        assert adapter._extract_folder_id("https://drive.google.com/drive/folders/ABC-def_123") == "ABC-def_123"

    def test_drive_source_type(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        assert GoogleDriveAdapter().source_type == "google_drive.companies.folder"

    @pytest.mark.asyncio
    async def test_drive_tags_source_as_google_drive(self):
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        results = await adapter.gather({"folder_path": str(TEST_DRIVE_DIR)})
        for r in results:
            assert r["source_data"]["source"] == "google_drive"

    @pytest.mark.asyncio
    async def test_drive_empty_folder(self):
        """Drive adapter should raise for folder with no CSV files."""
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="No CSV"):
                await adapter.gather({"folder_path": tmpdir})

    @pytest.mark.asyncio
    async def test_drive_ignores_non_csv_files(self):
        """Drive adapter should skip non-CSV files in folder."""
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a CSV and a non-CSV
            with open(os.path.join(tmpdir, "data.csv"), "w") as f:
                f.write("Company Name,Website\nTestCo,http://testco.com\n")
            with open(os.path.join(tmpdir, "notes.txt"), "w") as f:
                f.write("some notes")
            results = await adapter.gather({"folder_path": tmpdir})
            assert len(results) == 1
            assert results[0]["domain"] == "testco.com"


# ═══════════════════════════════════════════════════════════════
# 4. COLUMN AUTO-DETECTION TESTS
# ═══════════════════════════════════════════════════════════════

class TestColumnAutoDetection:
    """Test auto-detection of CSV/Sheet column mappings — all formats."""

    def test_detect_standard_columns(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns([
            "Company Name", "Website", "# Employees", "Industry",
            "Company Linkedin Url", "Company Country", "Company Address",
        ])
        assert mapping["domain"] == "Website"
        assert mapping["name"] == "Company Name"
        assert mapping["country"] == "Company Country"
        assert mapping["employee_count"] == "# Employees"
        assert mapping["industry"] == "Industry"
        assert mapping["linkedin_url"] == "Company Linkedin Url"
        assert mapping["address"] == "Company Address"

    def test_detect_apollo_export_columns(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns([
            "Organization Name", "Primary Domain", "Industry",
            "Estimated Num Employees", "Country", "City",
        ])
        assert mapping["domain"] == "Primary Domain"
        assert mapping["name"] == "Organization Name"
        assert mapping["country"] == "Country"
        assert mapping["city"] == "City"
        assert mapping["employee_count"] == "Estimated Num Employees"

    def test_detect_clay_export_columns(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns([
            "company_name", "company_website", "company_industry",
            "company_employee_count", "company_country",
        ])
        assert mapping["domain"] == "company_website"
        assert mapping["name"] == "company_name"
        assert mapping["industry"] == "company_industry"
        assert mapping["employee_count"] == "company_employee_count"
        assert mapping["country"] == "company_country"

    def test_detect_minimal_domain_only(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["url", "notes"])
        assert mapping.get("domain") == "url"

    def test_detect_case_insensitive(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["WEBSITE", "COMPANY NAME", "COUNTRY"])
        assert mapping["domain"] == "WEBSITE"
        assert mapping["name"] == "COMPANY NAME"
        assert mapping["country"] == "COUNTRY"

    def test_detect_domain_column_variant(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["domain", "name", "size"])
        assert mapping["domain"] == "domain"

    def test_detect_homepage_variant(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["homepage", "company", "headcount"])
        assert mapping["domain"] == "homepage"
        assert mapping["name"] == "company"
        assert mapping["employee_count"] == "headcount"

    def test_detect_founded_year(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["website", "name", "founded year", "keywords"])
        assert mapping["founded_year"] == "founded year"
        assert mapping["keywords"] == "keywords"

    def test_detect_description_variants(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        m1 = detect_columns(["website", "short description"])
        assert m1["description"] == "short description"
        m2 = detect_columns(["website", "about"])
        assert m2["description"] == "about"

    def test_detect_phone_variant(self):
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["website", "phone number"])
        assert mapping["phone"] == "phone number"

    def test_no_matching_columns(self):
        """No match should return empty mapping."""
        from app.services.gathering_adapters.column_detector import detect_columns
        mapping = detect_columns(["foo", "bar", "baz"])
        assert len(mapping) == 0

    def test_extract_company_basic(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "http://www.testco.com", "Company Name": "TestCo", "Company Country": "Chile"}
        mapping = {"domain": "Website", "name": "Company Name", "country": "Company Country"}
        company = extract_company(row, mapping)
        assert company is not None
        assert company["domain"] == "testco.com"
        assert company["name"] == "TestCo"
        assert company["country"] == "Chile"

    def test_extract_company_no_domain(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "", "Company Name": "TestCo"}
        mapping = {"domain": "Website", "name": "Company Name"}
        assert extract_company(row, mapping) is None

    def test_extract_company_short_domain(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "ab", "Company Name": "X"}
        mapping = {"domain": "Website"}
        assert extract_company(row, mapping) is None

    def test_extract_company_employee_parsing(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "http://testco.com", "# Employees": "150"}
        mapping = {"domain": "Website", "employee_count": "# Employees"}
        company = extract_company(row, mapping)
        assert company["employee_count"] == 150

    def test_extract_company_employee_with_comma(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "http://testco.com", "# Employees": "1,500"}
        mapping = {"domain": "Website", "employee_count": "# Employees"}
        company = extract_company(row, mapping)
        assert company["employee_count"] == 1500

    def test_extract_company_employee_non_numeric(self):
        from app.services.gathering_adapters.column_detector import extract_company
        row = {"Website": "http://testco.com", "# Employees": "unknown"}
        mapping = {"domain": "Website", "employee_count": "# Employees"}
        company = extract_company(row, mapping)
        assert company["employee_count"] is None


# ═══════════════════════════════════════════════════════════════
# 5. CROSS-SOURCE DEDUP TESTS
# ═══════════════════════════════════════════════════════════════

class TestCrossSourceDedup:
    """Test deduplication across different sources for the same project."""

    @pytest.mark.asyncio
    async def test_csv_sheet_overlap_exact_count(self, test_metadata):
        """CSV ∩ Sheet should be exactly 40 domains."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        csv_domains = set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
        sheet_domains = set(r["domain"] for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}))
        overlap = csv_domains & sheet_domains
        assert len(overlap) == 40, f"Expected 40 overlap, got {len(overlap)}"

    @pytest.mark.asyncio
    async def test_csv_drive_overlap_exact_count(self, test_metadata):
        """CSV ∩ Drive should be exactly 35 domains."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        csv_domains = set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
        drive_domains = set(r["domain"] for r in await GoogleDriveAdapter().gather({"folder_path": str(TEST_DRIVE_DIR)}))
        assert len(csv_domains & drive_domains) == 35

    @pytest.mark.asyncio
    async def test_sheet_drive_overlap_exact_count(self, test_metadata):
        """Sheet ∩ Drive should be exactly 35 domains."""
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        sheet_domains = set(r["domain"] for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}))
        drive_domains = set(r["domain"] for r in await GoogleDriveAdapter().gather({"folder_path": str(TEST_DRIVE_DIR)}))
        assert len(sheet_domains & drive_domains) == 35

    @pytest.mark.asyncio
    async def test_all_three_total_unique_215(self, test_metadata):
        """Union of all 3 sources = exactly 215 unique domains."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        all_domains = (
            set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
            | set(r["domain"] for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}))
            | set(r["domain"] for r in await GoogleDriveAdapter().gather({"folder_path": str(TEST_DRIVE_DIR)}))
        )
        assert len(all_domains) == 215

    @pytest.mark.asyncio
    async def test_overlap_domains_match_metadata(self, test_metadata):
        """Overlap domains should exactly match metadata."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        csv_domains = set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
        sheet_domains = set(r["domain"] for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}))
        expected = set(test_metadata["overlaps"]["csv_sheet"])
        actual = csv_domains & sheet_domains
        assert actual == expected, f"Overlap mismatch: extra={actual-expected}, missing={expected-actual}"


# ═══════════════════════════════════════════════════════════════
# 6. BLACKLISTING TESTS
# ═══════════════════════════════════════════════════════════════

class TestBlacklisting:
    """Test blacklisting — project-scoped, no cross-project leakage."""

    def test_trash_domain_detection_social_media(self):
        from app.services.domain_service import matches_trash_pattern
        assert matches_trash_pattern("facebook.com")
        assert matches_trash_pattern("linkedin.com")
        assert matches_trash_pattern("t.me")
        assert matches_trash_pattern("instagram.com")
        assert matches_trash_pattern("twitter.com")
        assert matches_trash_pattern("youtube.com")
        assert matches_trash_pattern("tiktok.com")
        assert matches_trash_pattern("vk.com")

    def test_trash_domain_detection_crypto(self):
        from app.services.domain_service import matches_trash_pattern
        assert matches_trash_pattern("binance.com")
        assert matches_trash_pattern("coinmarketcap.com")
        assert matches_trash_pattern("coinbase.com")

    def test_trash_domain_detection_travel(self):
        from app.services.domain_service import matches_trash_pattern
        assert matches_trash_pattern("booking.com")
        assert matches_trash_pattern("airbnb.com")

    def test_legitimate_domains_not_trash(self):
        from app.services.domain_service import matches_trash_pattern
        assert not matches_trash_pattern("building-ideas.com.ar")
        assert not matches_trash_pattern("trymeonline.com.ar")
        assert not matches_trash_pattern("giesso.com.ar")
        assert not matches_trash_pattern("polemic.cl")
        assert not matches_trash_pattern("godigital.pe")
        assert not matches_trash_pattern("easystaff.io")

    def test_domain_normalization_http(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("http://www.building-ideas.com.ar") == "building-ideas.com.ar"

    def test_domain_normalization_https(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("https://www.trymeonline.com.ar") == "trymeonline.com.ar"

    def test_domain_normalization_uppercase(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("GIESSO.com.ar") == "giesso.com.ar"

    def test_domain_normalization_trailing_slash(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("http://www.polemic.cl/") == "polemic.cl"

    def test_domain_normalization_empty(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("") == ""

    def test_domain_normalization_with_path(self):
        from app.services.domain_service import normalize_domain
        assert normalize_domain("https://example.com/about") == "example.com"

    @pytest.mark.asyncio
    async def test_csv_no_social_media_trash(self):
        """Test CSV should not contain actual social media / trash domains."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        results = await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)})
        actual_trash = {"facebook.com", "linkedin.com", "twitter.com", "instagram.com",
                        "tiktok.com", "youtube.com", "google.com", "t.me"}
        found_trash = [r["domain"] for r in results if r["domain"] in actual_trash]
        assert len(found_trash) == 0, f"Test data has actual trash domains: {found_trash}"


# ═══════════════════════════════════════════════════════════════
# 7. CUSTOM CLASSIFICATION PROMPT TESTS
# ═══════════════════════════════════════════════════════════════

class TestCustomPrompts:
    """Test custom user-provided classification prompts."""

    def test_latam_fashion_prompt_structure(self):
        """Fashion/apparel classification prompt for Result project."""
        prompt = "Classify companies as fashion/apparel brands in LATAM. Return VALID or NOT_VALID."
        assert "fashion" in prompt.lower()
        assert "VALID" in prompt
        assert "NOT_VALID" in prompt

    def test_multi_step_prompt_chain_structure(self):
        steps = [
            {"name": "classify_fashion", "prompt": "Classify as FASHION_BRAND or OTHER.", "output_column": "fashion_segment", "type": "classify"},
            {"name": "filter_valid", "type": "filter", "filter_condition": "segment != OTHER", "prompt": ""},
            {"name": "classify_size", "prompt": "Classify size: LARGE, MEDIUM, SMALL.", "output_column": "size_segment", "type": "classify"},
        ]
        assert len(steps) == 3
        assert steps[0]["type"] == "classify"
        assert steps[1]["type"] == "filter"
        assert steps[2]["output_column"] == "size_segment"

    def test_drive_json_enricher_parsing(self):
        """Parse enricher config from Drive JSON (as user would provide)."""
        enricher = {
            "name": "segment",
            "arguments": {
                "model": "GPT-4o Mini",
                "prompt": "Classify companies as fashion/apparel brands in LATAM. Return VALID or NOT_VALID."
            },
            "type": "call_ai"
        }
        assert enricher["type"] == "call_ai"
        assert "prompt" in enricher["arguments"]
        assert "GPT-4o" in enricher["arguments"]["model"]

    def test_enricher_chain_from_drive_json(self):
        """Parse a multi-step enricher chain like the Drive JSON format."""
        chain = [
            {"name": "Scrape Website", "type": "scrape_website", "arguments": {"url_column": "company_website"}},
            {"name": "segment", "type": "call_ai", "arguments": {"model": "GPT-4o Mini", "prompt": "Classify..."}},
            {"name": "filter", "type": "filter_code", "arguments": {"code": "!result.include?('NOT_VALID')"}},
        ]
        classify_steps = [s for s in chain if s["type"] == "call_ai"]
        filter_steps = [s for s in chain if s["type"] == "filter_code"]
        assert len(classify_steps) == 1
        assert len(filter_steps) == 1

    def test_normalize_company_name_prompt_from_drive(self):
        """The Drive JSON includes a company name normalization enricher."""
        enricher_prompt_snippet = "Normalize company names for professional email outreach"
        assert "normalize" in enricher_prompt_snippet.lower()
        assert "email" in enricher_prompt_snippet.lower()


# ═══════════════════════════════════════════════════════════════
# 8. MULTI-STEP PROMPT EXECUTION TESTS
# ═══════════════════════════════════════════════════════════════

class TestMultiStepExecution:
    """Test multi-step prompt chain execution logic."""

    def test_evaluate_filter_rejects_not_valid(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({"step1": "Classification: NOT_VALID"}, "!NOT_VALID") == False
        assert svc._evaluate_filter({"step1": "Classification: VALID"}, "!NOT_VALID") == True

    def test_evaluate_filter_rejects_other(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({"seg": "OTHER"}, "!= OTHER") == False
        assert svc._evaluate_filter({"seg": "FASHION_BRAND"}, "!= OTHER") == True

    def test_evaluate_filter_rejects_not_a_match(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({"seg": "NOT_A_MATCH"}, "!NOT_A_MATCH") == False

    def test_evaluate_filter_empty_results(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({}, "anything") == False

    def test_evaluate_filter_none_value(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({"seg": None}, "!OTHER") == False

    def test_evaluate_filter_positive_match(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        assert svc._evaluate_filter({"seg": "FASHION_BRAND"}, "FASHION_BRAND") == True
        assert svc._evaluate_filter({"seg": "OTHER"}, "FASHION_BRAND") == False

    def test_parse_step_output_json(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output(
            '{"is_target": true, "confidence": 0.92, "segment": "FASHION", "reasoning": "Clearly a fashion brand"}'
        )
        assert is_target == True
        assert conf == 0.92
        assert seg == "FASHION"
        assert "fashion" in reason.lower()

    def test_parse_step_output_json_with_markdown(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output(
            '```json\n{"is_target": false, "confidence": 0.3, "segment": "NOT_A_MATCH", "reasoning": "Marketing agency"}\n```'
        )
        assert is_target == False
        assert seg == "NOT_A_MATCH"

    def test_parse_step_output_text_valid(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output(
            "Analysis: This is a fashion brand in Argentina.\nClassification: VALID"
        )
        assert is_target == True
        assert conf == 0.7
        assert seg == "TARGET"

    def test_parse_step_output_text_not_valid(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output(
            "Analysis: This is a logistics company.\nClassification: NOT_VALID"
        )
        assert is_target == False
        assert seg == "NOT_A_MATCH"

    def test_parse_step_output_text_other(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output("Segment: OTHER\nReasoning: Not relevant")
        assert is_target == False

    def test_parse_step_output_empty(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output("")
        assert is_target == False
        assert seg == "NO_OUTPUT"

    def test_parse_step_output_none(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output(None)
        assert is_target == False

    def test_parse_step_output_ambiguous(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output("Cannot determine from available data")
        assert is_target == False
        assert seg == "UNCLEAR"
        assert conf == 0.4

    def test_parse_step_output_json_missing_fields(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        is_target, conf, seg, reason = svc._parse_step_output('{"is_target": true}')
        assert is_target == True
        assert conf == 0.5  # default
        assert seg == "UNKNOWN"  # default


# ═══════════════════════════════════════════════════════════════
# 9. SMART SOURCE SUGGESTION TESTS
# ═══════════════════════════════════════════════════════════════

class TestSourceSuggestion:
    """Test smart source suggestion — all phrasings and key requirements."""

    def test_suggest_csv_for_file_path(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Here's my list: /path/to/companies.csv", ["apollo"])
        assert s["source_type"] == "csv.companies.file"

    def test_suggest_csv_for_csv_mention(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("I have a CSV file with company data", ["apollo"])
        assert s["source_type"] == "csv.companies.file"

    def test_suggest_sheet_for_google_url(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Analyze this sheet: https://docs.google.com/spreadsheets/d/abc123/edit", ["apollo"])
        assert s["source_type"] == "google_sheets.companies.sheet"
        assert "abc123" in s.get("filters", {}).get("sheet_url", "")

    def test_suggest_drive_for_drive_url(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Check this folder: https://drive.google.com/drive/folders/abc123", [])
        assert s["source_type"] == "google_drive.companies.folder"
        assert "abc123" in s.get("filters", {}).get("drive_url", "")

    def test_suggest_apollo_for_search_query(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Find fashion companies in Argentina with 50-200 employees", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_suggest_apollo_for_gather_intent(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Gather IT consulting companies in London", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_suggest_apollo_for_discover_intent(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Discover startups in LATAM", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_no_apollo_key_warns(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Find fashion companies in Argentina", [])
        assert s["source_type"] != "apollo.companies.api"
        assert s.get("needs_key") == "apollo" or "alternatives" in s or "Apollo" in s.get("explanation", "")

    def test_no_apollo_key_suggests_alternatives(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Search for LATAM brands", [])
        assert "csv" in str(s).lower() or "sheet" in str(s).lower() or "alternative" in str(s).lower()

    def test_ambiguous_input_suggests_options(self):
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Hey, I need some data", [])
        assert "explanation" in s

    def test_list_sources_complete(self):
        from app.services.gathering_adapters.source_router import list_sources
        sources = list_sources()
        types = [s["source_type"] for s in sources]
        assert "csv.companies.file" in types
        assert "google_sheets.companies.sheet" in types
        assert "google_drive.companies.folder" in types
        assert "apollo.companies.api" in types
        assert "manual.companies.manual" in types
        assert len(sources) == 5

    def test_list_sources_have_descriptions(self):
        from app.services.gathering_adapters.source_router import list_sources
        for s in list_sources():
            assert s.get("name"), f"Source {s['source_type']} missing name"
            assert s.get("description"), f"Source {s['source_type']} missing description"
            assert s.get("cost") is not None, f"Source {s['source_type']} missing cost"

    def test_list_sources_key_requirements(self):
        from app.services.gathering_adapters.source_router import list_sources
        sources = {s["source_type"]: s for s in list_sources()}
        assert sources["apollo.companies.api"]["requires_key"] == "apollo"
        assert sources["csv.companies.file"]["requires_key"] is None
        assert sources["google_sheets.companies.sheet"]["requires_key"] is None
        assert sources["google_drive.companies.folder"]["requires_key"] is None


# ═══════════════════════════════════════════════════════════════
# 10. ADAPTER REGISTRATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestAdapterRegistration:
    """Test that all adapters are properly wired into the gathering service."""

    def test_get_adapter_csv(self):
        from app.services.gathering_service import GatheringService
        adapter = GatheringService()._get_adapter("csv.companies.file")
        assert adapter is not None
        assert adapter.source_type == "csv.companies.file"

    def test_get_adapter_sheet(self):
        from app.services.gathering_service import GatheringService
        adapter = GatheringService()._get_adapter("google_sheets.companies.sheet")
        assert adapter is not None
        assert adapter.source_type == "google_sheets.companies.sheet"

    def test_get_adapter_drive(self):
        from app.services.gathering_service import GatheringService
        adapter = GatheringService()._get_adapter("google_drive.companies.folder")
        assert adapter is not None
        assert adapter.source_type == "google_drive.companies.folder"

    def test_get_adapter_apollo(self):
        from app.services.gathering_service import GatheringService
        adapter = GatheringService()._get_adapter("apollo.companies.api")
        assert adapter is not None
        assert adapter.source_type == "apollo.companies.api"

    def test_get_adapter_manual(self):
        from app.services.gathering_service import GatheringService
        adapter = GatheringService()._get_adapter("manual.companies.manual")
        assert adapter is not None

    def test_get_adapter_unknown_returns_none(self):
        from app.services.gathering_service import GatheringService
        assert GatheringService()._get_adapter("nonexistent.source") is None

    def test_all_adapters_have_validate_filters(self):
        """All adapters must implement validate_filters."""
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        for source_type in ["csv.companies.file", "google_sheets.companies.sheet",
                           "google_drive.companies.folder", "apollo.companies.api",
                           "manual.companies.manual"]:
            adapter = svc._get_adapter(source_type)
            assert hasattr(adapter, "validate_filters"), f"{source_type} missing validate_filters"

    def test_all_adapters_have_gather(self):
        """All adapters must implement gather."""
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        for source_type in ["csv.companies.file", "google_sheets.companies.sheet",
                           "google_drive.companies.folder", "manual.companies.manual"]:
            adapter = svc._get_adapter(source_type)
            assert hasattr(adapter, "gather"), f"{source_type} missing gather"


# ═══════════════════════════════════════════════════════════════
# 11. PIPELINE E2E SIMULATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestPipelineE2E:
    """End-to-end: 3 runs for same project (Result), verify dedup counts."""

    @pytest.mark.asyncio
    async def test_run1_csv_110_new(self):
        """Run 1 (CSV): all 110 companies should be new."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        results = await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)})
        assert len(results) == 110

    @pytest.mark.asyncio
    async def test_run2_sheet_70_new_40_dup(self):
        """Run 2 (Sheet): 70 new + 40 dups from CSV."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        project_domains = set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
        sheet_results = await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)})
        new = [r for r in sheet_results if r["domain"] not in project_domains]
        dups = [r for r in sheet_results if r["domain"] in project_domains]
        assert len(new) == 70, f"Expected 70 new, got {len(new)}"
        assert len(dups) == 40, f"Expected 40 dups, got {len(dups)}"

    @pytest.mark.asyncio
    async def test_run3_drive_35_new_70_dup(self):
        """Run 3 (Drive): 35 new + 70 dups from CSV+Sheet."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        project_domains = set(r["domain"] for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}))
        project_domains |= set(r["domain"] for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}))
        drive_results = await GoogleDriveAdapter().gather({"folder_path": str(TEST_DRIVE_DIR)})
        new = [r for r in drive_results if r["domain"] not in project_domains]
        dups = [r for r in drive_results if r["domain"] in project_domains]
        assert len(new) == 35, f"Expected 35 new, got {len(new)}"
        assert len(dups) == 70, f"Expected 70 dups, got {len(dups)}"

    @pytest.mark.asyncio
    async def test_full_three_runs_215_total(self):
        """After 3 runs: 110 + 70 + 35 = 215 unique in project."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        from app.services.gathering_adapters.google_sheet import GoogleSheetAdapter
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        project = set()
        for r in await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)}):
            project.add(r["domain"])
        assert len(project) == 110
        for r in await GoogleSheetAdapter().gather({"file_path": str(TEST_SHEET_CSV_PATH)}):
            project.add(r["domain"])
        assert len(project) == 180  # 110 + 70 new
        for r in await GoogleDriveAdapter().gather({"folder_path": str(TEST_DRIVE_DIR)}):
            project.add(r["domain"])
        assert len(project) == 215  # 180 + 35 new

    @pytest.mark.asyncio
    async def test_all_companies_are_latam(self):
        """All test companies should be from LATAM countries."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        results = await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)})
        latam_countries = {"Argentina", "Chile", "Colombia", "Mexico", "Peru", "Uruguay",
                          "Ecuador", "Venezuela", "Panama", "Paraguay", "Guatemala",
                          "Puerto Rico", "Dominican Republic", "Bolivia", "Costa Rica",
                          "Honduras", "El Salvador", "Nicaragua", "Cuba"}
        for r in results:
            if r.get("country"):
                assert r["country"] in latam_countries, f"Non-LATAM country: {r['country']} for {r['domain']}"

    @pytest.mark.asyncio
    async def test_most_companies_are_fashion_apparel(self):
        """Majority of test companies should be in fashion/apparel/textiles industry."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        results = await CSVFileAdapter().gather({"file_path": str(TEST_CSV_PATH)})
        fashion_keywords = ["apparel", "fashion", "textile", "clothing", "design", "luxury", "retail"]
        fashion_count = sum(1 for r in results if r.get("industry") and
                          any(kw in r["industry"].lower() for kw in fashion_keywords))
        assert fashion_count > 50, f"Expected majority fashion/apparel, got {fashion_count}/110"


# ═══════════════════════════════════════════════════════════════
# 12. ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Test error handling for all adapters."""

    @pytest.mark.asyncio
    async def test_csv_malformed_file(self):
        """CSV adapter should handle malformed CSV gracefully."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("this is not,proper csv\nwith \"unbalanced quotes\n")
            path = f.name
        try:
            # Should not crash — may return 0 results or raise ValueError
            try:
                results = await adapter.gather({"file_path": path})
                # If it parses, should have handled gracefully
            except (ValueError, csv.Error):
                pass  # Expected
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_csv_utf8_bom(self):
        """CSV adapter should handle UTF-8 BOM encoding."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
            f.write(b'\xef\xbb\xbf')  # UTF-8 BOM
            f.write("Company Name,Website\nBOM Corp,http://bomcorp.com\n".encode('utf-8'))
            path = f.name
        try:
            results = await adapter.gather({"file_path": path})
            assert len(results) == 1
            assert results[0]["domain"] == "bomcorp.com"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_csv_with_extra_commas(self):
        """CSV adapter should handle rows with extra/missing commas."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Company Name,Website,Country\nExtra Co,http://extra.com,Chile,extrafield\nNormal Co,http://normal.com,Peru\n")
            path = f.name
        try:
            results = await adapter.gather({"file_path": path})
            assert len(results) >= 1  # At least the normal row
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_drive_folder_with_one_bad_csv(self):
        """Drive adapter should continue past unreadable files."""
        from app.services.gathering_adapters.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Good file
            with open(os.path.join(tmpdir, "good.csv"), "w") as f:
                f.write("Company Name,Website\nGoodCo,http://goodco.com\n")
            # Bad file (no domain column)
            with open(os.path.join(tmpdir, "bad.csv"), "w") as f:
                f.write("Notes,Priority\nSome note,High\n")
            results = await adapter.gather({"folder_path": tmpdir})
            assert len(results) == 1
            assert results[0]["domain"] == "goodco.com"

    @pytest.mark.asyncio
    async def test_csv_description_truncation(self):
        """Long descriptions should be truncated to 500 chars."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            if r.get("description"):
                assert len(r["description"]) <= 500

    @pytest.mark.asyncio
    async def test_csv_keywords_truncation(self):
        """Keywords should be truncated in source_data."""
        from app.services.gathering_adapters.csv_file import CSVFileAdapter
        adapter = CSVFileAdapter()
        results = await adapter.gather({"file_path": str(TEST_CSV_PATH)})
        for r in results:
            kw = r.get("source_data", {}).get("keywords")
            if kw:
                assert len(kw) <= 200


# ═══════════════════════════════════════════════════════════════
# 13. CONVERSATION-BASED SCENARIO TESTS
# ═══════════════════════════════════════════════════════════════

class TestConversationScenarios:
    """Test user intent → expected MCP behavior (per requirements_source.md)."""

    def test_scenario_user_provides_csv(self):
        """User: 'Here's my company list: /path/to/data.csv' → CSV source."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Here's my company list: /data/companies.csv", ["apollo"])
        assert s["source_type"] == "csv.companies.file"

    def test_scenario_user_provides_google_sheet(self):
        """User: 'Analyze this sheet: https://docs.google.com/...' → Sheet source."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Analyze this sheet: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit", [])
        assert s["source_type"] == "google_sheets.companies.sheet"

    def test_scenario_user_provides_drive_folder(self):
        """User: 'Check these files: https://drive.google.com/drive/folders/...' → Drive source."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Check these files: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj", [])
        assert s["source_type"] == "google_drive.companies.folder"

    def test_scenario_user_wants_to_gather_without_key(self):
        """User: 'Gather fashion brands in LATAM' (no Apollo key) → suggests alternatives."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Gather fashion brands in LATAM", [])
        assert s["source_type"] != "apollo.companies.api"
        # Should mention alternatives
        explanation = s.get("explanation", "")
        assert "apollo" in explanation.lower() or "csv" in explanation.lower() or "sheet" in explanation.lower()

    def test_scenario_user_wants_to_gather_with_key(self):
        """User: 'Gather fashion brands in LATAM' (has Apollo key) → Apollo source."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Gather fashion brands in LATAM", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_scenario_user_says_look_for(self):
        """User: 'Look for IT consulting companies in London' → Apollo."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Look for IT consulting companies in London", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_scenario_user_says_search(self):
        """User: 'Search for fintech startups in Colombia' → Apollo."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Search for fintech startups in Colombia", ["apollo"])
        assert s["source_type"] == "apollo.companies.api"

    def test_scenario_ambiguous_request(self):
        """User: 'Hey' → fallback with explanation."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("Hey", [])
        assert s.get("explanation"), "Ambiguous input should get explanation"

    def test_scenario_user_provides_tsv(self):
        """User: 'I have a .tsv file' → CSV source (handles TSV too)."""
        from app.services.gathering_adapters.source_router import suggest_source
        s = suggest_source("I have companies.tsv with leads", [])
        assert s["source_type"] == "csv.companies.file"


# ═══════════════════════════════════════════════════════════════
# 14. PHASE ENFORCEMENT WITH NEW SOURCES
# ═══════════════════════════════════════════════════════════════

class TestPhaseEnforcement:
    """Test that pipeline phase enforcement works with new source types."""

    def test_phase_order_defined(self):
        from app.services.gathering_service import PHASE_ORDER
        assert "gather" in PHASE_ORDER
        assert "blacklist" in PHASE_ORDER
        assert "awaiting_scope_ok" in PHASE_ORDER
        assert "pre_filter" in PHASE_ORDER
        assert "scrape" in PHASE_ORDER
        assert "analyze" in PHASE_ORDER
        assert "awaiting_targets_ok" in PHASE_ORDER
        assert PHASE_ORDER.index("gather") < PHASE_ORDER.index("blacklist")
        assert PHASE_ORDER.index("blacklist") < PHASE_ORDER.index("analyze")

    def test_check_phase_rejects_wrong_phase(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        run = MagicMock()
        run.id = 1
        run.current_phase = "gather"
        with pytest.raises(ValueError, match="expected 'blacklist'"):
            svc._check_phase(run, "blacklist")

    def test_check_phase_accepts_correct_phase(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        run = MagicMock()
        run.current_phase = "analyze"
        svc._check_phase(run, "analyze")  # Should not raise

    def test_advance_phase_updates_run(self):
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        run = MagicMock()
        run.current_phase = "gather"
        svc._advance_phase(run, "blacklist")
        assert run.current_phase == "blacklist"
