"""Apollo Service — adapted for MCP with per-user API keys."""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class ApolloService:
    RATE_LIMIT_INTERVAL = 0.3

    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://api.apollo.io/api/v1"
        self._api_key = api_key
        self.credits_used: int = 0
        self._last_call_time: float = 0

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        from app.config import settings
        return settings.APOLLO_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < self.RATE_LIMIT_INTERVAL:
            await asyncio.sleep(self.RATE_LIMIT_INTERVAL - elapsed)
        self._last_call_time = time.monotonic()

    async def _api_call(self, method: str, endpoint: str, json_data: dict = None) -> Optional[dict]:
        MAX_RETRIES = 3
        backoff_waits = [30, 60, 120]

        for attempt in range(MAX_RETRIES + 1):
            await self._rate_limit()
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    if method == "POST":
                        resp = await client.post(f"{self.base_url}{endpoint}", json=json_data, headers=self._get_headers())
                    else:
                        resp = await client.get(f"{self.base_url}{endpoint}", headers=self._get_headers())
                    if resp.status_code == 429:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(backoff_waits[attempt])
                            self._last_call_time = time.monotonic()
                            continue
                        return None
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Apollo API {endpoint}: {e.response.status_code}")
                return None
            except Exception as e:
                logger.error(f"Apollo API {endpoint} failed: {e}")
                return None
        return None

    async def search_organizations(
        self, keyword_tags: List[str], locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        latest_funding_stages: Optional[List[str]] = None,
        page: int = 1, per_page: int = 100,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        payload: Dict[str, Any] = {
            "q_organization_keyword_tags": keyword_tags,
            "page": page, "per_page": min(per_page, 100),
        }
        if locations:
            payload["organization_locations"] = locations
        if num_employees_ranges:
            payload["organization_num_employees_ranges"] = num_employees_ranges
        if latest_funding_stages:
            payload["organization_latest_funding_stage_cd"] = latest_funding_stages
        return await self._api_call("POST", "/mixed_companies/search", payload)

    async def search_organizations_all_pages(
        self, keyword_tags: List[str], locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        latest_funding_stages: Optional[List[str]] = None,
        max_pages: int = 50, per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        all_orgs: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            data = await self.search_organizations(
                keyword_tags=keyword_tags, locations=locations,
                num_employees_ranges=num_employees_ranges,
                latest_funding_stages=latest_funding_stages,
                page=page, per_page=per_page,
            )
            if not data:
                break
            # Apollo returns companies in "accounts" OR "organizations" depending on endpoint version
            orgs = data.get("organizations", []) or data.get("accounts", [])
            all_orgs.extend(orgs)
            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)
            logger.info(f"Apollo org search: page {page}/{total_pages}, got {len(orgs)} orgs (total: {len(all_orgs)})")
            if page >= total_pages:
                break
        return all_orgs

    async def enrich_by_domain(self, domain: str, limit: int = 5, titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
        payload: Dict[str, Any] = {"q_organization_domains": domain, "page": 1, "per_page": min(limit, 10)}
        if titles:
            payload["person_titles"] = titles
        search_data = await self._api_call("POST", "/mixed_people/api_search", payload)
        if not search_data:
            return []
        people = search_data.get("people", [])[:limit]
        if not people:
            return []
        details = [{"id": p["id"]} for p in people if p.get("id")]
        if not details:
            return []
        bulk_data = await self._api_call("POST", "/people/bulk_match", {"details": details, "reveal_personal_emails": True})
        if not bulk_data:
            return []
        matches = bulk_data.get("matches", [])
        self.credits_used += sum(1 for m in matches if m)
        results = []
        for match in matches:
            if not match:
                continue
            phone = None
            if match.get("phone_numbers"):
                phone = match["phone_numbers"][0].get("sanitized_number")
            results.append({
                "email": match.get("email"),
                "first_name": match.get("first_name"),
                "last_name": match.get("last_name"),
                "job_title": match.get("title"),
                "linkedin_url": match.get("linkedin_url"),
                "is_verified": match.get("email_status") == "verified",
                "phone": phone,
            })
        return results

    async def enrich_organization(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get FULL company data by domain — includes keywords, industry, employees.
        WARNING: costs 1 credit per call."""
        if not self.api_key:
            return None
        data = await self._api_call("POST", "/organizations/enrich", {"domain": domain})
        if data and data.get("organization"):
            self.credits_used += 1
            return data["organization"]
        return None

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        data = await self._api_call("POST", "/mixed_people/api_search", {"q_organization_domains": "apollo.io", "per_page": 1})
        return data is not None

    def reset_credits(self):
        self.credits_used = 0
