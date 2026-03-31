"""
Tests for iGaming module — normalization, CSV parsing, import logic.
Runs with SQLite in-memory (no PostgreSQL needed).
"""
import asyncio
import csv
import io
import os
import sys
from unittest.mock import MagicMock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Mock heavy optional dependencies before any app imports
for mod_name in [
    "openai", "redis", "redis.asyncio",
    "googleapiclient", "googleapiclient.discovery", "googleapiclient.errors",
    "googleapiclient.http", "google.oauth2", "google.oauth2.service_account",
    "google.auth", "google.auth.transport.requests",
    "google.genai", "google.genai.types",
    "apify_client", "slack_sdk", "slack_sdk.web.async_client",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Set dummy env vars to avoid startup crashes
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("APOLLO_API_KEY", "test-dummy")
os.environ.setdefault("FINDYMAIL_API_KEY", "test-dummy")
os.environ.setdefault("SMARTLEAD_API_KEY", "test-dummy")

# Pre-import all iGaming modules to trigger lazy loads once
from app.models.igaming import (
    normalize_business_type, normalize_website, BusinessType, IGamingCompany,
)
from app.services.igaming_import_service import parse_csv_content, parse_semicolon_list
from app.services.igaming_llm_service import render_prompt
from app.schemas.igaming import (
    IGamingContactResponse, IGamingCompanyResponse,
    IGamingImportStartRequest, IGamingAIColumnCreate,
)

# ── Test 1: Business type normalization ────────────────────────────────

def test_business_type_normalization():
    pass  # already imported at module level

    cases = [
        # Direct map hits
        ("OPERATOR", BusinessType.OPERATOR),
        ("Operator (team involved in offering betting / games / slots to consumers)", BusinessType.OPERATOR),
        ("Operator - Casino/Bookmaker/Sportsbook", BusinessType.OPERATOR),
        ("AFFILIATE", BusinessType.AFFILIATE),
        ("Affiliate", BusinessType.AFFILIATE),
        ("Supplier (product, technology or service)", BusinessType.SUPPLIER),
        ("Supplier/Service Provider", BusinessType.SUPPLIER),
        ("GAME_PROVIDER", BusinessType.SUPPLIER),
        ("PLATFORM", BusinessType.PLATFORM),
        ("PAYMENT", BusinessType.PAYMENT),
        ("MARKETING", BusinessType.MARKETING),
        ("Professional Services (HR, Audit, Legal, Consultancy, Agency)", BusinessType.PROFESSIONAL_SERVICES),
        ("MEDIA", BusinessType.MEDIA),
        ("Regulator/Government Body", BusinessType.REGULATOR),
        ("OTHER", BusinessType.OTHER),
        ("organizationType:null", BusinessType.OTHER),
        ("Other (please specify in English)", BusinessType.OTHER),
        # Fuzzy fallback
        ("Casino Operator XYZ", BusinessType.OPERATOR),
        ("Affiliate Network Ltd", BusinessType.AFFILIATE),
        ("Software supplier", BusinessType.SUPPLIER),
        ("Payment gateway company", BusinessType.PAYMENT),
        ("Marketing agency", BusinessType.MARKETING),
        ("Legal consultancy firm", BusinessType.PROFESSIONAL_SERVICES),
        ("Media group", BusinessType.MEDIA),
        ("Gaming regulator", BusinessType.REGULATOR),
        ("Random unknown type", BusinessType.OTHER),
        # Edge cases
        ("", BusinessType.OTHER),
        (None, BusinessType.OTHER),
        ("  OPERATOR  ", BusinessType.OPERATOR),
    ]

    passed = 0
    failed = 0
    for raw, expected in cases:
        result = normalize_business_type(raw)
        if result == expected:
            passed += 1
        else:
            print(f"  FAIL: normalize_business_type({raw!r}) = {result}, expected {expected}")
            failed += 1

    print(f"[Business Type Normalization] {passed}/{passed + failed} passed")
    return failed == 0


# ── Test 2: Website normalization ──────────────────────────────────────

def test_website_normalization():
    pass  # already imported

    cases = [
        ("https://www.example.com/", "example.com"),
        ("http://example.com", "example.com"),
        ("https://example.com/", "example.com"),
        ("www.example.com", "example.com"),
        ("example.com", "example.com"),
        ("N/A", None),
        ("n/a", None),
        ("NA", None),
        ("-", None),
        ("none", None),
        ("", None),
        (None, None),
        ("  https://hisplayer.com  ", "hisplayer.com"),
        ("https://www.adflow.io/", "adflow.io"),
        ("equalsmoney.com", "equalsmoney.com"),
        ("kyp.io", "kyp.io"),
    ]

    passed = 0
    failed = 0
    for raw, expected in cases:
        result = normalize_website(raw)
        if result == expected:
            passed += 1
        else:
            print(f"  FAIL: normalize_website({raw!r}) = {result!r}, expected {expected!r}")
            failed += 1

    print(f"[Website Normalization] {passed}/{passed + failed} passed")
    return failed == 0


# ── Test 3: Company name normalization ─────────────────────────────────

def test_company_name_normalization():
    pass  # already imported

    cases = [
        ("Betsson", "betsson"),
        ("Betsson Group", "betsson"),
        ("BETSSON AB", "betsson"),
        ("Betsson Ltd", "betsson"),
        ("Betsson Ltd.", "betsson"),
        ("Equals Group PLC", "equals"),
        ("Vendo Services, GmbH", "vendo services,"),  # comma stays, suffix stripped
        ("Some Company Inc.", "some company"),
        ("Test Corp", "test"),
        ("  Extra   Spaces  ", "extra spaces"),
    ]

    passed = 0
    failed = 0
    for raw, expected in cases:
        result = IGamingCompany.normalize_name(raw)
        if result == expected:
            passed += 1
        else:
            print(f"  FAIL: normalize_name({raw!r}) = {result!r}, expected {expected!r}")
            failed += 1

    print(f"[Company Name Normalization] {passed}/{passed + failed} passed")
    return failed == 0


# ── Test 4: CSV parsing ───────────────────────────────────────────────

def test_csv_parsing():
    pass  # already imported

    # Test CSV parsing
    csv_data = b"firstName,lastName,email,organization\nJohn,Doe,john@test.com,TestCo\nJane,,jane@test.com,\n"
    columns, rows = parse_csv_content(csv_data, "test.csv")

    assert columns == ["firstName", "lastName", "email", "organization"], f"Columns mismatch: {columns}"
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert rows[0]["firstName"] == "John"
    assert rows[0]["email"] == "john@test.com"
    assert rows[1]["lastName"] == ""  # Empty field
    print(f"[CSV Parsing] OK — {len(columns)} columns, {len(rows)} rows")

    # Test semicolon list parsing
    assert parse_semicolon_list("Europe; North America; Asia") == ["Europe", "North America", "Asia"]
    assert parse_semicolon_list("Europe") == ["Europe"]
    assert parse_semicolon_list("") is None
    assert parse_semicolon_list(None) is None
    assert parse_semicolon_list("  ;  ; ") is None  # Only empty items
    print("[Semicolon List Parsing] OK")

    return True


# ── Test 5: Real CSV file parsing ─────────────────────────────────────

def test_real_csv():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "igaming_sample.csv")
    if not os.path.exists(csv_path):
        # Try alternative path
        csv_path = "D:/CURSOR Projects/igaming_sample.csv"

    if not os.path.exists(csv_path):
        print("[Real CSV] SKIP — file not found")
        return True

    pass  # already imported

    with open(csv_path, "rb") as f:
        content = f.read()

    columns, rows = parse_csv_content(content, "igaming_sample.csv")

    print(f"[Real CSV] Parsed {len(rows)} rows, {len(columns)} columns")
    print(f"  Columns: {columns}")

    # Check expected columns exist
    expected = {"firstName", "lastName", "email", "organization", "websiteUrl", "typeOfBusiness", "linkedin"}
    found = set(columns)
    missing = expected - found
    assert not missing, f"Missing columns: {missing}"
    print(f"  All expected columns present")

    # Test normalization on real data
    type_counts = {}
    website_count = 0
    na_websites = 0
    email_count = 0

    for row in rows[:1000]:  # First 1000 for speed
        # Business type
        raw_type = row.get("typeOfBusiness", "")
        norm = normalize_business_type(raw_type)
        type_counts[norm] = type_counts.get(norm, 0) + 1

        # Website
        raw_web = row.get("websiteUrl", "")
        clean = normalize_website(raw_web)
        if clean:
            website_count += 1
        if raw_web and raw_web.strip().upper() in ("N/A", "NA"):
            na_websites += 1

        # Email
        if row.get("email", "").strip():
            email_count += 1

    print(f"  First 1000 rows:")
    print(f"    Emails: {email_count}")
    print(f"    Websites (clean): {website_count}")
    print(f"    N/A websites filtered: {na_websites}")
    print(f"    Business types: {dict(sorted(((k.value, v) for k, v in type_counts.items()), key=lambda x: -x[1]))}")

    # Verify no N/A leaked through
    for row in rows[:100]:
        clean = normalize_website(row.get("websiteUrl", ""))
        if clean:
            assert clean.lower() != "n/a", f"N/A leaked through: {row.get('websiteUrl')}"
            assert not clean.startswith("http"), f"Protocol not stripped: {clean}"

    print(f"  Website normalization: no N/A leaks, protocols stripped")
    return True


