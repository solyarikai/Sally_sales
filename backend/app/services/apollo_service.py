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

    # Apollo rate limits (paid plan danila@getsally.io):
    # /mixed_people/api_search: 200/min, 6000/hr, 50000/day
    # /people/bulk_match: 1000/min, unlimited hr/day
    # Keep 0.3s between calls to be safe
    RATE_LIMIT_INTERVAL = 0.3  # seconds between calls

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
        """Wait between API calls to stay under rate limits."""
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
                    wait = 30
                    logger.warning(f"Apollo 429 rate limit, waiting {wait}s...")
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
        # Use Apollo person ID — search returns obfuscated last names,
        # so name+domain matching fails. ID matching always works.
        details = []
        for person in people:
            person_id = person.get("id")
            if not person_id:
                continue
            details.append({"id": person_id})

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

    async def search_organizations(
        self,
        keyword_tags: List[str],
        locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """
        Search for organizations via Apollo /mixed_companies/search endpoint.

        Args:
            keyword_tags: keyword array e.g. ["family office", "wealth management"]
            locations: country names e.g. ["Russia", "Cyprus"]
            num_employees_ranges: size ranges e.g. ["1,10", "11,50"]
            page: page number (1-indexed)
            per_page: results per page (max 100)

        Returns raw API response with 'organizations' list + 'pagination' info,
        or None on failure.
        """
        if not self.api_key:
            logger.warning("Apollo API key not configured")
            return None

        payload: Dict[str, Any] = {
            "q_organization_keyword_tags": keyword_tags,
            "page": page,
            "per_page": min(per_page, 100),
        }
        if locations:
            payload["organization_locations"] = locations
        if num_employees_ranges:
            payload["organization_num_employees_ranges"] = num_employees_ranges

        return await self._api_call("POST", "/mixed_companies/search", payload)

    async def search_organizations_all_pages(
        self,
        keyword_tags: List[str],
        locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        max_pages: int = 50,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Paginated wrapper around search_organizations.
        Loops pages 1..N until total_pages reached or max_pages cap.

        Returns flat list of all organization dicts.
        Each page = 1 API credit.
        """
        all_orgs: List[Dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            data = await self.search_organizations(
                keyword_tags=keyword_tags,
                locations=locations,
                num_employees_ranges=num_employees_ranges,
                page=page,
                per_page=per_page,
            )
            if not data:
                break

            orgs = data.get("organizations", [])
            all_orgs.extend(orgs)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            logger.info(
                f"Apollo org search: page {page}/{total_pages}, "
                f"got {len(orgs)} orgs (total so far: {len(all_orgs)}), "
                f"keywords={keyword_tags}, locations={locations}"
            )

            if page >= total_pages:
                break

        return all_orgs

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
