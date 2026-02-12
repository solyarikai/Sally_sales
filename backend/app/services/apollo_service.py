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

    # Apollo rate limits: 50 calls/min, 200 calls/hour
    # Use the stricter hourly limit: 200/hour = ~3.3/min = 18s between calls
    # But burst up to 50/min is OK, so use 1.5s between calls + track hourly
    RATE_LIMIT_INTERVAL = 1.5  # seconds between calls
    HOURLY_LIMIT = 200
    HOURLY_WINDOW = 3600  # seconds

    def __init__(self):
        self.base_url = settings.APOLLO_API_URL
        self.credits_used: int = 0
        self._last_call_time: float = 0
        self._hourly_calls: List[float] = []  # timestamps of calls in current hour

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
        """Wait to stay under API rate limits (50/min and 200/hour)."""
        now = time.monotonic()

        # Per-call interval
        elapsed = now - self._last_call_time
        if elapsed < self.RATE_LIMIT_INTERVAL:
            await asyncio.sleep(self.RATE_LIMIT_INTERVAL - elapsed)

        # Hourly limit: prune old calls, wait if at limit
        self._hourly_calls = [t for t in self._hourly_calls if time.monotonic() - t < self.HOURLY_WINDOW]
        if len(self._hourly_calls) >= self.HOURLY_LIMIT - 5:  # leave 5 call buffer
            oldest = self._hourly_calls[0]
            wait_time = self.HOURLY_WINDOW - (time.monotonic() - oldest) + 5
            if wait_time > 0:
                logger.warning(f"Apollo hourly limit approaching ({len(self._hourly_calls)}/{self.HOURLY_LIMIT}), waiting {wait_time:.0f}s")
                await asyncio.sleep(wait_time)
                self._hourly_calls = [t for t in self._hourly_calls if time.monotonic() - t < self.HOURLY_WINDOW]

        self._last_call_time = time.monotonic()
        self._hourly_calls.append(self._last_call_time)

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
                    body = resp.text
                    # Detect hourly vs per-minute limit
                    if "per hour" in body or "times per hour" in body:
                        wait = 900  # 15 min for hourly limit
                        logger.warning(f"Apollo HOURLY limit hit, waiting {wait}s...")
                    else:
                        wait = 65
                        logger.warning(f"Apollo per-minute limit hit, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    self._last_call_time = time.monotonic()
                    async with httpx.AsyncClient(timeout=30) as retry_client:
                        if method == "POST":
                            resp = await retry_client.post(
                                f"{self.base_url}{endpoint}",
                                json=json_data,
                                headers=self._get_headers(),
                            )
                        else:
                            resp = await retry_client.get(
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
        Find and enrich people at a domain using 2 API calls:
        1. Search /mixed_people/api_search → find people names + titles
        2. Bulk enrich /people/bulk_match → get emails, LinkedIn, phones (up to 10 per call)

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
            "per_page": min(limit, 10),  # max 10 for bulk_match
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

        # Step 2: Bulk enrich all found people in one call (max 10)
        details = []
        for person in people:
            first_name = person.get("first_name")
            if not first_name:
                continue
            details.append({
                "first_name": first_name,
                "last_name": person.get("last_name") or "",
                "domain": domain,
            })

        if not details:
            return []

        bulk_data = await self._api_call("POST", "/people/bulk_match", {
            "details": details,
            "reveal_personal_emails": True,
        })
        if not bulk_data:
            return []

        matches = bulk_data.get("matches", [])
        results = []
        for match in matches:
            if not match:
                continue
            email = match.get("email")
            linkedin = match.get("linkedin_url")
            title = match.get("title")
            phone = None
            if match.get("phone_numbers"):
                phone = match["phone_numbers"][0].get("sanitized_number")

            results.append({
                "email": email,
                "first_name": match.get("first_name"),
                "last_name": match.get("last_name"),
                "job_title": title,
                "linkedin_url": linkedin,
                "is_verified": match.get("email_status") == "verified",
                "phone": phone,
                "raw_data": {
                    "id": match.get("id"),
                    "organization": match.get("organization", {}).get("name") if match.get("organization") else None,
                    "headline": match.get("headline"),
                    "city": match.get("city"),
                    "country": match.get("country"),
                    "email_status": match.get("email_status"),
                    "seniority": match.get("seniority"),
                    "personal_emails": match.get("personal_emails", []),
                },
            })

        logger.info(
            f"Apollo: {len(results)} enriched people for {domain} "
            f"(searched={len(people)}, bulk_matched={len(matches)}, credits_used={self.credits_used})"
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
