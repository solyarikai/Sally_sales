"""
Tests for Data Search Service.

Covers:
- Query generation via OpenAI (mocked)
- Yandex search execution (mocked)
- Domain qualification via Crona + OpenAI (mocked)
- Full pipeline and chat search
- Usage logging
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.data_search_service import DataSearchService


# ═══════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════

@pytest.fixture
def service():
    return DataSearchService()


@pytest.fixture
def mock_openai_generate():
    """Mock openai_service.enrich_single_row for query generation."""
    response = {
        "queries": [
            "SaaS companies Berlin",
            "tech startups Germany B2B",
            "cloud software providers Munich",
        ],
        "qualification_prompt": "Determine if this company is a SaaS company in Germany.",
        "segment_summary": "SaaS companies in Germany",
    }
    result = {
        "success": True,
        "result": json.dumps(response),
        "tokens_used": 350,
    }
    with patch(
        "app.services.data_search_service.openai_service.enrich_single_row",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


@pytest.fixture
def mock_yandex_search():
    """Mock search_service._yandex_search_single_query."""
    async def _side_effect(query, max_pages):
        # Return different domains per query to simulate real behavior
        base = query.replace(" ", "").lower()[:6]
        return {f"{base}1.com", f"{base}2.com", f"shared-domain.com"}

    with patch(
        "app.services.data_search_service.search_service._yandex_search_single_query",
        new_callable=AsyncMock,
        side_effect=_side_effect,
    ) as mock:
        yield mock


@pytest.fixture
def mock_usage_logger():
    """Mock usage_logger to avoid file I/O in tests."""
    with patch("app.services.data_search_service.usage_logger") as mock:
        mock.log_yandex_request = MagicMock()
        mock.log_openai_request = MagicMock()
        mock.log_session_summary = MagicMock()
        yield mock


# ═══════════════════════════════════════════════════════
# Query Generation Tests
# ═══════════════════════════════════════════════════════

class TestGenerateSearchQueries:
    @pytest.mark.asyncio
    async def test_generates_queries_from_segment(
        self, service, mock_openai_generate, mock_usage_logger
    ):
        result = await service.generate_search_queries(
            "SaaS companies in Germany", count=3
        )
        assert "queries" in result
        assert len(result["queries"]) == 3
        assert "qualification_prompt" in result
        assert "segment_summary" in result

    @pytest.mark.asyncio
    async def test_logs_openai_usage(
        self, service, mock_openai_generate, mock_usage_logger
    ):
        await service.generate_search_queries("SaaS in Germany", count=3)
        mock_usage_logger.log_openai_request.assert_called_once()
        call_args = mock_usage_logger.log_openai_request.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["tokens_used"] == 350

    @pytest.mark.asyncio
    async def test_fallback_on_openai_failure(self, service, mock_usage_logger):
        with patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "API error", "tokens_used": 0},
        ):
            result = await service.generate_search_queries("test segment")
        # Should fallback to using the description as the query
        assert result["queries"] == ["test segment"]

    @pytest.mark.asyncio
    async def test_handles_malformed_json(self, service, mock_usage_logger):
        with patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "result": "not valid json at all",
                "tokens_used": 50,
            },
        ):
            result = await service.generate_search_queries("test segment")
        # Should fallback
        assert result["queries"] == ["test segment"]

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self, service, mock_usage_logger):
        response = json.dumps({
            "queries": ["query one"],
            "qualification_prompt": "test prompt",
            "segment_summary": "test",
        })
        with patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "result": f"```json\n{response}\n```",
                "tokens_used": 100,
            },
        ):
            result = await service.generate_search_queries("test")
        assert result["queries"] == ["query one"]


# ═══════════════════════════════════════════════════════
# Yandex Search Tests
# ═══════════════════════════════════════════════════════

class TestSearchYandex:
    @pytest.mark.asyncio
    async def test_returns_unique_domains(
        self, service, mock_yandex_search, mock_usage_logger
    ):
        result = await service.search_yandex(
            queries=["query one", "query two"], max_pages=1
        )
        assert "total_domains" in result
        assert "domains" in result
        # Should have unique domains from both queries plus shared
        assert result["total_domains"] > 0
        assert "shared-domain.com" in result["domains"]

    @pytest.mark.asyncio
    async def test_query_results_detail(
        self, service, mock_yandex_search, mock_usage_logger
    ):
        result = await service.search_yandex(
            queries=["test query"], max_pages=2
        )
        assert len(result["query_results"]) == 1
        qr = result["query_results"][0]
        assert qr["query"] == "test query"
        assert qr["status"] == "done"
        assert qr["domains_found"] > 0

    @pytest.mark.asyncio
    async def test_logs_yandex_usage(
        self, service, mock_yandex_search, mock_usage_logger
    ):
        await service.search_yandex(queries=["q1", "q2"], max_pages=5)
        assert mock_usage_logger.log_yandex_request.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_yandex_failure(self, service, mock_usage_logger):
        with patch(
            "app.services.data_search_service.search_service._yandex_search_single_query",
            new_callable=AsyncMock,
            side_effect=Exception("Yandex API error"),
        ):
            result = await service.search_yandex(queries=["bad query"])
        assert result["total_domains"] == 0
        assert result["query_results"][0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self, service, mock_usage_logger):
        with patch("app.services.data_search_service.settings") as mock_settings:
            mock_settings.YANDEX_SEARCH_API_KEY = None
            mock_settings.YANDEX_SEARCH_FOLDER_ID = "folder"
            with pytest.raises(ValueError, match="YANDEX_SEARCH_API_KEY"):
                await service.search_yandex(queries=["test"])


# ═══════════════════════════════════════════════════════
# Qualification Tests
# ═══════════════════════════════════════════════════════

class TestQualifyDomains:
    @pytest.mark.asyncio
    async def test_qualifies_with_crona_and_openai(self, service, mock_usage_logger):
        qualify_response = json.dumps({
            "qualified": True,
            "confidence": 0.9,
            "reason": "Matches criteria",
            "company_name": "TestCo",
            "company_description": "A test company",
        })
        with patch(
            "app.services.data_search_service.crona_service.is_configured",
            return_value=True,
        ), patch(
            "app.services.data_search_service.crona_service.scrape_websites_and_wait",
            new_callable=AsyncMock,
            return_value={
                "results": {
                    "data": [
                        ["website", "scraped_content"],
                        ["https://example.com", "We are a SaaS company."],
                    ]
                }
            },
        ), patch(
            "app.services.data_search_service.crona_service.parse_results_to_dict",
            return_value={"example.com": "We are a SaaS company."},
        ), patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "result": qualify_response,
                "tokens_used": 200,
            },
        ):
            result = await service.qualify_domains(
                ["example.com"], "Check if SaaS"
            )
        assert result["total_qualified"] == 1
        assert result["qualified"][0]["domain"] == "example.com"
        assert result["qualified"][0]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_skips_scraping_when_crona_not_configured(
        self, service, mock_usage_logger
    ):
        with patch(
            "app.services.data_search_service.crona_service.is_configured",
            return_value=False,
        ), patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
        ) as mock_openai:
            # Since no content is scraped, qualification returns no-content error
            result = await service.qualify_domains(
                ["noscrap.com"], "Check"
            )
        # Should be in errors (no content scraped)
        assert result["total_errors"] == 1
        # OpenAI should NOT be called since there's no content
        mock_openai.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_limit(self, service, mock_usage_logger):
        domains = [f"domain{i}.com" for i in range(100)]
        with patch(
            "app.services.data_search_service.crona_service.is_configured",
            return_value=False,
        ):
            result = await service.qualify_domains(
                domains, "Check", limit=5
            )
        assert result["total_checked"] == 5

    @pytest.mark.asyncio
    async def test_not_qualified_domains(self, service, mock_usage_logger):
        qualify_response = json.dumps({
            "qualified": False,
            "confidence": 0.2,
            "reason": "Not matching",
            "company_name": "OtherCo",
            "company_description": "A different company",
        })
        with patch(
            "app.services.data_search_service.crona_service.is_configured",
            return_value=True,
        ), patch(
            "app.services.data_search_service.crona_service.scrape_websites_and_wait",
            new_callable=AsyncMock,
            return_value={"results": {}},
        ), patch(
            "app.services.data_search_service.crona_service.parse_results_to_dict",
            return_value={"bad.com": "Unrelated content"},
        ), patch(
            "app.services.data_search_service.openai_service.enrich_single_row",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "result": qualify_response,
                "tokens_used": 150,
            },
        ):
            result = await service.qualify_domains(["bad.com"], "Check if SaaS")
        assert result["total_not_qualified"] == 1


# ═══════════════════════════════════════════════════════
# Full Pipeline Tests
# ═══════════════════════════════════════════════════════

class TestSearchSegment:
    @pytest.mark.asyncio
    async def test_full_pipeline_no_qualify(
        self, service, mock_openai_generate, mock_yandex_search, mock_usage_logger
    ):
        result = await service.search_segment(
            "SaaS companies in Germany",
            query_count=3,
            max_pages=1,
            qualify=False,
        )
        assert result["segment_description"] == "SaaS companies in Germany"
        assert len(result["generated_queries"]) == 3
        assert result["search_results"]["total_domains"] > 0
        assert result["qualification"] is None
        mock_usage_logger.log_session_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_pipeline_with_qualify(
        self, service, mock_openai_generate, mock_yandex_search, mock_usage_logger
    ):
        qualify_response = json.dumps({
            "qualified": True,
            "confidence": 0.8,
            "reason": "Match",
            "company_name": "Co",
            "company_description": "Desc",
        })
        with patch(
            "app.services.data_search_service.crona_service.is_configured",
            return_value=True,
        ), patch(
            "app.services.data_search_service.crona_service.scrape_websites_and_wait",
            new_callable=AsyncMock,
            return_value={"results": {}},
        ), patch(
            "app.services.data_search_service.crona_service.parse_results_to_dict",
            return_value={},
        ):
            result = await service.search_segment(
                "test segment", qualify=True, qualify_limit=5
            )
        assert result["qualification"] is not None


# ═══════════════════════════════════════════════════════
# Chat Search Tests
# ═══════════════════════════════════════════════════════

class TestChatSearch:
    @pytest.mark.asyncio
    async def test_chat_returns_expected_fields(
        self, service, mock_openai_generate, mock_yandex_search, mock_usage_logger
    ):
        result = await service.chat_search("Find SaaS companies in Germany")
        assert "response" in result
        assert "queries_generated" in result
        assert "qualification_prompt" in result
        assert "companies" in result
        assert "total" in result
        assert isinstance(result["companies"], list)

    @pytest.mark.asyncio
    async def test_chat_limits_companies_to_100(
        self, service, mock_openai_generate, mock_usage_logger
    ):
        # Return 150 domains
        async def _many_domains(query, max_pages):
            return {f"domain{i}.com" for i in range(150)}

        with patch(
            "app.services.data_search_service.search_service._yandex_search_single_query",
            new_callable=AsyncMock,
            side_effect=_many_domains,
        ):
            result = await service.chat_search("test")
        assert result["total"] <= 100

    @pytest.mark.asyncio
    async def test_chat_logs_session_summary(
        self, service, mock_openai_generate, mock_yandex_search, mock_usage_logger
    ):
        await service.chat_search("test query")
        mock_usage_logger.log_session_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_response_mentions_domain_count(
        self, service, mock_openai_generate, mock_yandex_search, mock_usage_logger
    ):
        result = await service.chat_search("test")
        # Response should mention the number of domains found
        assert "found" in result["response"].lower() or "company" in result["response"].lower()
