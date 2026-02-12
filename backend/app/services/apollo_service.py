"""
Apollo Service — People enrichment via Apollo.io API.

Finds people by domain with verified emails, titles, LinkedIn profiles.
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

    # Apollo free tier: 50 API calls per minute
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

    async def enrich_by_domain(
        self,
        domain: str,
        limit: int = 5,
        titles: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search Apollo for people at a given domain.

        Returns list of people with:
        {email, first_name, last_name, job_title, linkedin_url, is_verified, raw_data}
        """
        if not self.api_key:
            logger.warning("Apollo API key not configured")
            return []

        payload: Dict[str, Any] = {
            "q_organization_domains": domain,
            "page": 1,
            "per_page": min(limit, 25),
        }

        # Optional title filter (e.g., ["CEO", "CTO", "VP"])
        if titles:
            payload["person_titles"] = titles

        try:
            # Rate limiting: wait to stay under 50 calls/min
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < self.RATE_LIMIT_INTERVAL:
                await asyncio.sleep(self.RATE_LIMIT_INTERVAL - elapsed)
            self._last_call_time = time.monotonic()

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/mixed_people/api_search",
                    json=payload,
                    headers=self._get_headers(),
                )
                resp.raise_for_status()
                data = resp.json()

            people = data.get("people", [])
            results = []

            for person in people:
                # Include all people — free tier may not reveal emails/LinkedIn
                # but names + titles are still useful for outreach
                email = person.get("email")
                results.append({
                    "email": email,
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "job_title": person.get("title"),
                    "linkedin_url": person.get("linkedin_url"),
                    "is_verified": person.get("email_status") == "verified",
                    "phone": (person.get("phone_numbers") or [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None,
                    "raw_data": {
                        "id": person.get("id"),
                        "organization": person.get("organization", {}).get("name"),
                        "headline": person.get("headline"),
                        "city": person.get("city"),
                        "state": person.get("state"),
                        "country": person.get("country"),
                        "email_status": person.get("email_status"),
                        "seniority": person.get("seniority"),
                        "departments": person.get("departments"),
                    },
                })

            self.credits_used += 1
            logger.info(f"Apollo found {len(results)} people for {domain} (credits_used={self.credits_used})")
            return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited — wait 65 seconds and retry once
                logger.warning(f"Apollo 429 for {domain}, waiting 65s and retrying...")
                await asyncio.sleep(65)
                self._last_call_time = time.monotonic()
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            f"{self.base_url}/mixed_people/api_search",
                            json=payload,
                            headers=self._get_headers(),
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    people = data.get("people", [])
                    results = []
                    for person in people:
                        email = person.get("email")
                        results.append({
                            "email": email,
                            "first_name": person.get("first_name"),
                            "last_name": person.get("last_name"),
                            "job_title": person.get("title"),
                            "linkedin_url": person.get("linkedin_url"),
                            "is_verified": person.get("email_status") == "verified",
                            "phone": (person.get("phone_numbers") or [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None,
                            "raw_data": {"id": person.get("id"), "organization": person.get("organization", {}).get("name")},
                        })
                    self.credits_used += 1
                    logger.info(f"Apollo retry found {len(results)} people for {domain} (credits_used={self.credits_used})")
                    return results
                except Exception as retry_err:
                    logger.error(f"Apollo retry also failed for {domain}: {retry_err}")
                    return []
            logger.error(f"Apollo API error for {domain}: {e.response.status_code} - {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"Apollo enrichment failed for {domain}: {e}")
            return []

    def reset_credits(self):
        """Reset the credit counter."""
        self.credits_used = 0

    async def test_connection(self) -> bool:
        """Test Apollo API connection."""
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/mixed_people/api_search",
                    json={
                        "q_organization_domains": "apollo.io",
                        "per_page": 1,
                    },
                    headers=self._get_headers(),
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Apollo connection test failed: {e}")
            return False


# Module-level singleton
apollo_service = ApolloService()
