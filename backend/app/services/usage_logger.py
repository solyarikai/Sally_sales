"""
API Usage Logger — tracks Yandex Search API and OpenAI API usage.

Logs every request to yandex.md in markdown table format for easy review.
Tracks:
- Yandex: request count, queries, domains found, pages scanned
- OpenAI: request count, model, tokens used (prompt + completion), estimated cost
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Approximate pricing per 1k tokens (as of 2025)
OPENAI_PRICING = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "o1": {"input": 0.015, "output": 0.06},
    "o1-mini": {"input": 0.003, "output": 0.012},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
}

# Yandex Search API pricing
YANDEX_PRICE_PER_1K_REQUESTS = 0.25


class UsageLogger:
    """Logs API usage to a markdown file."""

    def __init__(self, log_path: Optional[str] = None):
        if log_path:
            self.log_path = Path(log_path)
        else:
            # Default: yandex.md in the backend root
            self.log_path = Path(__file__).parent.parent.parent / "yandex.md"

        # Cumulative session counters
        self._yandex_requests = 0
        self._yandex_domains_found = 0
        self._openai_requests = 0
        self._openai_total_tokens = 0
        self._openai_estimated_cost = 0.0

        self._ensure_file()

    def _ensure_file(self):
        """Create the log file with headers if it doesn't exist."""
        if not self.log_path.exists():
            header = (
                "# API Usage Log\n\n"
                "Tracks Yandex Search API and OpenAI API usage for the Data Search pipeline.\n\n"
                "---\n\n"
                "## Yandex Search API\n\n"
                "| Timestamp | Query | Pages | Domains Found | Status | Cost Est. |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "\n"
                "## OpenAI API\n\n"
                "| Timestamp | Operation | Model | Tokens Used | Cost Est. |\n"
                "| --- | --- | --- | --- | --- |\n"
                "\n"
                "## Session Summaries\n\n"
                "| Timestamp | Yandex Reqs | Yandex Domains | OpenAI Reqs | OpenAI Tokens | OpenAI Cost | Yandex Cost | Total Cost |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            )
            self.log_path.write_text(header)

    def _read_sections(self) -> dict:
        """Read the file and split into sections."""
        content = self.log_path.read_text()
        sections = {
            "header": "",
            "yandex": "",
            "openai": "",
            "summary": "",
        }

        # Find section markers
        yandex_marker = "## Yandex Search API"
        openai_marker = "## OpenAI API"
        summary_marker = "## Session Summaries"

        yandex_idx = content.find(yandex_marker)
        openai_idx = content.find(openai_marker)
        summary_idx = content.find(summary_marker)

        if yandex_idx >= 0:
            sections["header"] = content[:yandex_idx]
        if yandex_idx >= 0 and openai_idx >= 0:
            sections["yandex"] = content[yandex_idx:openai_idx]
        if openai_idx >= 0 and summary_idx >= 0:
            sections["openai"] = content[openai_idx:summary_idx]
        if summary_idx >= 0:
            sections["summary"] = content[summary_idx:]

        return sections

    def _append_to_section(self, section_name: str, row: str):
        """Append a row to a specific section's table."""
        try:
            sections = self._read_sections()
            section = sections.get(section_name, "")
            if not section:
                return

            # Find the last line of the table (before any blank line after table)
            lines = section.rstrip().split("\n")
            lines.append(row)
            sections[section_name] = "\n".join(lines) + "\n\n"

            # Reassemble
            content = (
                sections["header"]
                + sections["yandex"]
                + sections["openai"]
                + sections["summary"]
            )
            self.log_path.write_text(content)
        except Exception as e:
            logger.error(f"Failed to write usage log: {e}")

    def log_yandex_request(
        self,
        query: str,
        pages_scanned: int,
        domains_found: int,
        status: str = "ok",
    ):
        """Log a Yandex Search API request."""
        self._yandex_requests += 1
        self._yandex_domains_found += domains_found
        cost = pages_scanned * YANDEX_PRICE_PER_1K_REQUESTS / 1000
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        # Escape pipe chars in query
        safe_query = query.replace("|", "\\|")[:80]
        row = f"| {ts} | {safe_query} | {pages_scanned} | {domains_found} | {status} | ${cost:.4f} |"
        self._append_to_section("yandex", row)

    def log_openai_request(
        self,
        operation: str,
        model: str,
        tokens_used: int,
    ):
        """Log an OpenAI API request."""
        self._openai_requests += 1
        self._openai_total_tokens += tokens_used
        pricing = OPENAI_PRICING.get(model, OPENAI_PRICING["gpt-4o-mini"])
        # Rough estimate: assume 50/50 input/output split
        cost = (tokens_used / 1000) * (pricing["input"] + pricing["output"]) / 2
        self._openai_estimated_cost += cost
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        safe_op = operation.replace("|", "\\|")[:60]
        row = f"| {ts} | {safe_op} | {model} | {tokens_used} | ${cost:.4f} |"
        self._append_to_section("openai", row)

    def log_session_summary(self):
        """Write a cumulative session summary row."""
        yandex_cost = self._yandex_requests * YANDEX_PRICE_PER_1K_REQUESTS / 1000
        total_cost = yandex_cost + self._openai_estimated_cost
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = (
            f"| {ts} | {self._yandex_requests} | {self._yandex_domains_found} "
            f"| {self._openai_requests} | {self._openai_total_tokens} "
            f"| ${self._openai_estimated_cost:.4f} | ${yandex_cost:.4f} "
            f"| ${total_cost:.4f} |"
        )
        self._append_to_section("summary", row)

    def get_stats(self) -> dict:
        """Return current session stats."""
        yandex_cost = self._yandex_requests * YANDEX_PRICE_PER_1K_REQUESTS / 1000
        return {
            "yandex_requests": self._yandex_requests,
            "yandex_domains_found": self._yandex_domains_found,
            "yandex_cost": round(yandex_cost, 4),
            "openai_requests": self._openai_requests,
            "openai_total_tokens": self._openai_total_tokens,
            "openai_estimated_cost": round(self._openai_estimated_cost, 4),
            "total_estimated_cost": round(yandex_cost + self._openai_estimated_cost, 4),
        }


# Module-level singleton
usage_logger = UsageLogger()
