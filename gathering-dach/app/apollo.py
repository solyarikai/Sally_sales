"""
Apollo API client — minimal, standalone, no external dependencies.
Only uses /mixed_people/api_search which is FREE (no email reveal).
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

RATE_LIMIT = 0.34  # ~3 req/sec
BASE_URL = "https://api.apollo.io/api/v1"


class ApolloClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._last_call = 0.0

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    async def _call(self, payload: dict, retries: int = 3) -> Optional[dict]:
        """POST /mixed_people/api_search — FREE, no credits."""
        for attempt in range(retries):
            # Rate limit
            elapsed = time.monotonic() - self._last_call
            if elapsed < RATE_LIMIT:
                await asyncio.sleep(RATE_LIMIT - elapsed)
            self._last_call = time.monotonic()

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{BASE_URL}/mixed_people/api_search",
                        json=payload,
                        headers=self._headers(),
                    )
                    if resp.status_code == 429:
                        wait = 30 * (attempt + 1)
                        logger.warning(f"Rate limited, waiting {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Apollo HTTP error: {e.response.status_code}")
                if attempt == retries - 1:
                    return None
            except Exception as e:
                logger.error(f"Apollo call failed: {e}")
                if attempt == retries - 1:
                    return None
        return None

    async def people_search_page(
        self,
        page: int,
        per_page: int = 100,
        person_locations: Optional[List[str]] = None,
        person_titles: Optional[List[str]] = None,
        organization_locations: Optional[List[str]] = None,
        organization_num_employees_ranges: Optional[List[str]] = None,
        organization_domains: Optional[List[str]] = None,
    ) -> Optional[dict]:
        payload: Dict[str, Any] = {"page": page, "per_page": min(per_page, 100)}
        if person_locations:
            payload["person_locations"] = person_locations
        if person_titles:
            payload["person_titles"] = person_titles
        if organization_locations:
            payload["organization_locations"] = organization_locations
        if organization_num_employees_ranges:
            payload["organization_num_employees_ranges"] = organization_num_employees_ranges
        if organization_domains:
            payload["organization_domains"] = organization_domains
        return await self._call(payload)

    async def people_search_all(
        self,
        max_pages: int = 100,
        on_page: Optional[Any] = None,
        **kwargs,
    ) -> List[dict]:
        """Paginate through all results. on_page(page, found, total) callback for progress."""
        all_people: List[dict] = []

        for page in range(1, max_pages + 1):
            data = await self.people_search_page(page=page, **kwargs)
            if not data:
                logger.warning(f"Page {page} returned None, stopping")
                break

            people = data.get("people", [])
            pagination = data.get("pagination", {})
            total = pagination.get("total_entries", 0)

            all_people.extend(people)

            if on_page:
                await on_page(page, len(all_people), total)

            logger.info(f"Page {page}: +{len(people)} people | total so far: {len(all_people)} / {total}")

            if not people or len(all_people) >= total:
                break

        return all_people
