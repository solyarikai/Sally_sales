"""Streaming Pipeline — SINGLE MODE, every company flows through immediately.

Architecture:
  scrape_queue → Scraper (100 concurrent) → classify_queue → Classifier (100 concurrent) → people_queue → People (20 concurrent)

  1. Workers start FIRST (scraper, classifier, people)
  2. Existing companies (from tam_gather probe+confirm) fed to scrape_queue — flow immediately
  3. If KPI not met: Apollo pages fetched in PARALLEL batches of 10 → results fed to same scrape_queue
  4. Exhaustion: 10 consecutive empty pages (Apollo-raw) → regenerate keywords via GPT (up to 5 cycles)
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
try:
    from app.models.project import Project
except ImportError:
    from app.models.contact import Project

logger = logging.getLogger(__name__)

DEFAULT_TARGET_COUNT = 100
DEFAULT_CONTACTS_PER_COMPANY = 3


class StreamingPipeline:
    """Streaming pipeline — each company flows through all phases immediately."""

    def __init__(self, session: AsyncSession, run: GatheringRun,
                 openai_key: str, apollo_service=None, apify_proxy: Optional[str] = None):
        # NOTE: session stored for backward compat but NEVER used — all ops use own sessions
        self.run = run
        self.openai_key = openai_key
        self.apollo = apollo_service
        # Pass OpenAI key to Apollo for GPT-powered role filtering
        if apollo_service and openai_key:
            apollo_service._openai_key = openai_key
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
        self.apollo_total_entries = 0  # Total companies in Apollo matching filters

        # Queues (for streaming phase only — Apollo page discovery)
        self.scrape_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.classify_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.people_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # State
        self._kpi_met = False
        self._kpi_met_at: Optional[float] = None
        self._stop = False
        self._shutdown = asyncio.Event()  # Set on KPI met — unblocks all queue.put() calls
        self._domains_seen: Set[str] = set()
        self._started_at = time.time()
        self._tam_pages = run.pages_fetched or 0  # Pages already consumed by tam_gather
        self._level_stats: Dict[str, Dict] = {}  # Track pages/companies per cascade level

        # Shared services (initialized once, reused across phases)
        self._scraper = None
        self._offer_text = None
        self._person_titles = None

    async def _init_services(self):
        """Initialize shared services once. Own session — no shared state."""
        from app.services.scraper_service import ScraperService
        from app.db import async_session_maker
        try:
            self._scraper = ScraperService(apify_proxy_password=self.apify_proxy)
        except TypeError:
            self._scraper = ScraperService()  # Server version takes no args

        async with async_session_maker() as ws:
            project = await ws.get(Project, self.run.project_id)
            self._offer_text = project.target_segments if project else ""
            self._segments = []
            self._person_titles = None
            self._person_exclude_titles = None

            if project and project.offer_summary and isinstance(project.offer_summary, dict):
                offer = project.offer_summary
                target_roles = offer.get("target_roles", {})
                if target_roles.get("titles"):
                    self._person_titles = target_roles["titles"]
                # Negative role list from document or defaults
                if target_roles.get("exclude_titles"):
                    self._person_exclude_titles = target_roles["exclude_titles"]
                # Segments from document extraction
                segments = offer.get("segments", [])
                if segments:
                    self._segments = [s.get("name", "") for s in segments if s.get("name")]
                # Load geo filters from document extraction (ALWAYS applied, never dropped)
                apollo_filters = offer.get("apollo_filters", {})
                self._project_locations = apollo_filters.get("locations", [])
                self._project_employee_range = apollo_filters.get("employee_range")
                # Load exclusion list from document for Agent #2
                if offer.get("exclusion_list"):
                    self._exclusion_list = offer["exclusion_list"]
                # Use stored classification prompt if available
                if offer.get("classification_prompt"):
                    self._classification_prompt = offer["classification_prompt"]

            # Generate classification prompt if not stored
            if not getattr(self, "_classification_prompt", None):
                # If document has exclusion list → use Agent #2 to generate from it
                if getattr(self, '_exclusion_list', None):
                    try:
                        self._classification_prompt = await self._generate_classification_prompt()
                    except Exception:
                        self._classification_prompt = self._build_via_negativa_prompt()
                else:
                    # No exclusion list from document → use minimal via negativa
                    self._classification_prompt = self._build_via_negativa_prompt()

    def _build_via_negativa_prompt(self) -> str:
        """Build via negativa classification prompt — dynamic from project context.

        Uses offer text, segments, and document exclusion list.
        No generic hardcoded categories — exclusions derived from context.
        """
        segments_line = ""
        if self._segments:
            segments_line = (
                f"\nTARGET SEGMENTS: {', '.join(self._segments)}\n"
                f"If target, assign ONE of these segments.\n"
            )

        # Include document's exclusion list if available
        exclusion_rules = ""
        if getattr(self, '_exclusion_list', None):
            rules = [f"- {ex.get('type','')}: {ex.get('reason','')}" for ex in self._exclusion_list]
            exclusion_rules = "\nDOCUMENT EXCLUSIONS:\n" + "\n".join(rules) + "\n"

        return (
            f"You classify companies as potential customers using VIA NEGATIVA.\n\n"
            f"WE SELL: {self._offer_text}\n"
            f"{segments_line}"
            f"{exclusion_rules}\n"
            f"EXCLUDE (is_target=false) if the company would clearly NOT buy what we sell.\n"
            f"INCLUDE (is_target=true) if the company could realistically be a customer.\n"
            f"When in doubt → include.\n\n"
            f"Return JSON: {{\"is_target\": true/false, \"segment\": \"CAPS_LABEL\", \"reasoning\": \"1 line\"}}"
        )

    async def _generate_classification_prompt(self) -> str:
        """Agent #2: Generate optimal classification prompt from project context.

        Reads offer, segments, target audience, AND document exclusion list
        → generates exclusion rules specific to THIS campaign. No hardcoded categories.
        """
        import httpx, json

        # Get exclusion list from project offer_summary if available
        exclusion_context = ""
        if hasattr(self, '_exclusion_list') and self._exclusion_list:
            exclusion_lines = [f"- {ex.get('type','')}: {ex.get('reason','')}" for ex in self._exclusion_list]
            exclusion_context = f"\nDOCUMENT EXCLUSION LIST (from user's strategy doc):\n" + "\n".join(exclusion_lines) + "\n"

        meta_prompt = (
            f"Generate a classification prompt for filtering companies in a lead generation pipeline.\n\n"
            f"CONTEXT:\n"
            f"We sell: {self._offer_text}\n"
            f"Target segments: {', '.join(self._segments) if self._segments else 'general'}\n"
            f"{exclusion_context}\n"
            f"Generate a VIA NEGATIVA classification prompt that:\n"
            f"1. Lists 5-8 EXCLUSION rules specific to this campaign (what types of companies are NOT potential buyers)\n"
            f"2. INCORPORATE the document's exclusion list above (if provided) into the rules\n"
            f"3. Lists 3-4 INCLUSION rules (what makes a company a good target)\n"
            f"4. Uses the offer context to derive exclusions — don't use generic rules\n"
            f"5. Ends with: Return JSON: {{\"is_target\": true/false, \"segment\": \"CAPS_LABEL\", \"reasoning\": \"1 line\"}}\n\n"
            f"Return ONLY the prompt text, no explanation."
        )

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": meta_prompt}],
                          "max_tokens": 1000, "temperature": 0},
                )
                data = resp.json()
                generated = data["choices"][0]["message"]["content"].strip()
                if generated.startswith("```"):
                    generated = generated.split("\n", 1)[1].rsplit("```", 1)[0]
                logger.info(f"Agent #2 generated classification prompt: {len(generated)} chars")
                return generated
        except Exception as e:
            logger.warning(f"Agent #2 prompt generation failed: {e}")
            return self._build_via_negativa_prompt()


    async def _safe_put(self, queue: asyncio.Queue, item) -> bool:
        """Put item into queue, but abort immediately if shutdown is triggered.

        Returns True if item was placed, False if shutdown fired first.
        Prevents the classic producer-consumer deadlock: when KPI is met the
        downstream consumer stops, queues fill up, upstream producers block on
        put() forever, and the finally-block that sends poison pills never runs.
        """
        if self._shutdown.is_set():
            return False
        # Race: wait for EITHER queue space OR shutdown signal
        put_task = asyncio.create_task(queue.put(item))
        shutdown_task = asyncio.create_task(self._shutdown.wait())
        done, pending = await asyncio.wait(
            {put_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        if put_task in done:
            return True
        return False

    def _trigger_shutdown(self):
        """Signal all producers to stop blocking on queue.put().

        Called when KPI is met. Sets the shutdown event so every _safe_put
        and every worker loop breaks immediately. No more deadlocks.
        """
        self._kpi_met = True
        self._kpi_met_at = time.time()
        self._shutdown.set()
        logger.info(f"SHUTDOWN triggered: {self.total_people} people >= {self.target_count}")

    async def run_until_kpi(self, filters: Dict) -> Dict:
        """Main entry — SINGLE STREAMING MODE for everything.

        All companies (existing + new Apollo) flow through the same queue workers:
          scrape_queue → scraper (100) → classify_queue → classifier (100) → people_queue → people (20)

        Each company flows immediately — no waiting for batches.
        """
        # Use own session for all run updates — never share with workers
        from app.db import async_session_maker as _asm
        from sqlalchemy import update as _upd
        async with _asm() as _ws:
            await _ws.execute(_upd(GatheringRun).where(GatheringRun.id == self.run.id).values(started_at=datetime.now(timezone.utc)))
            await _ws.commit()
        await self._init_services()

        logger.info(f"Streaming pipeline started: target={self.target_count} people, "
                     f"max {self.max_per_company}/company")

        # Start streaming workers — they run the ENTIRE time
        workers = [
            asyncio.create_task(self._scraper_worker()),
            asyncio.create_task(self._classifier_worker()),
            asyncio.create_task(self._people_worker()),
        ]

        # Feed existing companies (probe 100) → scrape starts INSTANTLY
        existing = await self._load_existing_companies()
        if existing:
            logger.info(f"Feeding {len(existing)} existing companies to streaming queue")
            self.total_companies = len(existing)
            for dc in existing:
                self._domains_seen.add(dc.domain)
                if not await self._safe_put(self.scrape_queue, dc):
                    break

        # Apollo pages run IN PARALLEL with scraping (not blocking)
        # Workers are ALREADY processing probe companies while Apollo fetches pages 2-10+
        try:
            if not self._shutdown.is_set():
                await self._feed_apollo_pages(filters)
        except Exception as e:
            logger.error(f"Apollo page fetching failed: {e}")
        finally:
            # Drain queues first so poison pills aren't blocked behind full queues
            for q in (self.scrape_queue, self.classify_queue, self.people_queue):
                while not q.empty():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            # ALWAYS send poison pills to ALL queues — workers must stop
            self.scrape_queue.put_nowait(None)
            self.classify_queue.put_nowait(None)
            self.people_queue.put_nowait(None)

        await asyncio.gather(*workers, return_exceptions=True)

        # Final progress persist
        await self._persist_progress()

        # Use KPI-met timestamp for elapsed (frozen at the moment KPI was hit)
        if self._kpi_met_at:
            elapsed = self._kpi_met_at - self._started_at
        else:
            elapsed = time.time() - self._started_at
        logger.info(f"Pipeline done: {self.total_scraped} scraped, {self.total_targets} targets, "
                    f"{self.total_people} people in {elapsed:.0f}s")
        return self._build_result(elapsed)

    async def _load_existing_companies(self) -> List[DiscoveredCompany]:
        """Load companies for this run. Uses own session, returns DETACHED objects."""
        from app.db import async_session_maker
        async with async_session_maker() as ws:
            result = await ws.execute(
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
            companies = result.scalars().all()
            if companies:
                from types import SimpleNamespace
                return [SimpleNamespace(
                    id=dc.id, domain=dc.domain, name=dc.name, industry=dc.industry,
                    employee_count=dc.employee_count, country=dc.country, city=dc.city,
                    project_id=dc.project_id, company_id=dc.company_id,
                    scraped_text=dc.scraped_text, status=dc.status, is_target=dc.is_target,
                    analysis_segment=dc.analysis_segment, analysis_reasoning=dc.analysis_reasoning,
                ) for dc in companies]

            result = await ws.execute(
                select(DiscoveredCompany)
                .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
                .where(
                    CompanySourceLink.gathering_run_id == self.run.id,
                    DiscoveredCompany.scraped_text.isnot(None),
                    DiscoveredCompany.is_target.is_(None),
                )
            )
            companies = result.scalars().all()
            from types import SimpleNamespace
            return [SimpleNamespace(
                id=dc.id, domain=dc.domain, name=dc.name, industry=dc.industry,
                employee_count=dc.employee_count, country=dc.country, city=dc.city,
                project_id=dc.project_id, company_id=dc.company_id,
                scraped_text=dc.scraped_text, status=dc.status, is_target=dc.is_target,
                analysis_segment=dc.analysis_segment, analysis_reasoning=dc.analysis_reasoning,
            ) for dc in companies]

    # ── Apollo page fetching + streaming workers ──

    # KPIs and limits
    MAX_PAGES_PER_KEYWORD = 5     # Max pages per single keyword/industry request
    MAX_KEYWORD_REGENERATIONS = 5  # Regen cycles with different angles
    LOW_YIELD_THRESHOLD = 10      # If keyword returns <10 companies on page 1, stop
    MAX_TOTAL_CREDITS = 200       # Safety cap on total Apollo credits

    async def _feed_apollo_pages(self, filters: Dict):
        """1-filter-per-request parallel gathering with lazy keyword batching.

        Each keyword/industry runs as its own parallel Apollo request (1 filter per call).
        Verified: 1 keyword per request finds 7.4x more companies than all-together.
        Verified: 1 industry per request finds 3.7x more companies than all-together.
        """
        if not self.apollo:
            logger.warning("No Apollo service — cannot feed pages")
            return

        # Pre-load domains from THIS RUN
        from app.db import async_session_maker as _asm
        async with _asm() as _ws:
            existing_result = await _ws.execute(
                select(DiscoveredCompany.domain)
                .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
                .where(CompanySourceLink.gathering_run_id == self.run.id)
            )
            self._domains_seen.update(r[0] for r in existing_result.all())
            logger.info(f"Pre-loaded {len(self._domains_seen)} domains from current run")

        per_page = filters.get("per_page", 100)

        # AUTO-EXPAND keywords
        base_kw = (filters.get("q_organization_keyword_tags") or
                   filters.get("mapping_details", {}).get("keywords_selected", []))
        if base_kw and len(base_kw) < 60:
            expanded = await self._expand_keywords(base_kw)
            if expanded and len(expanded) > len(base_kw):
                filters["q_organization_keyword_tags"] = expanded
                logger.info(f"Keywords expanded: {len(base_kw)} → {len(expanded)}")

        # HARD FILTERS from project — ALWAYS applied
        if not filters.get("organization_locations") and getattr(self, '_project_locations', None):
            filters["organization_locations"] = self._project_locations
        if not filters.get("organization_num_employees_ranges") and getattr(self, '_project_employee_range', None):
            filters["organization_num_employees_ranges"] = [self._project_employee_range]

        # Extract all keywords and industry_tag_ids
        all_keywords = list(filters.get("q_organization_keyword_tags") or
                           filters.get("mapping_details", {}).get("keywords_selected", []))
        all_industry_ids = list(filters.get("organization_industry_tag_ids") or
                               filters.get("mapping_details", {}).get("industry_tag_ids", []))
        funding_stages = (filters.get("organization_latest_funding_stage_cd") or
                         filters.get("mapping_details", {}).get("funding_stages"))

        # Base filters (geo + size) — shared by all requests
        base_filters = {}
        if filters.get("organization_locations"):
            base_filters["organization_locations"] = filters["organization_locations"]
        if filters.get("organization_num_employees_ranges"):
            base_filters["organization_num_employees_ranges"] = filters["organization_num_employees_ranges"]

        # Tracking
        self._keyword_stats = {}
        self._industry_stats = {}
        self._search_requests = []
        all_tried_keywords = set(k.lower() for k in all_keywords)
        keyword_cursor = 0

        logger.info(f"Pipeline: {len(all_keywords)} keywords, {len(all_industry_ids)} industries, "
                    f"funding={'yes' if funding_stages else 'no'}")

        # ── ROUND-BASED GATHERING ──
        round_num = 0
        while not self._shutdown.is_set() and not self._stop:
            round_num += 1
            round_start_companies = self.total_companies
            streams = []

            # Industry streams — all industries in round 1 (typically 2-3)
            if round_num == 1 and all_industry_ids:
                for tag_id in all_industry_ids:
                    ind_filter = dict(base_filters)
                    ind_filter["organization_industry_tag_ids"] = [tag_id]
                    label = f"R{round_num}_ind_{tag_id[:8]}"
                    if funding_stages:
                        funded_f = dict(ind_filter)
                        funded_f["organization_latest_funding_stage_cd"] = funding_stages
                        streams.append(self._run_single_filter(
                            funded_f, per_page, f"{label}_funded",
                            filter_type="industry", filter_value=tag_id, round_num=round_num, funded=True))
                    streams.append(self._run_single_filter(
                        ind_filter, per_page, label,
                        filter_type="industry", filter_value=tag_id, round_num=round_num, funded=False))

            # Keyword streams — 1 keyword per request, all remaining in parallel
            remaining = all_keywords[keyword_cursor:]
            if remaining:
                for kw in remaining:
                    kw_filter = dict(base_filters)
                    kw_filter["q_organization_keyword_tags"] = [kw]
                    label = f"R{round_num}_kw_{kw[:20].replace(' ', '_')}"
                    if funding_stages:
                        funded_f = dict(kw_filter)
                        funded_f["organization_latest_funding_stage_cd"] = funding_stages
                        streams.append(self._run_single_filter(
                            funded_f, per_page, f"{label}_funded",
                            filter_type="keyword", filter_value=kw, round_num=round_num, funded=True))
                    streams.append(self._run_single_filter(
                        kw_filter, per_page, label,
                        filter_type="keyword", filter_value=kw, round_num=round_num, funded=False))
                keyword_cursor += len(remaining)

            if not streams:
                logger.info(f"Round {round_num}: no more filters to try")
                break

            logger.info(f"Round {round_num}: launching {len(streams)} parallel streams")
            await asyncio.gather(*streams)

            round_new = self.total_companies - round_start_companies
            logger.info(f"Round {round_num} done: +{round_new} companies "
                        f"(total: {self.total_companies}, targets: {self.total_targets}, people: {self.total_people})")

            # Wait for processing to catch up
            await self._wait_for_processing()

            if self._shutdown.is_set() or self._kpi_met:
                logger.info(f"KPI met after round {round_num}")
                break

            # Keyword regeneration if all exhausted
            if keyword_cursor >= len(all_keywords) and round_num <= self.MAX_KEYWORD_REGENERATIONS:
                new_kw = await self._regenerate_keywords(filters, all_tried_keywords, cycle_num=round_num)
                if new_kw:
                    all_keywords.extend(new_kw)
                    all_tried_keywords.update(k.lower() for k in new_kw)
                    logger.info(f"Regenerated {len(new_kw)} keywords for round {round_num + 1}")
                else:
                    logger.info("No more keywords to regenerate")
                    break
            elif keyword_cursor >= len(all_keywords):
                logger.info(f"All keywords exhausted after round {round_num}")
                break

        # Persist tracking stats
        await self._persist_tracking_stats()

        if not self._kpi_met:
            logger.info(f"Gathering exhausted: {self.pages_fetched} pages, "
                       f"{self.total_companies} companies, {self.total_people} people")

    async def _run_single_filter(self, filters: Dict, per_page: int, label: str,
                                  filter_type: str, filter_value: str,
                                  round_num: int, funded: bool) -> None:
        """Run a single keyword or industry_tag_id across pages. Stops on low yield or KPI."""
        pages_fetched = 0
        raw_total = 0
        new_unique = 0

        for page in range(1, self.MAX_PAGES_PER_KEYWORD + 1):
            if self._shutdown.is_set() or self._stop:
                break
            page_counts = await self._fetch_pages_parallel(filters, per_page, page, 1)
            for page_num, page_new, apollo_raw in page_counts:
                pages_fetched += 1
                self.pages_fetched += 1
                raw_total += apollo_raw
                new_unique += max(0, page_new)
                if apollo_raw < self.LOW_YIELD_THRESHOLD and page == 1:
                    logger.debug(f"[{label}] low yield: {apollo_raw} on page 1")
                    break
                if apollo_raw <= 0:
                    break
            await self._persist_progress()

        # Track stats
        stat_dict = self._keyword_stats if filter_type == "keyword" else self._industry_stats
        stat_key = filter_value
        if stat_key not in stat_dict:
            stat_dict[stat_key] = {"pages_fetched": 0, "raw_companies": 0, "new_unique": 0,
                                    "credits_used": 0, "funded": funded, "round": round_num}
        stat_dict[stat_key]["pages_fetched"] += pages_fetched
        stat_dict[stat_key]["raw_companies"] += raw_total
        stat_dict[stat_key]["new_unique"] += new_unique
        stat_dict[stat_key]["credits_used"] += pages_fetched

        self._search_requests.append({
            "type": filter_type, "filter_value": filter_value,
            "round": round_num, "funded": funded,
            "pages": pages_fetched, "raw": raw_total, "new_unique": new_unique,
        })
        if new_unique > 0:
            logger.info(f"[{label}] {pages_fetched}p, {raw_total} raw, {new_unique} new")

    async def _wait_for_processing(self):
        """Wait for scrape + classify queues to drain."""
        max_wait = 300
        waited = 0
        while waited < max_wait:
            if self._shutdown.is_set():
                return
            if self.scrape_queue.qsize() == 0 and self.classify_queue.qsize() == 0:
                await asyncio.sleep(2)
                return
            await asyncio.sleep(3)
            waited += 3
            if waited % 30 == 0:
                logger.info(f"Waiting: {self.scrape_queue.qsize()} scrape, {self.classify_queue.qsize()} classify")
        logger.warning(f"Processing wait timeout ({max_wait}s)")

    async def _persist_tracking_stats(self):
        """Save per-keyword/industry tracking stats to gathering_run."""
        try:
            from app.db import async_session_maker
            async with async_session_maker() as ws:
                run = await ws.get(GatheringRun, self.run.id)
                if run and run.filters:
                    f = dict(run.filters)
                    f["keyword_stats"] = getattr(self, '_keyword_stats', {})
                    f["industry_stats"] = getattr(self, '_industry_stats', {})
                    f["search_requests"] = getattr(self, '_search_requests', [])
                    f["pipeline_summary"] = {
                        "total_credits_used": self.run.credits_used or 0,
                        "total_unique_companies": self.total_companies,
                        "total_targets": self.total_targets,
                        "keywords_used": len(getattr(self, '_keyword_stats', {})),
                        "industries_used": len(getattr(self, '_industry_stats', {})),
                        "kpi_met": self._kpi_met,
                        "total_people": self.total_people,
                    }
                    run.filters = f
                    await ws.commit()
        except Exception as e:
            logger.debug(f"Tracking stats persist failed: {e}")

    async def _expand_keywords(self, base_keywords: list) -> list:
        """Auto-expand base keywords to 80-100 segment-specific ones using GPT.
        Called ONCE at pipeline start. Works for ANY industry — fintech, iGaming, fashion."""
        try:
            import httpx, json
            segments_text = ", ".join(self._segments) if self._segments else "general"
            offer_text = self._offer_text or "B2B lead generation"

            prompt = (
                f"You have {len(base_keywords)} base keywords for an Apollo.io company search:\n"
                f"{json.dumps(base_keywords)}\n\n"
                f"Target segments: {segments_text}\n"
                f"We sell: {offer_text}\n\n"
                f"EXPAND these into 80-100 SPECIFIC keywords. For each segment, add:\n"
                f"- Specific product/platform type names (e.g. 'payment gateway API', not 'payment solutions')\n"
                f"- Technology terms (e.g. 'PCI DSS', 'ISO 20022', 'open banking API')\n"
                f"- Use case phrases (e.g. 'merchant onboarding', 'instant settlements')\n"
                f"- Buyer search terms (e.g. 'KYC vendor', 'BaaS provider', 'card issuing platform')\n\n"
                f"Each keyword: 2-4 words, specific enough to find relevant B2B companies.\n"
                f"Include ALL original keywords plus 50-70 new ones.\n"
                f"Return ONLY a JSON array: [\"keyword1\", \"keyword2\", ...]"
            )

            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 2000, "temperature": 0.5},
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                expanded = json.loads(content)

                # Merge: keep all base + add new, dedup
                all_kw = list(base_keywords)
                seen = {k.lower() for k in base_keywords}
                for kw in expanded:
                    if kw.lower() not in seen:
                        all_kw.append(kw)
                        seen.add(kw.lower())

                logger.info(f"Keyword expansion: {len(base_keywords)} base → {len(all_kw)} total "
                           f"(+{len(all_kw) - len(base_keywords)} new)")
                return all_kw
        except Exception as e:
            logger.warning(f"Keyword expansion failed: {e}")
            return base_keywords

    async def _fetch_pages_parallel(self, filters: Dict, per_page: int,
                                     start_page: int, count: int) -> list:
        """Fetch `count` pages in parallel using self.apollo DIRECTLY.
        Feed companies to scrape_queue AS EACH PAGE ARRIVES.
        NEVER uses main app's GatheringService or adapter pattern."""
        results_list = []

        # Extract Apollo search params from filters
        keyword_tags = filters.get("q_organization_keyword_tags")
        industry_tag_ids = filters.get("organization_industry_tag_ids")
        locations = filters.get("organization_locations")
        num_employees = filters.get("organization_num_employees_ranges")
        funding_stages = filters.get("organization_latest_funding_stage_cd")

        async def fetch_and_feed(page_num):
            """Fetch one page via self.apollo and immediately feed to scrape queue."""
            try:
                data = await self.apollo.search_organizations(
                    keyword_tags=keyword_tags,
                    industry_tag_ids=industry_tag_ids,
                    locations=locations,
                    num_employees_ranges=num_employees,
                    latest_funding_stages=funding_stages,
                    page=page_num,
                    per_page=per_page,
                )
                orgs = (data or {}).get("organizations", [])
                # Capture total_entries from Apollo pagination (first page that returns it)
                pagination = (data or {}).get("pagination", {})
                total = pagination.get("total_entries", 0)
                if total and total > self.apollo_total_entries:
                    self.apollo_total_entries = total
                # Track Apollo search credit (1 credit per page)
                self.run.credits_used = (self.run.credits_used or 0) + 1
                # Convert to pipeline format
                results = []
                for org in orgs:
                    domain = org.get("primary_domain") or org.get("domain", "")
                    if domain:
                        if domain.startswith("http"):
                            from urllib.parse import urlparse
                            domain = urlparse(domain).hostname or domain
                        if domain.startswith("www."):
                            domain = domain[4:]
                        # Extract ALL useful fields from Apollo response
                        country = org.get("country") or org.get("organization_country")
                        city = org.get("city") or org.get("organization_city")
                        state = org.get("state") or org.get("organization_state")
                        emp = org.get("estimated_num_employees") or org.get("num_contacts")
                        city_full = f"{city}, {state}" if city and state else (city or state)
                        # Build full source_data from Apollo org (preserve all fields)
                        raw_org = {
                            "domain": domain.strip().lower(),
                            "name": org.get("name"),
                            "country": country, "city": city, "state": state,
                            "industry": org.get("industry"),
                            "employee_count": emp,
                            "employee_range": org.get("employee_range"),
                            "founded_year": org.get("founded_year"),
                            "linkedin_url": org.get("linkedin_url"),
                            "website_url": org.get("website_url"),
                            "phone": org.get("phone") or (org.get("primary_phone") or {}).get("number"),
                            "revenue": org.get("revenue") or org.get("estimated_annual_revenue"),
                            "revenue_raw": org.get("revenue_raw") or org.get("organization_revenue"),
                            "sic_codes": org.get("sic_codes"),
                            "naics_codes": org.get("naics_codes"),
                            "apollo_id": org.get("id"),
                            "num_contacts_in_apollo": org.get("num_contacts"),
                            "headcount_6m_growth": org.get("headcount_6m_growth"),
                            "headcount_12m_growth": org.get("headcount_12m_growth"),
                            "languages": org.get("languages"),
                        }
                        results.append({
                            "domain": domain.strip().lower(),
                            "name": org.get("name", domain),
                            "industry": org.get("industry"),
                            "employee_count": emp,
                            "country": country,
                            "city": city_full,
                            "_raw_org": raw_org,
                        })
                # Feed to scrape queue IMMEDIATELY
                apollo_raw = len(orgs)  # How many Apollo returned (before dedup)
                if results:
                    new_count = await self._ingest_page_results(results)
                    results_list.append((page_num, new_count, apollo_raw))
                else:
                    results_list.append((page_num, 0, apollo_raw))
            except Exception as e:
                logger.warning(f"Apollo page {page_num} failed: {e}")
                results_list.append((page_num, -1, 0))

        tasks = [fetch_and_feed(start_page + i) for i in range(count)]
        await asyncio.gather(*tasks)
        return sorted(results_list, key=lambda x: x[0])

    async def _regenerate_keywords(self, current_filters: Dict, all_tried: Set[str],
                                    cycle_num: int = 1) -> Optional[list]:
        """Generate fresh keywords using DIFFERENT ANGLES per cycle.

        Each cycle attacks from a different direction — not just synonyms:
          1: Specific product/platform names in the space
          2: Technology stack terms and standards
          3: Use cases and problems solved
          4: Buyer search language
          5: Adjacent niches and verticals
          6-10: Creative combinations of above
        """
        try:
            from app.db import async_session_maker
            async with async_session_maker() as ws:
                project = await ws.get(Project, self.run.project_id)
                if not project:
                    return None
                query = project.target_segments or ", ".join(list(all_tried)[:5])
                offer = self._offer_text or project.sender_company or ""

                from app.services.user_context import UserServiceContext
                user_id_str = self.run.triggered_by.split(":")[-1] if self.run.triggered_by else "0"
                try:
                    user_id_int = int(user_id_str)
                except ValueError:
                    user_id_int = 0
                ctx = UserServiceContext(user_id_int, ws)
                openai_key = await ctx.get_key("openai") or self.openai_key

            old_keywords = list(all_tried)
            if not openai_key:
                return None

            # Different expansion angle per cycle
            ANGLES = [
                "Generate SPECIFIC PRODUCT and PLATFORM NAMES that exist in this space. "
                "Think of real companies' product names, API names, platform brands.",
                "Generate TECHNOLOGY STACK terms — protocols, standards, certifications, "
                "technical specifications that companies in this space use on their websites.",
                "Generate USE CASE phrases — what problems do these companies solve? "
                "What do their customers search for when looking for solutions?",
                "Generate BUYER SEARCH LANGUAGE — how do procurement teams and CTOs "
                "search for vendors in this space? Think RFP language, comparison terms.",
                "Generate ADJACENT NICHE terms — related verticals, emerging sub-categories, "
                "crossover markets that overlap with this space.",
                "Generate INDUSTRY JARGON — insider terminology, acronyms, regulatory terms "
                "that ONLY companies in this space would use on their websites.",
                "Generate COMPETITOR and ALTERNATIVE keywords — terms like 'alternative to X', "
                "'X competitor', category leaders that define the space.",
                "Generate JOB POSTING keywords — what do companies in this space write in "
                "their job descriptions? Technical skills, team names, role-specific terms.",
                "Generate INVESTOR and FUNDING keywords — terms from pitch decks, "
                "funding announcements, market maps used by VCs in this space.",
                "Generate CONFERENCE and EVENT keywords — names of industry events, "
                "awards, publications, associations specific to this space.",
            ]

            angle_idx = (cycle_num - 1) % len(ANGLES)
            angle = ANGLES[angle_idx]

            import httpx, json
            prompt = (
                f"I'm searching Apollo.io for companies matching: {query}\n"
                f"We sell: {offer}\n\n"
                f"EXHAUSTED keywords ({len(old_keywords)} tried, DO NOT repeat ANY):\n"
                f"{json.dumps(old_keywords[:150])}\n\n"
                f"EXPANSION ANGLE for this cycle:\n{angle}\n\n"
                f"Generate 30-40 COMPLETELY NEW keywords from this angle.\n"
                f"Each keyword should be 2-4 words, specific enough to find relevant companies.\n"
                f"Return ONLY a JSON array: [\"keyword1\", \"keyword2\", ...]"
            )
            logger.info(f"Regen cycle {cycle_num} angle: {ANGLES[angle_idx][:60]}...")
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

    # _build_strategies REMOVED — replaced by 3-level cascade in _feed_apollo_pages

    async def _ingest_page_results(self, results) -> int:
        """Ingest Apollo page results. Own session — no conflicts with workers."""
        from app.db import async_session_maker
        page_companies = []
        for company_data in (results or []):
            if self._shutdown.is_set():
                break
            domain = company_data.get("domain", "").lower().strip()
            if not domain or domain in self._domains_seen:
                continue
            self._domains_seen.add(domain)
            page_companies.append(company_data)

        if not page_companies:
            return 0

        # Create or reuse companies — handles cross-run duplicates via upsert
        created_dcs = []
        async with async_session_maker() as ws:
            from sqlalchemy import text as sa_text
            for company_data in page_companies:
                domain = company_data.get("domain", "").lower().strip()
                # Check if company already exists for this project (from previous runs)
                existing = await ws.execute(
                    select(DiscoveredCompany).where(
                        DiscoveredCompany.project_id == self.run.project_id,
                        DiscoveredCompany.domain == domain,
                    )
                )
                dc = existing.scalars().first()
                if dc:
                    # Reuse existing company — update geo/industry from fresh Apollo data + reset classification
                    dc.is_target = None
                    dc.analysis_segment = None
                    dc.analysis_reasoning = None
                    dc.status = "new" if not dc.scraped_text else "scraped"
                    # Update company data from Apollo (may have been NULL before)
                    if company_data.get("country"):
                        dc.country = company_data["country"]
                    if company_data.get("city"):
                        dc.city = company_data["city"]
                    if company_data.get("industry"):
                        dc.industry = company_data["industry"]
                    if company_data.get("employee_count"):
                        dc.employee_count = company_data["employee_count"]
                    # Update source_data with full Apollo org
                    raw_org = company_data.get("_raw_org")
                    if raw_org:
                        dc.source_data = raw_org
                        if raw_org.get("linkedin_url") and not dc.linkedin_url:
                            dc.linkedin_url = raw_org["linkedin_url"]
                else:
                    raw_org = company_data.get("_raw_org", company_data)
                    dc = DiscoveredCompany(
                        project_id=self.run.project_id,
                        company_id=self.run.company_id,
                        domain=domain,
                        name=company_data.get("name"),
                        industry=company_data.get("industry"),
                        employee_count=company_data.get("employee_count"),
                        country=company_data.get("country"),
                        city=company_data.get("city"),
                        linkedin_url=raw_org.get("linkedin_url"),
                        website_url=raw_org.get("website_url"),
                        source_data=raw_org,
                    )
                    ws.add(dc)
            await ws.flush()

            # Re-query to get all company IDs (both new and reused)
            domain_list = [c.get("domain", "").lower().strip() for c in page_companies]
            r = await ws.execute(
                select(DiscoveredCompany).where(
                    DiscoveredCompany.project_id == self.run.project_id,
                    DiscoveredCompany.domain.in_(domain_list),
                )
            )
            all_dcs = r.scalars().all()
            for dc_obj in all_dcs:
                from types import SimpleNamespace
                dc = SimpleNamespace(
                    id=dc_obj.id, domain=dc_obj.domain, name=dc_obj.name,
                    industry=dc_obj.industry, employee_count=dc_obj.employee_count,
                    country=dc_obj.country, city=dc_obj.city,
                    project_id=self.run.project_id, company_id=self.run.company_id,
                    scraped_text=dc_obj.scraped_text, status=dc_obj.status,
                    is_target=dc_obj.is_target,
                    analysis_segment=dc_obj.analysis_segment,
                    analysis_reasoning=dc_obj.analysis_reasoning,
                )
                created_dcs.append(dc)
                # Link to current run (ON CONFLICT skip if already linked)
                try:
                    ws.add(CompanySourceLink(discovered_company_id=dc.id, gathering_run_id=self.run.id))
                    await ws.flush()
                except Exception:
                    await ws.rollback()
            await ws.commit()

        for dc in created_dcs:
            self.total_companies += 1
            if not await self._safe_put(self.scrape_queue, dc):
                break  # Shutdown triggered — stop feeding

        return len(created_dcs)

    async def _scraper_worker(self):
        """Streaming scrape worker — 100 concurrent. Own session for DB writes."""
        from app.db import async_session_maker
        sem = asyncio.Semaphore(100)

        async def scrape_one(dc):
            async with sem:
                if self._shutdown.is_set():
                    return
                try:
                    result = await self._scraper.scrape_website(f"https://{dc.domain}")
                    if self._shutdown.is_set():
                        return
                    if result.get("success"):
                        text = result["text"][:50000]
                        async with async_session_maker() as ws:
                            await ws.execute(
                                select(DiscoveredCompany).where(DiscoveredCompany.id == dc.id)
                            )
                            from sqlalchemy import update
                            await ws.execute(
                                update(DiscoveredCompany).where(DiscoveredCompany.id == dc.id).values(
                                    scraped_text=text,
                                    scraped_at=datetime.now(timezone.utc),
                                    status="scraped",
                                )
                            )
                            await ws.commit()
                        dc.scraped_text = text
                        dc.status = "scraped"
                        self.total_scraped += 1
                        await self._safe_put(self.classify_queue, dc)
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
            if self._shutdown.is_set():
                break
            tasks.append(asyncio.create_task(scrape_one(dc)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.classify_queue.put(None)

    async def _classifier_worker(self):
        """Streaming classify worker — 100 concurrent. One shared httpx client."""
        from app.db import async_session_maker
        import httpx
        import json
        sem = asyncio.Semaphore(100)
        client = httpx.AsyncClient(timeout=30)

        # Log the classification prompt ONCE so Prompts page can display it
        try:
            system_prompt = self._classification_prompt
            user_id_str = self.run.triggered_by.split(":")[-1] if self.run.triggered_by else "0"
            try:
                uid = int(user_id_str)
            except ValueError:
                uid = 1
            async with async_session_maker() as log_s:
                from sqlalchemy import text as sa_text
                await log_s.execute(
                    sa_text("INSERT INTO mcp_usage_logs (user_id, tool_name, action, metadata, created_at) VALUES (:uid, :tool, :action, :data::jsonb, now())"),
                    {"uid": uid, "tool": "analysis_prompt", "action": "classify", "data": json.dumps({"run_id": self.run.id, "prompt_text": system_prompt, "model": "gpt-4o-mini"})},
                )
                await log_s.commit()
        except Exception as e:
            logger.debug(f"Prompt logging failed: {e}")

        async def classify_one(dc):
            async with sem:
                if not dc.scraped_text or self._shutdown.is_set():
                    return
                try:
                    company_text = f"Company: {dc.name or dc.domain}\nDomain: {dc.domain}"
                    company_text += f"\n\nWebsite:\n{dc.scraped_text[:3000]}"

                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.openai_key}",
                                 "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": self._classification_prompt},
                                {"role": "user", "content": company_text},
                            ],
                            "max_tokens": 200, "temperature": 0.1,
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
                    confidence = parsed.get("confidence", "high")

                    # TWO-PASS: low/medium confidence → re-evaluate with gpt-4o
                    if confidence in ("low", "medium"):
                        try:
                            resp2 = await client.post(
                                "https://api.openai.com/v1/chat/completions",
                                headers={"Authorization": f"Bearer {self.openai_key}",
                                         "Content-Type": "application/json"},
                                json={
                                    "model": "gpt-4o",
                                    "messages": [
                                        {"role": "system", "content": self._classification_prompt},
                                        {"role": "user", "content": company_text},
                                    ],
                                    "max_tokens": 200, "temperature": 0,
                                },
                            )
                            data2 = resp2.json()
                            content2 = data2.get("choices", [{}])[0].get("message", {}).get("content", "")
                            clean2 = content2.strip()
                            if clean2.startswith("```"):
                                clean2 = clean2.split("\n", 1)[1].rsplit("```", 1)[0]
                            parsed2 = json.loads(clean2)
                            is_target = parsed2.get("is_target", is_target)
                            segment = parsed2.get("segment", segment)
                            reasoning = f"[2-pass] {parsed2.get('reasoning', reasoning)}"
                        except Exception:
                            pass  # Keep pass-1 result

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
                        await self._safe_put(self.people_queue, dc)
                except Exception as e:
                    dc.status = "classify_failed"
                    logger.debug(f"Classify {dc.domain}: {e}")

        tasks = []
        while True:
            dc = await self.classify_queue.get()
            if dc is None:
                break
            if self._shutdown.is_set():
                break
            tasks.append(asyncio.create_task(classify_one(dc)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await client.aclose()  # Clean up shared httpx client
        await self.people_queue.put(None)

    async def _people_worker(self):
        """Streaming people extraction — 20 concurrent. Own session for DB writes."""
        from app.db import async_session_maker
        if not self.apollo:
            return
        sem = asyncio.Semaphore(20)

        async def extract_one(dc):
            if self._shutdown.is_set():
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
                                self._trigger_shutdown()
                                break
                        # Store org data from bulk_match back to company (free with enrichment)
                        org_data = people[0] if people else {}
                        if org_data.get("org_country") or org_data.get("org_funding"):
                            from sqlalchemy import update
                            update_vals = {}
                            if org_data.get("org_country"):
                                update_vals["country"] = org_data["org_country"]
                            if org_data.get("org_city"):
                                update_vals["city"] = org_data["org_city"]
                            if org_data.get("org_industry"):
                                update_vals["industry"] = org_data["org_industry"]
                            if org_data.get("org_employee_count"):
                                update_vals["employee_count"] = org_data["org_employee_count"]
                            if org_data.get("org_funding"):
                                update_vals["funding_stage"] = org_data["org_funding"]
                            if org_data.get("org_funding_amount"):
                                update_vals["funding_amount"] = org_data["org_funding_amount"]
                            if update_vals:
                                await ws.execute(
                                    update(DiscoveredCompany).where(DiscoveredCompany.id == dc.id).values(**update_vals)
                                )
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
            if self._shutdown.is_set():
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
                vals = dict(
                    new_companies_count=self.total_companies,
                    pages_fetched=self._tam_pages + self.pages_fetched,
                    total_targets_found=self.total_targets,
                    total_people_found=self.total_people,
                    credits_used=self.run.credits_used or 0,
                )
                if self.apollo_total_entries:
                    vals["raw_results_count"] = self.apollo_total_entries
                await ws.execute(
                    update(GatheringRun).where(GatheringRun.id == self.run.id).values(**vals)
                )
                await ws.commit()
        except Exception as e:
            logger.debug(f"Progress persist failed: {e}")

    def _build_result(self, elapsed: float) -> Dict:
        total_pages = self._tam_pages + self.pages_fetched
        target_rate = round(self.total_targets / max(self.total_classified, 1) * 100)
        scrape_rate = round(self.total_scraped / max(self.total_companies, 1) * 100)

        # Persist level stats to run filters for UI
        try:
            if self._level_stats and self.run.filters:
                self.run.filters["_level_stats"] = self._level_stats
        except Exception:
            pass

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
            "status": "completed",  # Always "completed" per spec — use kpi_met field to distinguish outcome
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
            "companies_per_page_avg": round(self.total_companies / max(total_pages, 1), 1),
            "issues": issues,
            "message": msg,
        }
