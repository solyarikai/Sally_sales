"""Apollo Service — adapted for MCP with per-user API keys.

Official Apollo API credit costs (from Apollo pricing page):
  /mixed_people/api_search     — FREE (partial profile, max 100/page)
  /mixed_companies/search  — 1 credit / page returned (max 100/page)
  /people/match                — 1 credit / net-new email, 1 / firmographic, 5 / phone
  /people/bulk_match           — same as /people/match per result
  /organizations/enrich        — 1 credit / result returned
  /organizations/bulk_enrich   — 1 credit / company returned (max 10/page)
  /organizations/{id}/job_postings — 1 credit / result (max 10,000/page)
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.services.cost_tracker import get_tracker

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
        from app.services.adaptive_semaphore import APOLLO_SEM
        sem = APOLLO_SEM()

        for attempt in range(MAX_RETRIES + 1):
            await self._rate_limit()
            try:
                async with sem.acquire():
                    async with httpx.AsyncClient(timeout=30) as client:
                        if method == "POST":
                            resp = await client.post(f"{self.base_url}{endpoint}", json=json_data, headers=self._get_headers())
                        else:
                            resp = await client.get(f"{self.base_url}{endpoint}", headers=self._get_headers())
                        if resp.status_code == 429:
                            sem.report_429()
                            if attempt < MAX_RETRIES:
                                await asyncio.sleep(backoff_waits[attempt])
                                self._last_call_time = time.monotonic()
                                continue
                            return None
                        sem.report_ok()
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
        self, keyword_tags: Optional[List[str]] = None,
        industry_tag_ids: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        latest_funding_stages: Optional[List[str]] = None,
        q_organization_name: Optional[str] = None,
        page: int = 1, per_page: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """Search Apollo companies.

        Best filter priority:
        1. industry_tag_ids (from enrichment) → organization_industry_tag_ids → BEST pagination
        2. keyword_tags → q_organization_keyword_tags → inconsistent pagination
        3. q_organization_name → text search → OK pagination
        """
        if not self.api_key:
            return None
        payload: Dict[str, Any] = {
            "page": page, "per_page": min(per_page, 100),
        }
        # Prefer industry_tag_ids (real Apollo IDs from enrichment — best pagination)
        if industry_tag_ids:
            payload["organization_industry_tag_ids"] = industry_tag_ids
        # Add keyword_tags as secondary filter
        if keyword_tags:
            payload["q_organization_keyword_tags"] = keyword_tags
        # Text search by company name
        if q_organization_name:
            payload["q_organization_name"] = q_organization_name
        if locations:
            payload["organization_locations"] = locations
        if num_employees_ranges:
            payload["organization_num_employees_ranges"] = num_employees_ranges
        if latest_funding_stages:
            payload["organization_latest_funding_stage_cd"] = latest_funding_stages
        result = await self._api_call("POST", "/mixed_companies/search", payload)
        if result:
            self.credits_used += 1
            get_tracker().log_apollo(1, "search")
        return result

    async def search_organizations_all_pages(
        self, keyword_tags: Optional[List[str]] = None,
        industry_tag_ids: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        num_employees_ranges: Optional[List[str]] = None,
        latest_funding_stages: Optional[List[str]] = None,
        q_organization_name: Optional[str] = None,
        max_pages: int = 50, per_page: int = 100,
        batch_size: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch multiple pages in parallel batches of batch_size.
        Prefers industry_tag_ids (from enrichment) for best pagination."""
        all_orgs: List[Dict[str, Any]] = []
        total_pages_apollo = max_pages

        for batch_start in range(1, max_pages + 1, batch_size):
            batch_end = min(batch_start + batch_size, max_pages + 1)
            pages_to_fetch = list(range(batch_start, batch_end))

            async def fetch_page(page):
                return page, await self.search_organizations(
                    keyword_tags=keyword_tags, industry_tag_ids=industry_tag_ids,
                    locations=locations, num_employees_ranges=num_employees_ranges,
                    latest_funding_stages=latest_funding_stages,
                    q_organization_name=q_organization_name,
                    page=page, per_page=per_page,
                )

            results = await asyncio.gather(*[fetch_page(p) for p in pages_to_fetch])

            batch_orgs = 0
            stop = False
            for page, data in sorted(results, key=lambda x: x[0]):
                if not data:
                    stop = True
                    break
                orgs = data.get("organizations", []) or data.get("accounts", [])
                all_orgs.extend(orgs)
                batch_orgs += len(orgs)
                pagination = data.get("pagination", {})
                total_pages_apollo = pagination.get("total_pages", total_pages_apollo)
                if page >= total_pages_apollo:
                    stop = True
                    break

            logger.info(f"Apollo batch {batch_start}-{batch_end-1}: {batch_orgs} orgs (total: {len(all_orgs)}, apollo_pages: {total_pages_apollo})")

            if stop:
                break

        return all_orgs

    async def enrich_by_domain(self, domain: str, limit: int = 5, titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search people at a domain. FREE via /mixed_people/api_search.

        Returns partial profiles (name, title, linkedin). Email requires bulk_match (1 credit each).
        For MCP: return partial profiles first — email enrichment is optional.
        """
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

        # Step 1: FREE search got people IDs
        people_ids = [p["id"] for p in people if p.get("id")]
        logger.info(f"People search for {domain}: found {len(people)} people, {len(people_ids)} with IDs")
        if not people_ids:
            return []
        # Step 2: bulk_match to get emails (1 credit per person — REQUIRED for SmartLead)
        enriched = await self.enrich_people_emails(people_ids)
        logger.info(f"People enrichment for {domain}: {len(enriched)} with emails")
        return enriched

    async def enrich_people_emails(self, people_ids: List[str]) -> List[Dict[str, Any]]:
        """Enrich people with emails via bulk_match (1 credit per person)."""
        logger.info(f"bulk_match: enriching {len(people_ids)} people IDs")
        if not self.api_key or not people_ids:
            return []
        details = [{"id": pid} for pid in people_ids]
        bulk_data = await self._api_call("POST", "/people/bulk_match", {"details": details, "reveal_personal_emails": True})
        if not bulk_data:
            return []
        matches = bulk_data.get("matches", [])
        matched_count = sum(1 for m in matches if m)
        self.credits_used += matched_count
        get_tracker().log_apollo(matched_count, "bulk_match")
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
                "title": match.get("title"),
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
            get_tracker().log_apollo(1, "enrich")
            return data["organization"]
        return None

    async def bulk_enrich_organizations(self, domains: List[str]) -> List[Dict[str, Any]]:
        """Bulk enrich companies by domain — returns full Apollo labels.
        Max 10 per call, 1 credit per company returned.
        Use for adjustment phase: extract keywords/industries from top targets."""
        if not self.api_key or not domains:
            return []
        results = []
        # Apollo bulk_enrich: max 10 per request
        for i in range(0, len(domains), 10):
            batch = domains[i:i+10]
            data = await self._api_call("POST", "/organizations/bulk_enrich", {"domains": batch})
            if data and data.get("organizations"):
                orgs = data["organizations"]
                self.credits_used += len(orgs)
                get_tracker().log_apollo(len(orgs), "bulk_enrich")
                results.extend(orgs)
        return results

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        data = await self._api_call("POST", "/mixed_people/api_search", {"q_organization_domains": "apollo.io", "per_page": 1})
        return data is not None

    async def get_account_info(self) -> dict:
        """Get account info including plan type and credit limit."""
        if not self.api_key:
            return {}
        data = await self._api_call("GET", "/auth/check")
        if not data:
            return {}
        bd = data.get("bootstrapped_data", {})
        return {
            "is_core": bd.get("is_core", False),
            "free_lead_credit_limit": bd.get("free_lead_credit_limit", 0),
            "team_id": bd.get("current_team_id"),
        }

    def reset_credits(self):
        self.credits_used = 0
