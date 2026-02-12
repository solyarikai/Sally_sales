"""
Apollo Service — People enrichment via Apollo.io API.

Two-step flow:
1. Search: /mixed_people/api_search → find people names + titles at a domain
2. Enrich: /people/enrich → get email, LinkedIn, phone for each person

The search endpoint does NOT return contact info (emails, LinkedIn, phones).
The enrich endpoint reveals them (uses email credits).
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ApolloService:
    """Service for interacting with Apollo.io API."""

    # Apollo rate limit: 50 API calls per minute
    RATE_LIMIT_PER_MINUTE = 50
    RATE_LIMIT_INTERVAL = 60.0 / RATE_LIMIT_PER_MINUTE + 0.1  # ~1.3s between calls

    def __init__(self):
        self.base_url = settings.APOLLO_API_URL
        self.credits_used: int = 0
        self._last_call_time: float = 0

    @property
    def api_key(self) -> Optional[str]:
        return settings.APOLLO_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    async def _rate_limit(self):
        """Wait to stay under API rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < self.RATE_LIMIT_INTERVAL:
            await asyncio.sleep(self.RATE_LIMIT_INTERVAL - elapsed)
        self._last_call_time = time.monotonic()

    async def _api_call(self, method: str, endpoint: str, json_data: dict = None) -> Optional[dict]:
        """Make a rate-limited API call with 429 retry."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "POST":
                    resp = await client.post(
                        f"{self.base_url}{endpoint}",
                        json=json_data,
                        headers=self._get_headers(),
                    )
                else:
                    resp = await client.get(
                        f"{self.base_url}{endpoint}",
                        headers=self._get_headers(),
                    )
                if resp.status_code == 429:
                    logger.warning(f"Apollo 429, waiting 65s...")
                    await asyncio.sleep(65)
                    self._last_call_time = time.monotonic()
                    if method == "POST":
                        resp = await client.post(
                            f"{self.base_url}{endpoint}",
                            json=json_data,
                            headers=self._get_headers(),
                        )
                    else:
                        resp = await client.get(
                            f"{self.base_url}{endpoint}",
                            headers=self._get_headers(),
                        )
                resp.raise_for_status()
                self.credits_used += 1
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo API {endpoint}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Apollo API {endpoint} failed: {e}")
            return None

    async def enrich_by_domain(
        self,
        domain: str,
        limit: int = 5,
        titles: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find and enrich people at a domain.

        Step 1: Search /mixed_people/api_search for people (names + titles)
        Step 2: Enrich each person via /people/enrich (get email, LinkedIn, phone)

        Returns list of people with:
        {email, first_name, last_name, job_title, linkedin_url, is_verified, phone, raw_data}
        """
        if not self.api_key:
            logger.warning("Apollo API key not configured")
            return []

        # Step 1: Search for people at domain
        payload: Dict[str, Any] = {
            "q_organization_domains": domain,
            "page": 1,
            "per_page": min(limit, 25),
        }
        if titles:
            payload["person_titles"] = titles

        search_data = await self._api_call("POST", "/mixed_people/api_search", payload)
        if not search_data:
            return []

        people = search_data.get("people", [])
        if not people:
            logger.info(f"Apollo search: 0 people at {domain} (credits_used={self.credits_used})")
            return []

        # Step 2: Enrich each person to get actual contact info
        results = []
        for person in people:
            first_name = person.get("first_name")
            last_name = person.get("last_name")
            if not first_name:
                continue

            enrich_payload = {
                "first_name": first_name,
                "last_name": last_name or "",
                "organization_domain": domain,
                "reveal_personal_emails": True,
            }

            enrich_data = await self._api_call("POST", "/people/enrich", enrich_payload)
            if not enrich_data:
                continue

            enriched = enrich_data.get("person", {})
            email = enriched.get("email")
            linkedin = enriched.get("linkedin_url")
            title = enriched.get("title") or person.get("title")
            phone = None
            if enriched.get("phone_numbers"):
                phone = enriched["phone_numbers"][0].get("sanitized_number")

            results.append({
                "email": email,
                "first_name": enriched.get("first_name") or first_name,
                "last_name": enriched.get("last_name") or last_name,
                "job_title": title,
                "linkedin_url": linkedin,
                "is_verified": enriched.get("email_status") == "verified",
                "phone": phone,
                "raw_data": {
                    "id": enriched.get("id"),
                    "organization": enriched.get("organization", {}).get("name") if enriched.get("organization") else None,
                    "headline": enriched.get("headline"),
                    "city": enriched.get("city"),
                    "state": enriched.get("state"),
                    "country": enriched.get("country"),
                    "email_status": enriched.get("email_status"),
                    "seniority": enriched.get("seniority"),
                    "departments": enriched.get("departments"),
                    "personal_emails": enriched.get("personal_emails", []),
                },
            })

        logger.info(
            f"Apollo found {len(results)} enriched people for {domain} "
            f"(searched={len(people)}, credits_used={self.credits_used})"
        )
        return results

    def reset_credits(self):
        """Reset the credit counter."""
        self.credits_used = 0

    async def test_connection(self) -> bool:
        """Test Apollo API connection."""
        if not self.api_key:
            return False
        data = await self._api_call("POST", "/mixed_people/api_search", {
            "q_organization_domains": "apollo.io",
            "per_page": 1,
        })
        return data is not None


# Module-level singleton
apollo_service = ApolloService()
