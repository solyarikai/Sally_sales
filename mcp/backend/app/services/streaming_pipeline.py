"""Streaming Pipeline — companies flow through phases immediately, not in batches.

Architecture:
  Phase 1: Process existing companies (batch, fully concurrent within phase)
  Phase 2: If KPI not met → Apollo pages → Queue A → Scraper → Queue B → Classifier → Queue C → People → DB

Existing companies (from tam_gather) are processed in batch to avoid wasting Apollo credits.
New Apollo pages use streaming queues so companies flow through as soon as discovered.
KPI checked after each person saved — pipeline stops immediately when target met.

Concurrency per phase:
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

from sqlalchemy import select, or_, func as sa_func
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

        # Queues (for streaming phase only — Apollo page discovery)
        self.scrape_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.classify_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.people_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # State
        self._kpi_met = False
        self._stop = False
        self._domains_seen: Set[str] = set()
        self._started_at = time.time()

        # Shared services (initialized once, reused across phases)
        self._scraper = None
        self._offer_text = None
        self._person_titles = None

    async def _init_services(self):
        """Initialize shared services once."""
        from app.services.scraper_service import ScraperService
        self._scraper = ScraperService(apify_proxy_password=self.apify_proxy)

        project = await self.session.get(Project, self.run.project_id)
        self._offer_text = project.target_segments if project else ""

        if project and project.offer_summary and isinstance(project.offer_summary, dict):
            target_roles = project.offer_summary.get("target_roles", {})
            if target_roles.get("titles"):
                self._person_titles = target_roles["titles"]

    async def run_until_kpi(self, filters: Dict) -> Dict:
        """Main entry — process existing companies first, then stream from Apollo if needed."""
        self.run.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._init_services()

        logger.info(f"Streaming pipeline started: target={self.target_count} people, "
                     f"max {self.max_per_company}/company")

        # ── Phase 1: Process existing companies (batch mode) ──
        # These were gathered by tam_gather. Process them fully before deciding if we need Apollo.
        existing = await self._load_existing_companies()
        if existing:
            logger.info(f"Phase 1: Processing {len(existing)} existing companies in batch")
            self.total_companies = len(existing)
            for dc in existing:
                self._domains_seen.add(dc.domain)

            # Scrape → Classify → People (each phase waits for completion)
            await self._batch_scrape(existing)
            scraped = [dc for dc in existing if dc.scraped_text]
            await self._batch_classify(scraped)
            targets = [dc for dc in existing if dc.is_target]
            await self._batch_people(targets)

            await self._persist_progress()
            logger.info(f"Phase 1 done: {self.total_scraped} scraped, "
                        f"{self.total_targets} targets, {self.total_people} people "
                        f"in {time.time() - self._started_at:.0f}s")

        # ── Phase 2: Stream from Apollo if KPI not met ──
        if not self._kpi_met:
            logger.info(f"Phase 2: KPI not met ({self.total_people}/{self.target_count}). "
                        f"Starting Apollo streaming.")

            workers = [
                asyncio.create_task(self._scraper_worker()),
                asyncio.create_task(self._classifier_worker()),
                asyncio.create_task(self._people_worker()),
            ]

            await self._feed_apollo_pages(filters)

            # Signal workers to stop
            await self.scrape_queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)
        else:
            logger.info(f"KPI met from existing companies — skipping Apollo pages")

        elapsed = time.time() - self._started_at
        return self._build_result(elapsed)

    # ── Batch processing (Phase 1: existing companies) ──

    async def _load_existing_companies(self) -> List[DiscoveredCompany]:
        """Load companies for this run that haven't been processed yet."""
        # First: unscraped companies
        result = await self.session.execute(
            select(DiscoveredCompany)
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .where(
                CompanySourceLink.gathering_run_id == self.run.id,
                or_(
                    DiscoveredCompany.status.in_(["new", "gathered"]),
                    DiscoveredCompany.status.is_(None),
                ),
                DiscoveredCompany.scraped_text.is_(None),
            )
        )
        companies = list(result.scalars().all())
        if companies:
            return companies

        # Fallback: already scraped but not classified
        result = await self.session.execute(
            select(DiscoveredCompany)
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .where(
                CompanySourceLink.gathering_run_id == self.run.id,
                DiscoveredCompany.scraped_text.isnot(None),
                DiscoveredCompany.is_target.is_(None),
            )
        )
        return list(result.scalars().all())

    async def _batch_scrape(self, companies: List[DiscoveredCompany]):
        """Scrape all companies concurrently (100 parallel)."""
        sem = asyncio.Semaphore(100)

        async def scrape_one(dc):
            async with sem:
                try:
                    result = await self._scraper.scrape_website(f"https://{dc.domain}")
                    if result.get("success"):
                        dc.scraped_text = result["text"][:50000]
                        dc.scraped_at = datetime.now(timezone.utc)
                        dc.status = "scraped"
                        self.total_scraped += 1
                    else:
                        dc.status = "scrape_failed"
                except Exception as e:
                    dc.status = "scrape_failed"
                    logger.debug(f"Scrape {dc.domain}: {e}")

        await asyncio.gather(*[scrape_one(dc) for dc in companies], return_exceptions=True)
        await self.session.flush()
        logger.info(f"Batch scrape: {self.total_scraped}/{len(companies)} succeeded")

    async def _batch_classify(self, companies: List[DiscoveredCompany]):
        """Classify all scraped companies concurrently (100 parallel)."""
        import httpx
        import json
        sem = asyncio.Semaphore(100)

        async def classify_one(dc):
            async with sem:
                if not dc.scraped_text:
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
                                    {"role": "system", "content": (
                                        f"Classify if this company is a target customer.\n"
                                        f"Offer: {self._offer_text}\n"
                                        f"Return JSON: {{\"is_target\": true/false, \"segment\": \"CAPS_LABEL\", \"reasoning\": \"1 line\"}}"
                                    )},
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
                except Exception as e:
                    dc.status = "classify_failed"
                    logger.debug(f"Classify {dc.domain}: {e}")

        await asyncio.gather(*[classify_one(dc) for dc in companies], return_exceptions=True)
        await self.session.flush()
        logger.info(f"Batch classify: {self.total_classified} done, {self.total_targets} targets")

    async def _batch_people(self, targets: List[DiscoveredCompany]):
        """Extract people for target companies concurrently (20 parallel)."""
        if not self.apollo or not targets:
            return
        sem = asyncio.Semaphore(20)
        contacts_to_add = []

        async def extract_one(dc):
            nonlocal contacts_to_add
            if self._kpi_met:
                return
            async with sem:
                try:
                    people = await self.apollo.enrich_by_domain(
                        dc.domain, limit=self.max_per_company,
                        titles=self._person_titles,
                    )
                    for person in people:
                        contacts_to_add.append(ExtractedContact(
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
                        ))
                        self.total_people += 1
                        if self.total_people >= self.target_count:
                            self._kpi_met = True
                            logger.info(f"KPI MET: {self.total_people} people >= {self.target_count}")
                            break

                    self.run.credits_used = (self.run.credits_used or 0) + len(people)
                except Exception as e:
                    logger.debug(f"People search {dc.domain}: {e}")

        await asyncio.gather(*[extract_one(dc) for dc in targets], return_exceptions=True)

        # Add all contacts to session at once (avoids session.add inside flush)
        for contact in contacts_to_add:
            self.session.add(contact)
        self.run.total_people_found = self.total_people
        self.run.total_targets_found = self.total_targets
        await self.session.flush()
        logger.info(f"Batch people: {self.total_people} contacts from {len(targets)} targets")

    # ── Streaming processing (Phase 2: Apollo page discovery) ──

    async def _feed_apollo_pages(self, filters: Dict):
        """Fetch Apollo pages and feed companies to scrape queue."""
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        adapter = svc._get_adapter(self.run.source_type, apollo_service=self.apollo)
        if not adapter:
            return

        # Pre-load all existing domains for this project (avoids N SELECT queries per page)
        existing_result = await self.session.execute(
            select(DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == self.run.project_id
            )
        )
        self._domains_seen.update(r[0] for r in existing_result.all())

        max_pages = filters.get("max_pages", 10)
        # Start from where tam_gather left off (avoid re-fetching same pages)
        tam_pages = self.run.pages_fetched or 0
        page_offset = tam_pages + 1
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

                # Batch: create companies, flush once per page, then create links
                page_batch = []
                for company_data in (results or []):
                    if self._kpi_met:
                        break
                    domain = company_data.get("domain", "").lower().strip()
                    if not domain or domain in self._domains_seen:
                        continue
                    self._domains_seen.add(domain)

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
                    page_batch.append(dc)

                if page_batch:
                    await self.session.flush()  # Single flush — all get IDs
                    for dc in page_batch:
                        link = CompanySourceLink(
                            discovered_company_id=dc.id,
                            gathering_run_id=self.run.id,
                        )
                        self.session.add(link)
                        self.total_companies += 1
                        await self.scrape_queue.put(dc)

                logger.info(f"Apollo page {page}: {self.total_companies} companies, "
                           f"{self.total_targets} targets, {self.total_people} people")

            except Exception as e:
                logger.warning(f"Apollo page {page} failed: {e}")

            await self._persist_progress()

    async def _scraper_worker(self):
        """Streaming scrape worker — reads from queue, 100 concurrent."""
        sem = asyncio.Semaphore(100)

        async def scrape_one(dc):
            async with sem:
                try:
                    result = await self._scraper.scrape_website(f"https://{dc.domain}")
                    if result.get("success"):
                        dc.scraped_text = result["text"][:50000]
                        dc.scraped_at = datetime.now(timezone.utc)
                        dc.status = "scraped"
                        self.total_scraped += 1
                        await self.classify_queue.put(dc)
                    else:
                        dc.status = "scrape_failed"
                except Exception as e:
                    dc.status = "scrape_failed"
                    logger.debug(f"Scrape {dc.domain}: {e}")

        tasks = []
        while True:
            dc = await self.scrape_queue.get()
            if dc is None:
                break
            if self._kpi_met:
                continue
            tasks.append(asyncio.create_task(scrape_one(dc)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.classify_queue.put(None)

    async def _classifier_worker(self):
        """Streaming classify worker — reads from queue, 100 concurrent."""
        import httpx
        import json
        sem = asyncio.Semaphore(100)

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
                                    {"role": "system", "content": (
                                        f"Classify if this company is a target customer.\n"
                                        f"Offer: {self._offer_text}\n"
                                        f"Return JSON: {{\"is_target\": true/false, \"segment\": \"CAPS_LABEL\", \"reasoning\": \"1 line\"}}"
                                    )},
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
        """Streaming people extraction worker — reads from queue, 20 concurrent."""
        if not self.apollo:
            return
        sem = asyncio.Semaphore(20)
        contacts_batch = []

        async def extract_one(dc):
            if self._kpi_met:
                return
            async with sem:
                try:
                    people = await self.apollo.enrich_by_domain(
                        dc.domain, limit=self.max_per_company,
                        titles=self._person_titles,
                    )
                    for person in people:
                        contacts_batch.append(ExtractedContact(
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
                        ))
                        self.total_people += 1
                        if self.total_people >= self.target_count:
                            self._kpi_met = True
                            logger.info(f"KPI MET: {self.total_people} people >= {self.target_count}")
                            break
                    self.run.credits_used = (self.run.credits_used or 0) + len(people)
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

        # Batch add contacts (avoids session.add inside flush)
        for contact in contacts_batch:
            self.session.add(contact)
        self.run.total_people_found = self.total_people
        self.run.total_targets_found = self.total_targets
        await self.session.flush()

    # ── Helpers ──

    async def _persist_progress(self):
        """Write counters to DB for frontend polling."""
        self.run.new_companies_count = self.total_companies
        self.run.pages_fetched = self.pages_fetched
        self.run.total_targets_found = self.total_targets
        self.run.total_people_found = self.total_people
        await self.session.flush()

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