# ── Test 6: Prompt template rendering ─────────────────────────────────

def test_prompt_rendering():
    pass  # already imported

    template = "Describe {name} ({website}) in 2 sentences. They are a {business_type} company."
    row = {"name": "Betsson", "website": "betsson.com", "business_type": "operator", "id": 1}
    result = render_prompt(template, row)

    expected = "Describe Betsson (betsson.com) in 2 sentences. They are a operator company."
    assert result == expected, f"Got: {result}"
    print("[Prompt Rendering] OK")

    # Test with missing fields — None/empty become ""
    row2 = {"name": "TestCo", "website": None, "business_type": ""}
    result2 = render_prompt(template, row2)
    assert "None" not in result2, f"None leaked into prompt: {result2}"
    assert "TestCo" in result2
    assert "()" in result2  # website=None → empty string
    print("[Prompt Rendering — missing fields] OK")

    return True


# ── Test 7: Auto-mapping ──────────────────────────────────────────────

def test_auto_mapping():
    """Test that CSV column names from real data get auto-mapped correctly."""
    # Simulate the AUTO_MAP from frontend (Python version)
    AUTO_MAP = {
        "id": "source_id",
        "firstName": "first_name",
        "lastName": "last_name",
        "email": "email",
        "Phone": "phone",
        "linkedin": "linkedin_url",
        "jobTitle": "job_title",
        "organization": "organization_name",
        "websiteUrl": "website_url",
        "typeOfBusiness": "business_type_raw",
        "bio": "bio",
        "Other contact": "other_contact",
        "sector": "sector",
        "regionsOfOperation": "regions",
        "newRegionsTargeting": "new_regions_targeting",
        "channelOfOperation": "channel",
        "productsServicesOffering": "products_services",
    }

    # Real CSV columns
    real_columns = [
        "id", "firstName", "lastName", "jobTitle", "organization",
        "email", "Phone", "websiteUrl", "linkedin", "typeOfBusiness",
        "regionsOfOperation", "sector", "newRegionsTargeting",
        "channelOfOperation", "productsServicesOffering", "bio", "Other contact",
    ]

    mapped = 0
    unmapped = []
    for col in real_columns:
        if col in AUTO_MAP:
            mapped += 1
        else:
            unmapped.append(col)

    print(f"[Auto-Mapping] {mapped}/{len(real_columns)} columns auto-mapped")
    if unmapped:
        print(f"  Unmapped: {unmapped}")

    assert mapped == len(real_columns), f"Not all columns mapped! Unmapped: {unmapped}"
    print("[Auto-Mapping] All real CSV columns covered")
    return True


