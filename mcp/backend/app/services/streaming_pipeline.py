"""Streaming Pipeline — SINGLE MODE, every company flows through immediately.

Architecture:
  scrape_queue → Scraper (100 concurrent) → classify_queue → Classifier (100 concurrent) → people_queue → People (20 concurrent)

  1. Workers start FIRST (scraper, classifier, people)
  2. Existing companies (from tam_gather probe+confirm) fed to scrape_queue — flow immediately
  3. If KPI not met: Apollo pages fetched in PARALLEL batches of 10 → results fed to same scrape_queue
  4. Exhaustion: 20 empty pages → regenerate keywords via GPT (up to 5 times per strategy)
  5. KPI checked after each person — pipeline stops immediately when target met
  6. On completion or exhaustion: auto-push gathered contacts to SmartLead

No batch phases. No serial waiting. Each company flows through scrape→classify→people
as soon as it's discovered — whether from tam_gather or fresh Apollo pages.
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
        self._tam_pages = run.pages_fetched or 0  # Pages already consumed by tam_gather

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
        """Main entry — SINGLE STREAMING MODE for everything.

        All companies (existing + new Apollo) flow through the same queue workers:
          scrape_queue → scraper (100) → classify_queue → classifier (100) → people_queue → people (20)

        Each company flows immediately — no waiting for batches.
        """
        self.run.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self._init_services()

        logger.info(f"Streaming pipeline started: target={self.target_count} people, "
                     f"max {self.max_per_company}/company")

        # Start streaming workers — they run the ENTIRE time
        workers = [
            asyncio.create_task(self._scraper_worker()),
            asyncio.create_task(self._classifier_worker()),
            asyncio.create_task(self._people_worker()),
        ]

        # Feed existing companies (from tam_gather) into the queue — they flow immediately
        existing = await self._load_existing_companies()
        if existing:
            logger.info(f"Feeding {len(existing)} existing companies to streaming queue")
            self.total_companies = len(existing)
            for dc in existing:
                self._domains_seen.add(dc.domain)
                await self.scrape_queue.put(dc)

        # Feed more Apollo pages if needed — same queue, same workers
        # Workers are ALREADY processing existing companies in parallel
        if not self._kpi_met:
            await self._feed_apollo_pages(filters)

        # Signal workers to drain and stop
        await self.scrape_queue.put(None)
        await asyncio.gather(*workers, return_exceptions=True)

        # Final progress persist
        await self._persist_progress()

        elapsed = time.time() - self._started_at
        logger.info(f"Pipeline done: {self.total_scraped} scraped, {self.total_targets} targets, "
                    f"{self.total_people} people in {elapsed:.0f}s")
        return self._build_result(elapsed)

    async def _load_existing_companies(self) -> List[DiscoveredCompany]:
        """Load companies for this run that haven't been fully processed yet."""
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

        # Fallback: already scraped but not classified — feed to classify queue
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

    # ── Apollo page fetching + streaming workers ──

    MAX_PHASE2_PAGES = 200  # Safety cap — max pages total across all strategies
    EXHAUSTION_THRESHOLD = 20  # Pages with 0 new targets before switching/regenerating
    MAX_KEYWORD_REGENERATIONS = 5  # Stop pipeline after this many regenerations with no results

    async def _feed_apollo_pages(self, filters: Dict):
        """Fetch Apollo pages until KPI met or exhausted. Switches strategy on exhaustion."""
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

        # Build primary + backlog filter sets for exhaustion-based switching
        strategies = self._build_strategies(filters)
        per_page = filters.get("per_page", 100)

        productive_pages = 0  # Pages that found new companies (global safety cap)
        all_tried_keywords = set()  # Track ALL keywords across all strategies/regenerations

        for strategy_name, strategy_filters in strategies:
            if self._kpi_met or self._stop:
                break

            # Each strategy gets its own regeneration budget
            keyword_regenerations = 0
            consecutive_empty = 0

            # Track initial keywords
            all_tried_keywords.update(k.lower() for k in strategy_filters.get("q_organization_keyword_tags", []))

            # Start from where tam_gather left off for primary, page 1 for backlog
            page = (self._tam_pages + 1) if strategy_name == "primary" else 1

            logger.info(f"Phase 2 [{strategy_name}]: starting from page {page}")

            while productive_pages < self.MAX_PHASE2_PAGES:
                if self._kpi_met or self._stop:
                    break

                # Fetch up to 10 pages in PARALLEL for speed
                batch_size = min(10, self.MAX_PHASE2_PAGES - productive_pages)
                page_results = await self._fetch_pages_parallel(
                    adapter, strategy_filters, per_page, page, batch_size
                )

                batch_new_total = 0
                should_regen = False
                should_break = False

                for page_num, results in page_results:
                    if self._kpi_met or self._stop:
                        break
                    if results is None:
                        consecutive_empty += 1
                    else:
                        self.pages_fetched += 1
                        new_count = await self._ingest_page_results(results)
                        batch_new_total += new_count

                        if new_count == 0:
                            consecutive_empty += 1
                        else:
                            consecutive_empty = 0
                            productive_pages += 1

                    if consecutive_empty >= self.EXHAUSTION_THRESHOLD:
                        should_regen = True
                        break

                logger.info(f"Phase 2 [{strategy_name}] pages {page}-{page + batch_size - 1}: "
                           f"+{batch_new_total} new, {self.total_companies} total, "
                           f"{self.total_people} people")

                # Handle exhaustion → regenerate keywords
                if should_regen:
                    keyword_regenerations += 1
                    if keyword_regenerations >= self.MAX_KEYWORD_REGENERATIONS:
                        logger.info(f"Phase 2 [{strategy_name}]: {keyword_regenerations} regenerations "
                                   f"exhausted. Switching strategy.")
                        break

                    logger.info(f"Phase 2 [{strategy_name}]: {consecutive_empty} empty pages. "
                               f"Regenerating keywords ({keyword_regenerations}/{self.MAX_KEYWORD_REGENERATIONS})")
                    new_keywords = await self._regenerate_keywords(strategy_filters, all_tried_keywords)
                    if new_keywords:
                        all_tried_keywords.update(k.lower() for k in new_keywords)
                        strategy_filters["q_organization_keyword_tags"] = new_keywords
                        strategy_filters.pop("organization_industry_tag_ids", None)
                        consecutive_empty = 0
                        page = 1  # Restart with new keywords
                        await self._persist_progress()
                        continue
                    else:
                        logger.info(f"Phase 2 [{strategy_name}]: regeneration returned nothing. Switching.")
                        break

                await self._persist_progress()
                page += batch_size

    async def _fetch_pages_parallel(self, adapter, filters: Dict, per_page: int,
                                     start_page: int, count: int) -> list:
        """Fetch up to `count` Apollo pages in parallel. Returns [(page_num, results_or_None)]."""
        async def fetch_one(page_num):
            try:
                f = dict(filters)
                f["page"] = page_num
                f["max_pages"] = 1
                f["per_page"] = per_page
                results = await adapter.gather(f)
                return (page_num, results)
            except Exception as e:
                logger.warning(f"Apollo page {page_num} failed: {e}")
                return (page_num, None)

        tasks = [fetch_one(start_page + i) for i in range(count)]
        results = await asyncio.gather(*tasks)
        # Return sorted by page number to maintain order for sequential ingestion
        return sorted(results, key=lambda x: x[0])

    async def _regenerate_keywords(self, current_filters: Dict, all_tried: Set[str]) -> Optional[list]:
        """Generate fresh keywords when current ones are exhausted.

        Args:
            current_filters: Current strategy filters
            all_tried: ALL keywords tried across ALL strategies and regenerations (lowercase)
        """
        try:
            project = await self.session.get(Project, self.run.project_id)
            if not project:
                return None

            old_keywords = list(all_tried)
            query = project.target_segments or ", ".join(list(all_tried)[:5])
            offer = project.sender_company or ""

            from app.services.user_context import UserServiceContext
            user_id_str = self.run.triggered_by.split(":")[-1] if self.run.triggered_by else "0"
            try:
                user_id_int = int(user_id_str)
            except ValueError:
                user_id_int = 0
            ctx = UserServiceContext(user_id_int, self.session)
            openai_key = await ctx.get_key("openai")
            if not openai_key:
                return None

            import httpx, json
            prompt = (
                f"I'm searching Apollo.io for: {query}\n"
                f"Our product: {offer}\n\n"
                f"ALL these keywords have been tried and exhausted ({len(old_keywords)} total):\n"
                f"{json.dumps(old_keywords[:100])}\n\n"
                f"Generate 20-30 COMPLETELY NEW keyword variations.\n"
                f"Think creatively: synonyms, adjacent niches, specific product/service names,\n"
                f"alternate phrasings, industry jargon, related technologies.\n"
                f"Do NOT repeat ANY of the exhausted keywords above.\n\n"
                f"Return ONLY a JSON array of strings: [\"keyword1\", \"keyword2\", ...]"
            )
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 1000, "temperature": 0.7},
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                new_keywords = json.loads(content)
                # Filter out ALL previously tried keywords
                fresh = [k for k in new_keywords if k.lower() not in all_tried]
                logger.info(f"Regenerated {len(fresh)} fresh keywords ({len(all_tried)} previously tried)")
                return fresh if fresh else None
        except Exception as e:
            logger.warning(f"Keyword regeneration failed: {e}")
            return None

    def _build_strategies(self, filters: Dict) -> list:
        """Build primary + backlog filter strategies for exhaustion-based switching."""
        strategies = [("primary", dict(filters))]

        strategy = filters.get("filter_strategy", "keywords_only")
        has_industry = bool(filters.get("organization_industry_tag_ids"))
        has_keywords = bool(filters.get("q_organization_keyword_tags"))

        if strategy == "industry_first" and has_keywords:
            # Backlog: keywords only (drop industry tags)
            backlog = dict(filters)
            backlog.pop("organization_industry_tag_ids", None)
            strategies.append(("backlog_keywords", backlog))
        elif strategy == "keywords_first" and has_industry:
            # Backlog: industry only (drop keywords)
            backlog = dict(filters)
            backlog.pop("q_organization_keyword_tags", None)
            strategies.append(("backlog_industry", backlog))

        return strategies

    async def _ingest_page_results(self, results) -> int:
        """Ingest Apollo page results: dedup, create companies, queue for scraping. Returns new count."""
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
            await self.session.flush()
            for dc in page_batch:
                link = CompanySourceLink(
                    discovered_company_id=dc.id,
                    gathering_run_id=self.run.id,
                )
                self.session.add(link)
                self.total_companies += 1
                await self.scrape_queue.put(dc)

        return len(page_batch)

    async def _scraper_worker(self):
        """Streaming scrape worker — 100 concurrent. Own session for DB writes."""
        from app.db import async_session_maker
        sem = asyncio.Semaphore(100)

        async def scrape_one(dc):
            async with sem:
                try:
                    result = await self._scraper.scrape_website(f"https://{dc.domain}")
                    if result.get("success"):
                        text = result["text"][:50000]
                        # Write to DB with own session (no conflicts)
                        async with async_session_maker() as ws:
                            await ws.execute(
                                select(DiscoveredCompany).where(DiscoveredCompany.id == dc.id)
                            )  # load into session
                            from sqlalchemy import update
                            await ws.execute(
                                update(DiscoveredCompany).where(DiscoveredCompany.id == dc.id).values(
                                    scraped_text=text,
                                    scraped_at=datetime.now(timezone.utc),
                                    status="scraped",
                                )
                            )
                            await ws.commit()
                        dc.scraped_text = text  # keep in memory for classifier
                        dc.status = "scraped"
                        self.total_scraped += 1
                        await self.classify_queue.put(dc)
                    else:
                        async with async_session_maker() as ws:
                            from sqlalchemy import update
                            await ws.execute(update(DiscoveredCompany).where(DiscoveredCompany.id == dc.id).values(status="scrape_failed"))
                            await ws.commit()
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
        """Streaming classify worker — 100 concurrent. Own session for DB writes."""
        from app.db import async_session_maker
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

                        is_target = parsed.get("is_target", False)
                        segment = parsed.get("segment", "")
                        reasoning = parsed.get("reasoning", "")
                        status = "target" if is_target else "rejected"

                        # Write to DB with own session
                        async with async_session_maker() as ws:
                            from sqlalchemy import update
                            await ws.execute(
                                update(DiscoveredCompany).where(DiscoveredCompany.id == dc.id).values(
                                    is_target=is_target, analysis_segment=segment,
                                    analysis_reasoning=reasoning, status=status,
                                )
                            )
                            await ws.commit()

                        dc.is_target = is_target
                        dc.analysis_segment = segment
                        dc.status = status
                        self.total_classified += 1
                        if is_target:
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
        """Streaming people extraction — 20 concurrent. Own session for DB writes."""
        from app.db import async_session_maker
        if not self.apollo:
            return
        sem = asyncio.Semaphore(20)

        async def extract_one(dc):
            if self._kpi_met:
                return
            async with sem:
                try:
                    people = await self.apollo.enrich_by_domain(
                        dc.domain, limit=self.max_per_company,
                        titles=self._person_titles,
                    )
                    if not people:
                        return
                    # Write contacts to DB with own session
                    async with async_session_maker() as ws:
                        for person in people:
                            ws.add(ExtractedContact(
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
                        await ws.commit()
                    # Update progress with own session
                    self.run.credits_used = (self.run.credits_used or 0) + len(people)
                    await self._persist_progress()
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

    # ── Helpers ──

    async def _persist_progress(self):
        """Write counters to DB for frontend polling. Uses own session."""
        try:
            from app.db import async_session_maker
            from sqlalchemy import update
            async with async_session_maker() as ws:
                await ws.execute(
                    update(GatheringRun).where(GatheringRun.id == self.run.id).values(
                        new_companies_count=self.total_companies,
                        pages_fetched=self._tam_pages + self.pages_fetched,
                        total_targets_found=self.total_targets,
                        total_people_found=self.total_people,
                        credits_used=self.run.credits_used or 0,
                    )
                )
                await ws.commit()
        except Exception as e:
            logger.debug(f"Progress persist failed: {e}")

    def _build_result(self, elapsed: float) -> Dict:
        total_pages = self._tam_pages + self.pages_fetched
        target_rate = round(self.total_targets / max(self.total_classified, 1) * 100)
        scrape_rate = round(self.total_scraped / max(self.total_companies, 1) * 100)

        issues = []
        if not self._kpi_met:
            if self.total_people == 0:
                issues.append("No contacts found — check filters and target segments")
            elif self.total_people < self.target_count:
                remaining = self.target_count - self.total_people
                issues.append(f"Only {self.total_people}/{self.target_count} contacts found ({remaining} short)")
            if self.total_companies > 0 and target_rate < 20:
                issues.append(f"Low target rate ({target_rate}%) — keywords may be too broad")
            if self.total_companies > 0 and scrape_rate < 30:
                issues.append(f"Low scrape rate ({scrape_rate}%) — many websites unreachable")
            if total_pages > 0 and self.pages_fetched > 0:
                issues.append(f"Apollo exhausted after {total_pages} pages — broaden location or add keywords")
            elif total_pages > 0 and self.pages_fetched == 0 and not self._kpi_met:
                issues.append(f"Not enough companies from {total_pages} pages — try broader filters")

        if self._kpi_met:
            msg = (f"Pipeline complete: {self.total_targets} targets, "
                   f"{self.total_people}/{self.target_count} people "
                   f"in {elapsed:.0f}s ({total_pages} pages, {self.run.credits_used or 0} credits)")
        else:
            msg = (f"Pipeline stopped: {self.total_people}/{self.target_count} people "
                   f"({self.total_targets} targets, {target_rate}% target rate). "
                   + (f"Sending {self.total_people} gathered contacts to SmartLead."
                      if self.total_people > 0 else "No contacts to send."))

        return {
            "status": "completed" if self._kpi_met else "insufficient",
            "kpi_met": self._kpi_met,
            "total_companies": self.total_companies,
            "total_scraped": self.total_scraped,
            "total_classified": self.total_classified,
            "total_targets": self.total_targets,
            "total_people": self.total_people,
            "pages_fetched": total_pages,
            "elapsed_seconds": round(elapsed, 1),
            "credits_used": self.run.credits_used or 0,
            "target_rate_pct": target_rate,
            "scrape_rate_pct": scrape_rate,
            "issues": issues,
            "message": msg,
        }
