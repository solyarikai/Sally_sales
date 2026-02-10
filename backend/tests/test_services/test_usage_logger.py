"""
Tests for Usage Logger — tracks Yandex and OpenAI API usage to yandex.md.
"""
import os
import pytest
import tempfile
from pathlib import Path

from app.services.usage_logger import UsageLogger, YANDEX_PRICE_PER_1K_REQUESTS


@pytest.fixture
def tmp_log_file():
    """Create a temporary file for the usage log."""
    fd, path = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    os.unlink(path)  # Let UsageLogger create it
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def logger(tmp_log_file):
    """Create a UsageLogger with a temporary log file."""
    return UsageLogger(log_path=tmp_log_file)


class TestUsageLoggerInit:
    def test_creates_log_file(self, tmp_log_file):
        logger = UsageLogger(log_path=tmp_log_file)
        assert Path(tmp_log_file).exists()
        content = Path(tmp_log_file).read_text()
        assert "# API Usage Log" in content
        assert "## Yandex Search API" in content
        assert "## OpenAI API" in content
        assert "## Session Summaries" in content

    def test_does_not_overwrite_existing(self, tmp_log_file):
        # Create first logger
        logger1 = UsageLogger(log_path=tmp_log_file)
        logger1.log_yandex_request("test query", 1, 5)
        # Create second logger with same path
        logger2 = UsageLogger(log_path=tmp_log_file)
        content = Path(tmp_log_file).read_text()
        assert "test query" in content

    def test_initial_stats_are_zero(self, logger):
        stats = logger.get_stats()
        assert stats["yandex_requests"] == 0
        assert stats["openai_requests"] == 0
        assert stats["total_estimated_cost"] == 0


class TestYandexLogging:
    def test_logs_yandex_request(self, logger, tmp_log_file):
        logger.log_yandex_request("SaaS Berlin", 5, 12)
        content = Path(tmp_log_file).read_text()
        assert "SaaS Berlin" in content
        assert "12" in content

    def test_increments_yandex_counters(self, logger):
        logger.log_yandex_request("q1", 3, 10)
        logger.log_yandex_request("q2", 5, 20)
        stats = logger.get_stats()
        assert stats["yandex_requests"] == 2
        assert stats["yandex_domains_found"] == 30

    def test_escapes_pipe_in_query(self, logger, tmp_log_file):
        logger.log_yandex_request("query|with|pipes", 1, 1)
        content = Path(tmp_log_file).read_text()
        assert "query\\|with\\|pipes" in content

    def test_truncates_long_queries(self, logger, tmp_log_file):
        long_query = "a" * 200
        logger.log_yandex_request(long_query, 1, 1)
        content = Path(tmp_log_file).read_text()
        # Should be truncated to 80 chars
        assert "a" * 80 in content
        assert "a" * 81 not in content.split("|")[2]  # The query cell


class TestOpenAILogging:
    def test_logs_openai_request(self, logger, tmp_log_file):
        logger.log_openai_request("generate_queries", "gpt-4o-mini", 350)
        content = Path(tmp_log_file).read_text()
        assert "generate_queries" in content
        assert "gpt-4o-mini" in content
        assert "350" in content

    def test_increments_openai_counters(self, logger):
        logger.log_openai_request("op1", "gpt-4o-mini", 100)
        logger.log_openai_request("op2", "gpt-4o-mini", 200)
        stats = logger.get_stats()
        assert stats["openai_requests"] == 2
        assert stats["openai_total_tokens"] == 300

    def test_estimates_cost(self, logger):
        logger.log_openai_request("test", "gpt-4o-mini", 1000)
        stats = logger.get_stats()
        assert stats["openai_estimated_cost"] > 0


class TestSessionSummary:
    def test_writes_session_summary(self, logger, tmp_log_file):
        logger.log_yandex_request("q1", 5, 10)
        logger.log_openai_request("op1", "gpt-4o-mini", 500)
        logger.log_session_summary()
        content = Path(tmp_log_file).read_text()
        # Summary section should have a row with stats
        summary_section = content[content.find("## Session Summaries"):]
        assert "1" in summary_section  # yandex requests
        assert "10" in summary_section  # domains found


class TestGetStats:
    def test_returns_all_fields(self, logger):
        stats = logger.get_stats()
        assert "yandex_requests" in stats
        assert "yandex_domains_found" in stats
        assert "yandex_cost" in stats
        assert "openai_requests" in stats
        assert "openai_total_tokens" in stats
        assert "openai_estimated_cost" in stats
        assert "total_estimated_cost" in stats

    def test_cost_calculation(self, logger):
        # Log some requests
        logger.log_yandex_request("q", 1, 1)
        logger.log_openai_request("op", "gpt-4o-mini", 100)
        stats = logger.get_stats()
        assert stats["total_estimated_cost"] == round(
            stats["yandex_cost"] + stats["openai_estimated_cost"], 4
        )
