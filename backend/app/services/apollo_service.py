"""
Apollo Service — People enrichment via Apollo.io API.

Finds people by domain with verified emails, titles, LinkedIn profiles.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ApolloService:
    """Service for interacting with Apollo.io API."""

    def __init__(self):
        self.base_url = settings.APOLLO_API_URL
        self.credits_used: int = 0

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
                if not email:
                    continue

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
