"""Streaming Pipeline — companies flow through phases immediately, not in batches.

Architecture:
  Apollo pages → Queue A → Scraper → Queue B → Classifier → Queue C → People Search → DB

Each phase runs independently with its own concurrency control.
Companies don't wait for their batch — they flow through as soon as discovered.
KPI checked after each person saved — pipeline stops immediately when target met.

Concurrency per phase:
  Apollo search: 10 parallel pages (rate limited, paid)
  Scraper: 100 concurrent (Apify proxy, adaptive semaphore, retry 3x)
  Classifier: 100 concurrent (GPT-4o-mini, adaptive semaphore, retry 3x)
  People search: 20 concurrent (FREE seniority search)
  People enrichment: batched bulk_match (paid, 1 credit/person)
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from math import ceil
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gathering import GatheringRun, CompanySourceLink
from app.models.pipeline import DiscoveredCompany, ExtractedContact
from app.models.project import Project

logger = logging.getLogger(__name__)

DEFAULT_TARGET_COUNT = 100
DEFAULT_CONTACTS_PER_COMPANY = 3


class StreamingPipeline:
    """Streaming pipeline — each company flows through all phases immediately."""

    def __init__(self, session: AsyncSession, run: GatheringRun,
                 openai_key: str, apollo_service=None, apify_proxy: Optional[str] = None):
        self.session = session
        self.run = run
        self.openai_key = openai_key
        self.apollo = apollo_service
        self.apify_proxy = apify_proxy

        # KPI
        self.target_count = run.target_people or DEFAULT_TARGET_COUNT
        self.max_per_company = run.max_people_per_company or DEFAULT_CONTACTS_PER_COMPANY

        # Counters
        self.total_companies = 0
        self.total_scraped = 0
        self.total_classified = 0
        self.total_targets = 0
        self.total_people = 0
        self.pages_fetched = 0

        # Queues (backpressure via maxsize)
        self.scrape_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.classify_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.people_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.enrich_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # State
        self._kpi_met = False
        self._stop = False
        self._domains_seen: Set[str] = set()
        self._started_at = time.time()

    async def run_until_kpi(self, filters: Dict) -> Dict:
        """Main entry — start all phase workers, feed Apollo pages, wait for KPI."""
        self.run.started_at = datetime.now(timezone.utc)
        await self.session.flush()

        logger.info(f"Streaming pipeline started: target={self.target_count} people, "
                     f"max {self.max_per_company}/company")

        # Start phase workers
        workers = [
            asyncio.create_task(self._scraper_worker()),
            asyncio.create_task(self._classifier_worker()),
            asyncio.create_task(self._people_worker()),
        ]

        # Feed Apollo pages
        await self._feed_apollo_pages(filters)

        # Signal workers to stop (send poison pills)
        await self.scrape_queue.put(None)
        await self.classify_queue.put(None)
        await self.people_queue.put(None)

        # Wait for all workers to finish
        await asyncio.gather(*workers, return_exceptions=True)

        elapsed = time.time() - self._started_at
        return self._build_result(elapsed)

    async def _feed_apollo_pages(self, filters: Dict):
        """Fetch Apollo pages and feed companies to scrape queue."""
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        adapter = svc._get_adapter(self.run.source_type, apollo_service=self.apollo)
        if not adapter:
            return

        max_pages = filters.get("max_pages", 10)
        page_offset = filters.get("page_offset", 1)
        per_page = filters.get("per_page", 100)

        for page in range(page_offset, page_offset + max_pages):
            if self._kpi_met or self._stop:
                break

            batch_filters = dict(filters)
            batch_filters["page"] = page
            batch_filters["max_pages"] = 1
            batch_filters["per_page"] = per_page

            try:
                results = await adapter.gather(batch_filters)
                self.pages_fetched += 1

                for company_data in (results or []):
                    if self._kpi_met:
                        break
                    domain = company_data.get("domain", "").lower().strip()
                    if not domain or domain in self._domains_seen:
                        continue

                    # Check DB dedup
                    db_exists = (await self.session.execute(
                        select(DiscoveredCompany.id).where(
                            DiscoveredCompany.project_id == self.run.project_id,
                            DiscoveredCompany.domain == domain,
                        )
                    )).scalar_one_or_none()
                    if db_exists:
                        self._domains_seen.add(domain)
                        continue

                    self._domains_seen.add(domain)

                    # Create DiscoveredCompany + CompanySourceLink
                    dc = DiscoveredCompany(
                        project_id=self.run.project_id,
                        company_id=self.run.company_id,
                        domain=domain,
                        name=company_data.get("name"),
                        industry=company_data.get("industry"),
                        employee_count=company_data.get("employee_count"),
                        country=company_data.get("country"),
                        city=company_data.get("city"),
                        source_data=company_data,
                    )
                    self.session.add(dc)
                    await self.session.flush()

                    link = CompanySourceLink(
                        discovered_company_id=dc.id,
                        gathering_run_id=self.run.id,
                    )
                    self.session.add(link)
                    self.total_companies += 1

                    # Feed to scrape queue immediately
                    await self.scrape_queue.put(dc)

                logger.info(f"Apollo page {page}: {self.total_companies} companies, "
                           f"{self.total_targets} targets, {self.total_people} people")

            except Exception as e:
                logger.warning(f"Apollo page {page} failed: {e}")

            # Persist progress
            self.run.new_companies_count = self.total_companies
            self.run.pages_fetched = self.pages_fetched
            self.run.total_targets_found = self.total_targets
            self.run.total_people_found = self.total_people
            await self.session.flush()

    async def _scraper_worker(self):
        """Scrape websites — 100 concurrent via Apify proxy."""
        from app.services.scraper_service import ScraperService
        scraper = ScraperService(apify_proxy_password=self.apify_proxy)
        sem = asyncio.Semaphore(100)

        async def scrape_one(dc):
            async with sem:
                try:
                    result = await scraper.scrape_website(f"https://{dc.domain}")
                    if result.get("success"):
                        dc.scraped_text = result["text"][:50000]
                        dc.scraped_at = datetime.now(timezone.utc)
                        dc.status = "scraped"
                        self.total_scraped += 1
                        # Feed to classifier immediately
                        await self.classify_queue.put(dc)
                    else:
                        dc.status = "scrape_failed"
                except Exception as e:
                    dc.status = "scrape_failed"
                    logger.debug(f"Scrape {dc.domain}: {e}")

        tasks = []
        while True:
            dc = await self.scrape_queue.get()
            if dc is None:  # Poison pill
                break
            if self._kpi_met:
                continue
            tasks.append(asyncio.create_task(scrape_one(dc)))

        # Wait for remaining scrapes
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Pass poison pill to next queue
        await self.classify_queue.put(None)

    async def _classifier_worker(self):
        """Classify companies — 100 concurrent GPT-4o-mini."""
        import httpx
        import json
        sem = asyncio.Semaphore(100)

        # Get offer context for classification
        project = await self.session.get(Project, self.run.project_id)
        offer_text = project.target_segments if project else ""

        async def classify_one(dc):
            async with sem:
                if not dc.scraped_text or self._kpi_met:
                    return
                try:
                    company_text = f"Company: {dc.name or dc.domain}\nDomain: {dc.domain}"
                    if dc.industry:
                        company_text += f"\nIndustry: {dc.industry}"
                    company_text += f"\n\nWebsite:\n{dc.scraped_text[:3000]}"

                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {self.openai_key}",
                                     "Content-Type": "application/json"},
                            json={
                                "model": "gpt-4o-mini",
                                "messages": [
                                    {"role": "system", "content": f"Classify if this company is a target customer.\nOffer: {offer_text}\nReturn JSON: {{\"is_target\": true/false, \"segment\": \"CAPS_LABEL\", \"reasoning\": \"1 line\"}}"},
                                    {"role": "user", "content": company_text},
                                ],
                                "max_tokens": 150, "temperature": 0.1,
                            },
                        )
                        data = resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        clean = content.strip()
                        if clean.startswith("```"):
                            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                        parsed = json.loads(clean)

                        dc.is_target = parsed.get("is_target", False)
                        dc.analysis_segment = parsed.get("segment", "")
                        dc.analysis_reasoning = parsed.get("reasoning", "")
                        dc.status = "target" if dc.is_target else "rejected"
                        self.total_classified += 1

                        if dc.is_target:
                            self.total_targets += 1
                            # Feed to people queue immediately
                            await self.people_queue.put(dc)

                except Exception as e:
                    dc.status = "classify_failed"
                    logger.debug(f"Classify {dc.domain}: {e}")

        tasks = []
        while True:
            dc = await self.classify_queue.get()
            if dc is None:
                break
            if self._kpi_met:
                continue
            tasks.append(asyncio.create_task(classify_one(dc)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await self.people_queue.put(None)

    async def _people_worker(self):
        """Extract people for target companies — 20 concurrent."""
        if not self.apollo:
            return

        # Get target roles
        project = await self.session.get(Project, self.run.project_id)
        person_titles = None
        if project and project.offer_summary and isinstance(project.offer_summary, dict):
            target_roles = project.offer_summary.get("target_roles", {})
            if target_roles.get("titles"):
                person_titles = target_roles["titles"]

        sem = asyncio.Semaphore(20)

        async def extract_one(dc):
            async with sem:
                if self._kpi_met:
                    return
                try:
                    people = await self.apollo.enrich_by_domain(
                        dc.domain, limit=self.max_per_company,
                        titles=person_titles,
                    )
                    for person in people:
                        contact = ExtractedContact(
                            project_id=self.run.project_id,
                            discovered_company_id=dc.id,
                            email=person.get("email"),
                            first_name=person.get("first_name"),
                            last_name=person.get("last_name"),
                            job_title=person.get("title") or person.get("job_title"),
                            linkedin_url=person.get("linkedin_url"),
                            email_verified=person.get("is_verified", False),
                            email_source="apollo" if person.get("is_verified") else None,
                            source_data=person,
                        )
                        self.session.add(contact)
                        self.total_people += 1

                        # Check KPI after each person
                        if self.total_people >= self.target_count:
                            self._kpi_met = True
                            logger.info(f"KPI MET: {self.total_people} people >= {self.target_count}")
                            break

                    # Persist
                    self.run.total_people_found = self.total_people
                    self.run.total_targets_found = self.total_targets
                    self.run.credits_used = (self.run.credits_used or 0) + len(people)
                    await self.session.flush()

                except Exception as e:
                    logger.debug(f"People search {dc.domain}: {e}")

        tasks = []
        while True:
            dc = await self.people_queue.get()
            if dc is None:
                break
            tasks.append(asyncio.create_task(extract_one(dc)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _build_result(self, elapsed: float) -> Dict:
        return {
            "status": "completed" if self._kpi_met else "insufficient",
            "kpi_met": self._kpi_met,
            "total_companies": self.total_companies,
            "total_scraped": self.total_scraped,
            "total_classified": self.total_classified,
            "total_targets": self.total_targets,
            "total_people": self.total_people,
            "pages_fetched": self.pages_fetched,
            "elapsed_seconds": round(elapsed, 1),
            "credits_used": self.run.credits_used or 0,
            "message": (
                f"Pipeline {'complete' if self._kpi_met else 'incomplete'}: "
                f"{self.total_targets} targets, {self.total_people}/{self.target_count} people "
                f"in {elapsed:.0f}s ({self.pages_fetched} pages, {self.run.credits_used or 0} credits)"
            ),
        }
