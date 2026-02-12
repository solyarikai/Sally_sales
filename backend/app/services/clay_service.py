"""
Clay Service — Lightweight integration for pushing domains to Clay tables via webhook.

Clay does NOT have a REST company search API — it's webhook/table-based.
This service pushes domains to a Clay table for enrichment via webhook URL.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ClayService:
    """Push domains to Clay tables for enrichment via webhooks."""

    def __init__(self):
        self.api_key = settings.CLAY_API_KEY
        self.domains_pushed: int = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def push_domains_to_table(
        self,
        webhook_url: str,
        domains: List[str],
        extra_data: Optional[Dict[str, Any]] = None,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Push domains to a Clay table via webhook URL.

        Args:
            webhook_url: Clay table webhook URL (from Clay UI)
            domains: list of domain strings to push
            extra_data: optional extra fields to include per row
            batch_size: rows per webhook call

        Returns dict with {pushed, errors, total}.
        """
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