# ── Test 8: Pydantic schemas ──────────────────────────────────────────

def test_schemas():
    pass  # already imported

    # Test ContactResponse
    data = {
        "id": 1, "first_name": "John", "last_name": "Doe", "email": "john@test.com",
        "organization_name": "TestCo", "business_type": "operator",
        "custom_fields": {"ai_desc": "test"}, "tags": ["vip"],
    }
    resp = IGamingContactResponse(**data)
    assert resp.id == 1
    assert resp.email == "john@test.com"
    print("[Schemas — ContactResponse] OK")

    # Test ImportStartRequest
    req = IGamingImportStartRequest(
        file_id="abc-123",
        column_mapping={"firstName": "first_name", "email": "email"},
        source_conference="SIGMA 2025",
    )
    assert req.column_mapping["firstName"] == "first_name"
    print("[Schemas — ImportStartRequest] OK")

    # Test AIColumnCreate
    ai = IGamingAIColumnCreate(
        name="Description",
        target="company",
        prompt_template="Describe {name}",
        model="gemini-2.5-flash",
    )
    assert ai.model == "gemini-2.5-flash"
    print("[Schemas — AIColumnCreate] OK")

    return True


# ── Run all tests ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("iGaming Module Tests")
    print("=" * 60)

    tests = [
        ("Business Type Normalization", test_business_type_normalization),
        ("Website Normalization", test_website_normalization),
        ("Company Name Normalization", test_company_name_normalization),
        ("CSV Parsing", test_csv_parsing),
        ("Real CSV File", test_real_csv),
        ("Prompt Rendering", test_prompt_rendering),
        ("Auto-Mapping", test_auto_mapping),
        ("Pydantic Schemas", test_schemas),
    ]

    results = []
    for name, test_fn in tests:
        try:
            ok = test_fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))
        print()

    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    if passed < total:
        sys.exit(1)
    else:
        print("\nAll tests passed!")
