"""
Crona Service — Website scraping via Crona headless browser API.

Crona (api.crona.ai) provides JS-rendered website scraping at 1 credit per domain.
Much better than direct httpx for modern JS-heavy sites.

Flow:
1. Authenticate → get JWT token (cached)
2. Create project with source_type=websites_list
3. Upload CSV with domain URLs
4. Add scrape_website enricher
5. Run project, poll until complete
6. Fetch results (clean text, not raw HTML)
7. Delete project (cleanup)
"""
import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CronaService:
    """Scrapes websites via Crona API (headless browser, JS-rendered)."""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._credits_used: int = 0

    @property
    def is_configured(self) -> bool:
        return bool(settings.CRONA_EMAIL and settings.CRONA_PASSWORD)

    @property
    def credits_used(self) -> int:
        return self._credits_used

    async def _authenticate(self) -> str:
        """Get JWT token, cached for 6 days (tokens last 7 days)."""
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token

        if not self.is_configured:
            raise ValueError("CRONA_EMAIL and CRONA_PASSWORD not configured")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.CRONA_API_URL}/api/clients/sign_in",
                json={"client": {
                    "email": settings.CRONA_EMAIL,
                    "password": settings.CRONA_PASSWORD,
                }},
            )
            resp.raise_for_status()
            data = resp.json()

        self._token = data["jwt_token"]
        self._token_expires = datetime.utcnow() + timedelta(days=6)
        logger.info(f"Crona auth OK, credits_balance={data.get('credits_balance')}")
        return self._token

    async def _headers(self) -> dict:
        token = await self._authenticate()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def get_credits_balance(self) -> int:
        """Check current credits balance."""
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{settings.CRONA_API_URL}/api/whoami/credits_balance",
                headers=headers,
            )
            resp.raise_for_status()
        return resp.json().get("credits_balance", 0)

    async def scrape_domains(
        self,
        domains: List[str],
        timeout: int = 120,
        poll_interval: float = 3.0,
    ) -> Dict[str, Optional[str]]:
        """
        Scrape multiple domains via Crona.

        Args:
            domains: List of domain names (without https://)
            timeout: Max seconds to wait for completion
            poll_interval: Seconds between status polls

        Returns:
            Dict mapping domain → scraped text (or None if failed)
        """
        if not domains:
            return {}

        if not self.is_configured:
            logger.warning("Crona not configured, returning empty results")
            return {d: None for d in domains}

        headers = await self._headers()
        project_id = None

        try:
            # 1. Create project
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects",
                    headers=headers,
                    json={"project": {"name": f"scrape_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"}},
                )
                resp.raise_for_status()
                project_id = resp.json()["id"]

            # 2. Upload CSV with domains
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["website"])
            for d in domains:
                url = d if d.startswith("http") else f"https://{d}"
                writer.writerow([url])

            # Upload as multipart form
            token = await self._authenticate()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/source_file",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"source_type": "websites_list"},
                    files={"file": ("domains.csv", csv_buffer.getvalue().encode(), "text/csv")},
                )
                resp.raise_for_status()

            # 3. Add scrape_website enricher
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/enrichers",
                    headers=headers,
                    json={"enricher": {
                        "name": "Scrape Website",
                        "field_name": "scraped_text",
                        "code": "",
                        "order": 1,
                        "type": "scrape_website",
                        "arguments": {
                            "based_on": "Website URL",
                            "url_column": "website",
                        },
                    }},
                )
                resp.raise_for_status()

            # 4. Run project
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/project_runs",
                    headers=headers,
                    json={},
                )
                resp.raise_for_status()

            # 5. Poll until complete
            start = datetime.utcnow()
            while (datetime.utcnow() - start).total_seconds() < timeout:
                await asyncio.sleep(poll_interval)
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{settings.CRONA_API_URL}/api/projects/{project_id}/status",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    status = resp.json()

                if status["status"] == "completed":
                    break
                elif status["status"] == "failed":
                    logger.error(f"Crona project {project_id} failed: {status.get('error_message')}")
                    return {d: None for d in domains}

            # 6. Fetch results
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/last_results",
                    headers=headers,
                )
                resp.raise_for_status()
                result_data = resp.json()

            # Parse results: first row is header, rest are [url, scraped_text]
            rows = result_data.get("data", [])
            results: Dict[str, Optional[str]] = {}

            for row in rows[1:]:  # skip header row
                if len(row) < 2:
                    continue
                url = row[0] if isinstance(row[0], str) else ""
                text = row[1] if isinstance(row[1], str) else None

                # Extract domain from URL
                domain = url.replace("https://", "").replace("http://", "").rstrip("/")
                results[domain] = text

            # Track credits (1 per domain)
            self._credits_used += len(domains)

            # Map back to input domains
            final: Dict[str, Optional[str]] = {}
            for d in domains:
                clean_d = d.replace("https://", "").replace("http://", "").rstrip("/")
                final[d] = results.get(clean_d)

            logger.info(
                f"Crona scraped {len(domains)} domains: "
                f"{sum(1 for v in final.values() if v)} success, "
                f"{sum(1 for v in final.values() if not v)} failed, "
                f"credits_used={self._credits_used}"
            )
            return final

        except Exception as e:
            logger.error(f"Crona scrape batch failed: {e}")
            return {d: None for d in domains}

        finally:
            # 7. Cleanup: delete project
            if project_id:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.delete(
                            f"{settings.CRONA_API_URL}/api/projects/{project_id}",
                            headers=headers,
                        )
                except Exception:
                    pass  # Best-effort cleanup


    async def enrich_person_by_linkedin(
        self,
        linkedin_url: str,
        timeout: int = 60,
        poll_interval: float = 3.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Enrich a person by their LinkedIn profile URL via Crona.

        Uses the linkedin_profiles source type with linkedin_profile enricher.
        Returns enrichment data dict or None if failed.
        Cost: 1 credit per profile.
        """
        if not linkedin_url:
            return None

        if not self.is_configured:
            logger.warning("Crona not configured, skipping LinkedIn enrichment")
            return None

        headers = await self._headers()
        project_id = None

        try:
            # 1. Create project
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects",
                    headers=headers,
                    json={"project": {"name": f"li_enrich_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"}},
                )
                resp.raise_for_status()
                project_id = resp.json()["id"]

            # 2. Upload CSV with LinkedIn URL
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["linkedin_url"])
            url = linkedin_url if linkedin_url.startswith("http") else f"https://{linkedin_url}"
            writer.writerow([url])

            token = await self._authenticate()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/source_file",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"source_type": "linkedin_profiles"},
                    files={"file": ("profiles.csv", csv_buffer.getvalue().encode(), "text/csv")},
                )
                resp.raise_for_status()

            # 3. Add linkedin_profile enricher
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/enrichers",
                    headers=headers,
                    json={"enricher": {
                        "name": "LinkedIn Profile",
                        "field_name": "linkedin_data",
                        "code": "",
                        "order": 1,
                        "type": "linkedin_profile",
                        "arguments": {
                            "based_on": "LinkedIn URL",
                            "url_column": "linkedin_url",
                        },
                    }},
                )
                resp.raise_for_status()

            # 4. Run project
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/project_runs",
                    headers=headers,
                    json={},
                )
                resp.raise_for_status()

            # 5. Poll until complete
            start = datetime.utcnow()
            while (datetime.utcnow() - start).total_seconds() < timeout:
                await asyncio.sleep(poll_interval)
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{settings.CRONA_API_URL}/api/projects/{project_id}/status",
                        headers=headers,
                    )
                    resp.raise_for_status()
                    status = resp.json()

                if status["status"] == "completed":
                    break
                elif status["status"] == "failed":
                    logger.error(f"Crona LinkedIn enrichment failed: {status.get('error_message')}")
                    return None

            # 6. Fetch results
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{settings.CRONA_API_URL}/api/projects/{project_id}/last_results",
                    headers=headers,
                )
                resp.raise_for_status()
                result_data = resp.json()

            rows = result_data.get("data", [])
            if len(rows) < 2:
                return None

            # Parse result — header row + data row
            header = rows[0]
            data_row = rows[1]
            result = {}
            for i, col_name in enumerate(header):
                if i < len(data_row):
                    result[col_name] = data_row[i]

            self._credits_used += 1
            logger.info(f"Crona LinkedIn enrichment OK for {linkedin_url}, credits_used={self._credits_used}")
            return result

        except Exception as e:
            logger.error(f"Crona LinkedIn enrichment failed: {e}")
            return None

        finally:
            if project_id:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.delete(
                            f"{settings.CRONA_API_URL}/api/projects/{project_id}",
                            headers=headers,
                        )
                except Exception:
                    pass


# Module-level singleton
crona_service = CronaService()
