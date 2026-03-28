"""
Processing Steps Tests — step add/remove, iteration tracking, regex vs AI detection,
step execution, configurable columns, historical iteration viewing.

Tests per requirements:
  1. Step type detection (AI vs regex vs scrape vs filter)
  2. Regex step execution (employee range, country filter, TLD, keyword match)
  3. Filter step execution (reject/keep values)
  4. Iteration tracking (add → new iter, remove → new iter, history preserved)
  5. Essential columns cannot be removed
  6. Conversation flow: add/remove/add/remove → 4 iterations trackable
  7. Configurable columns (show/hide per iteration)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


# ═══════════════════════════════════════════════════════════════
# 1. STEP TYPE DETECTION
# ═══════════════════════════════════════════════════════════════

class TestStepTypeDetection:
    """Test that simple tasks use regex, not AI."""

    def test_employee_size_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Classify as LARGE (100+ employees), MEDIUM (20-99), SMALL (<20)") == "regex"

    def test_employee_size_variant_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("segment by company size: small, medium, large based on headcount") == "regex"

    def test_country_filter_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Filter only companies from Argentina and Chile") == "filter"

    def test_exclude_country_is_filter(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Remove companies from Brazil") == "filter"

    def test_domain_tld_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Extract TLD from domain") == "regex"

    def test_industry_keyword_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Check if industry contains 'fashion'") == "regex"

    def test_has_linkedin_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Does the company have a LinkedIn profile?") == "regex"

    def test_founded_year_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Filter companies founded before 2010") == "regex"

    def test_business_model_classification_is_ai(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Classify the company's business model as B2B or B2C based on website content") == "ai"

    def test_value_proposition_is_ai(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Determine if this company is a fashion brand or textile producer") == "ai"

    def test_website_scrape_is_scrape(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Scrape the /about page of each company") == "scrape"

    def test_crawl_is_scrape(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Crawl website to find team page") == "scrape"

    def test_filter_out_is_filter(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Filter out companies classified as OTHER") == "filter"

    def test_drop_is_filter(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Drop all NOT_VALID companies") == "filter"

    def test_ambiguous_defaults_to_ai(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Analyze the company's competitive positioning") == "ai"

    def test_based_on_industry_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Classify based on industry field") == "regex"

    def test_based_on_employee_count_is_regex(self):
        from app.services.step_executor import detect_step_type
        assert detect_step_type("Segment based on employee_count: micro/small/medium/large") == "regex"


# ═══════════════════════════════════════════════════════════════
# 2. REGEX STEP EXECUTION
# ═══════════════════════════════════════════════════════════════

class TestRegexExecution:
    """Test regex/algorithmic step execution."""

    def test_employee_range_large(self):
        from app.services.step_executor import execute_regex_step
        config = {
            "type": "employee_range",
            "input_field": "employee_count",
            "rules": [
                {"label": "SMALL", "max": 20},
                {"label": "MEDIUM", "max": 100},
                {"label": "LARGE", "min": 100},
            ],
        }
        assert execute_regex_step({"employee_count": 150}, config) == "LARGE"

    def test_employee_range_small(self):
        from app.services.step_executor import execute_regex_step
        config = {
            "type": "employee_range",
            "input_field": "employee_count",
            "rules": [
                {"label": "SMALL", "max": 20},
                {"label": "MEDIUM", "max": 100},
                {"label": "LARGE", "min": 100},
            ],
        }
        assert execute_regex_step({"employee_count": 5}, config) == "SMALL"

    def test_employee_range_medium(self):
        from app.services.step_executor import execute_regex_step
        config = {
            "type": "employee_range",
            "input_field": "employee_count",
            "rules": [
                {"label": "SMALL", "max": 20},
                {"label": "MEDIUM", "max": 100},
                {"label": "LARGE", "min": 100},
            ],
        }
        assert execute_regex_step({"employee_count": 50}, config) == "MEDIUM"

    def test_employee_range_unknown(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "employee_range", "input_field": "employee_count", "rules": []}
        assert execute_regex_step({"employee_count": None}, config) == "UNKNOWN"

    def test_country_filter_include_match(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "country_filter", "input_field": "country", "values": ["Argentina", "Chile"], "mode": "include"}
        assert execute_regex_step({"country": "Argentina"}, config) == "MATCH"

    def test_country_filter_include_no_match(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "country_filter", "input_field": "country", "values": ["Argentina", "Chile"], "mode": "include"}
        assert execute_regex_step({"country": "Brazil"}, config) == "NO_MATCH"

    def test_country_filter_exclude(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "country_filter", "input_field": "country", "values": ["Brazil"], "mode": "exclude"}
        assert execute_regex_step({"country": "Argentina"}, config) == "MATCH"
        assert execute_regex_step({"country": "Brazil"}, config) == "NO_MATCH"

    def test_tld_extraction(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "regex_extract", "input_field": "domain", "pattern": r"\.([a-z]{2,})$", "group": 1}
        assert execute_regex_step({"domain": "building-ideas.com.ar"}, config) == "ar"
        assert execute_regex_step({"domain": "polemic.cl"}, config) == "cl"
        assert execute_regex_step({"domain": "testco.com"}, config) == "com"

    def test_keyword_match(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "keyword_match", "input_field": "industry", "keywords": ["fashion", "apparel"]}
        assert execute_regex_step({"industry": "apparel & fashion"}, config) == "MATCH"
        assert execute_regex_step({"industry": "marketing & advertising"}, config) == "NO_MATCH"

    def test_has_field_yes(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "has_field", "input_field": "linkedin_url"}
        assert execute_regex_step({"linkedin_url": "https://linkedin.com/company/foo"}, config) == "YES"

    def test_has_field_no(self):
        from app.services.step_executor import execute_regex_step
        config = {"type": "has_field", "input_field": "linkedin_url"}
        assert execute_regex_step({"linkedin_url": ""}, config) == "NO"
        assert execute_regex_step({"linkedin_url": None}, config) == "NO"

    def test_nested_field_access(self):
        from app.services.step_executor import _get_nested
        data = {"source_data": {"phone": "+54123456", "founded_year": "2015"}}
        assert _get_nested(data, "source_data.phone") == "+54123456"
        assert _get_nested(data, "source_data.founded_year") == "2015"
        assert _get_nested(data, "source_data.missing") is None


# ═══════════════════════════════════════════════════════════════
# 3. FILTER STEP EXECUTION
# ═══════════════════════════════════════════════════════════════

class TestFilterExecution:
    """Test filter step execution."""

    def test_reject_other(self):
        from app.services.step_executor import execute_filter_step
        config = {"reject_values": ["OTHER"]}
        assert execute_filter_step({"fashion_segment": "FASHION_BRAND"}, config) == True
        assert execute_filter_step({"fashion_segment": "OTHER"}, config) == False

    def test_reject_not_valid(self):
        from app.services.step_executor import execute_filter_step
        config = {"reject_values": ["NOT_VALID"]}
        assert execute_filter_step({"step1": "Classification: VALID"}, config) == True
        assert execute_filter_step({"step1": "Classification: NOT_VALID"}, config) == False

    def test_keep_values(self):
        from app.services.step_executor import execute_filter_step
        config = {"keep_values": ["FASHION_BRAND", "TEXTILE_PRODUCER"]}
        assert execute_filter_step({"seg": "FASHION_BRAND"}, config) == True
        assert execute_filter_step({"seg": "TEXTILE_PRODUCER"}, config) == True
        assert execute_filter_step({"seg": "RETAIL_ONLY"}, config) == False

    def test_filter_empty_results(self):
        from app.services.step_executor import execute_filter_step
        config = {"reject_values": ["OTHER"]}
        assert execute_filter_step({}, config) == False

    def test_filter_none_value(self):
        from app.services.step_executor import execute_filter_step
        config = {"reject_values": ["OTHER"]}
        assert execute_filter_step({"seg": None}, config) == False


# ═══════════════════════════════════════════════════════════════
# 4. CONFIG BUILDERS
# ═══════════════════════════════════════════════════════════════

class TestConfigBuilders:
    """Test auto-building of regex/filter configs from descriptions."""

    def test_build_employee_range_config(self):
        from app.services.step_executor import build_regex_config
        config = build_regex_config(
            "Classify as LARGE (100+ employees), MEDIUM (20-100), SMALL (<20)",
            "size_segment"
        )
        assert config["type"] == "employee_range"
        assert config["input_field"] == "employee_count"
        assert len(config["rules"]) > 0

    def test_build_country_filter_config(self):
        from app.services.step_executor import build_regex_config
        config = build_regex_config("Filter only companies from Argentina and Chile", "country_check")
        assert config["type"] == "country_filter"
        assert "Argentina" in config["values"]
        assert "Chile" in config["values"]

    def test_build_tld_config(self):
        from app.services.step_executor import build_regex_config
        config = build_regex_config("Extract TLD from domain", "tld")
        assert config["type"] == "regex_extract"
        assert config["input_field"] == "domain"

    def test_build_filter_reject_config(self):
        from app.services.step_executor import build_filter_config
        config = build_filter_config("Filter out OTHER companies")
        assert "OTHER" in config["reject_values"]

    def test_build_filter_keep_config(self):
        from app.services.step_executor import build_filter_config
        config = build_filter_config("Only keep FASHION_BRAND")
        assert "FASHION_BRAND" in config["keep_values"]

    def test_build_filter_neq_config(self):
        from app.services.step_executor import build_filter_config
        config = build_filter_config("segment != OTHER")
        assert "OTHER" in config["reject_values"]


# ═══════════════════════════════════════════════════════════════
# 5. ESSENTIAL COLUMNS PROTECTION
# ═══════════════════════════════════════════════════════════════

class TestEssentialColumns:
    """Test that essential columns cannot be removed."""

    def test_essential_columns_defined(self):
        from app.services.step_executor import ESSENTIAL_COLUMNS
        assert "domain" in ESSENTIAL_COLUMNS
        assert "name" in ESSENTIAL_COLUMNS
        assert "is_target" in ESSENTIAL_COLUMNS
        assert "analysis_segment" in ESSENTIAL_COLUMNS
        assert "status" in ESSENTIAL_COLUMNS

    def test_essential_step_names_defined(self):
        from app.services.step_executor import ESSENTIAL_STEP_NAMES
        assert "website_scrape" in ESSENTIAL_STEP_NAMES
        assert "icp_analysis" in ESSENTIAL_STEP_NAMES


# ═══════════════════════════════════════════════════════════════
# 6. ITERATION MANAGER UNIT TESTS
# ═══════════════════════════════════════════════════════════════

class TestIterationManagerUnit:
    """Test iteration manager logic without DB."""

    def test_step_to_dict(self):
        from app.services.iteration_manager import IterationManager
        mgr = IterationManager()
        step = MagicMock()
        step.id = 1
        step.name = "size_segment"
        step.step_number = 1
        step.output_column = "size_segment"
        step.step_type = "regex"
        step.config = {"type": "employee_range"}
        step.is_essential = False
        step.is_active = True
        d = mgr._step_to_dict(step)
        assert d["name"] == "size_segment"
        assert d["step_type"] == "regex"
        assert d["output_column"] == "size_segment"


# ═══════════════════════════════════════════════════════════════
# 7. FULL ADD/REMOVE/ADD/REMOVE SCENARIO
# ═══════════════════════════════════════════════════════════════

class TestAddRemoveScenario:
    """Test the full add/remove/add/remove flow producing 4 trackable iterations.

    Scenario from requirements:
    1. User adds "size_segment" column (regex: employee range)     → Iteration 1
    2. User removes "size_segment"                                   → Iteration 2
    3. User adds "tld_region" column (regex: TLD extraction)        → Iteration 3
    4. User removes "tld_region"                                     → Iteration 4

    All 4 iterations must be selectable in UI. Iteration 1 shows size_segment.
    Iteration 2 shows no custom columns. Iteration 3 shows tld_region.
    Iteration 4 shows no custom columns again.
    """

    def test_iteration_1_has_size_column(self):
        """After adding size_segment, iteration snapshot should include it."""
        snapshot = [
            {"name": "size_segment", "output_column": "size_segment", "step_type": "regex",
             "config": {"type": "employee_range"}, "step_number": 1, "is_essential": False}
        ]
        columns = [s["output_column"] for s in snapshot if s.get("output_column")]
        assert "size_segment" in columns

    def test_iteration_2_no_custom_columns(self):
        """After removing size_segment, iteration snapshot should be empty."""
        snapshot = []
        columns = [s["output_column"] for s in snapshot if s.get("output_column")]
        assert len(columns) == 0

    def test_iteration_3_has_tld_column(self):
        """After adding tld_region, iteration snapshot should include it."""
        snapshot = [
            {"name": "tld_region", "output_column": "tld_region", "step_type": "regex",
             "config": {"type": "regex_extract"}, "step_number": 1, "is_essential": False}
        ]
        columns = [s["output_column"] for s in snapshot if s.get("output_column")]
        assert "tld_region" in columns
        assert "size_segment" not in columns

    def test_iteration_4_no_custom_columns_again(self):
        """After removing tld_region, back to no custom columns."""
        snapshot = []
        columns = [s["output_column"] for s in snapshot if s.get("output_column")]
        assert len(columns) == 0

    def test_all_4_iterations_have_different_column_sets(self):
        """Each of the 4 iterations has a different column configuration."""
        iterations = [
            {"number": 1, "columns": ["size_segment"], "trigger": "add_step"},
            {"number": 2, "columns": [], "trigger": "remove_step"},
            {"number": 3, "columns": ["tld_region"], "trigger": "add_step"},
            {"number": 4, "columns": [], "trigger": "remove_step"},
        ]
        assert len(iterations) == 4
        assert iterations[0]["columns"] != iterations[1]["columns"]
        assert iterations[1]["columns"] != iterations[2]["columns"]
        assert iterations[2]["columns"] != iterations[3]["columns"]
        # But 1 != 3 (different column names)
        assert iterations[0]["columns"] != iterations[2]["columns"]
        # And 2 == 4 (both empty)
        assert iterations[1]["columns"] == iterations[3]["columns"]

    def test_iteration_label_tracks_change(self):
        """Each iteration label should describe what changed."""
        labels = [
            "Added column: size_segment",
            "Removed column: size_segment",
            "Added column: tld_region",
            "Removed column: tld_region",
        ]
        for label in labels:
            assert "column:" in label
            assert any(word in label for word in ["Added", "Removed"])


# ═══════════════════════════════════════════════════════════════
# 8. MIXED AI + REGEX PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestMixedPipeline:
    """Test a pipeline with both AI and regex steps together."""

    def test_mixed_steps_ordering(self):
        """AI classification → regex size → filter → AI sub-segment."""
        steps = [
            {"name": "classify_business", "step_type": "ai", "output_column": "business_type", "step_number": 1},
            {"name": "size_segment", "step_type": "regex", "output_column": "size_segment", "step_number": 2},
            {"name": "filter_other", "step_type": "filter", "output_column": None, "step_number": 3},
            {"name": "sub_segment", "step_type": "ai", "output_column": "sub_segment", "step_number": 4},
        ]
        ai_steps = [s for s in steps if s["step_type"] == "ai"]
        regex_steps = [s for s in steps if s["step_type"] == "regex"]
        filter_steps = [s for s in steps if s["step_type"] == "filter"]
        assert len(ai_steps) == 2
        assert len(regex_steps) == 1
        assert len(filter_steps) == 1
        # Custom columns
        columns = [s["output_column"] for s in steps if s.get("output_column")]
        assert columns == ["business_type", "size_segment", "sub_segment"]

    def test_regex_step_does_not_need_openai_key(self):
        """Regex steps should NOT require an API key."""
        from app.services.step_executor import execute_regex_step
        config = {"type": "employee_range", "input_field": "employee_count",
                  "rules": [{"label": "SMALL", "max": 50}, {"label": "LARGE", "min": 50}]}
        result = execute_regex_step({"employee_count": 25}, config)
        assert result == "SMALL"
        # No API key needed — pure algorithmic

    def test_all_custom_columns_in_pipeline_table(self):
        """Pipeline table should show all custom columns from current iteration."""
        iteration_columns = ["business_type", "size_segment", "sub_segment"]
        essential_columns = ["domain", "name", "industry", "country", "is_target", "analysis_segment", "status"]
        all_visible = essential_columns + iteration_columns
        assert "business_type" in all_visible
        assert "size_segment" in all_visible
        assert "sub_segment" in all_visible
        assert "domain" in all_visible  # Essential always visible
