"""Pipeline Orchestrator — auto-gathers until target contacts KPI reached.

Two parallel processes:
  Process 1: Company gathering (pages from Apollo, 4 at a time)
  Process 2: People extraction (up to N contacts per target, runs immediately)

Stop condition: Process 2 reaches target_count people → Process 1 stops.

KPIs are user-settable via MCP prompts (set_pipeline_kpi tool):
  - target_count: total contacts to gather (default 100)
  - contacts_per_company: max people per company (default 3)
  - min_targets: target companies needed (auto-derived if not set)

Pause/Resume: orchestrator checks run.status between iterations.
Progress persisted to DB after each batch for frontend display + resume.

Flow:
  1. Page 1 (25 companies) → scrape → classify → start people for targets
  2. Exploration: enrich top 5 → optimize filters
  3. Pages 2-5 (100 companies) → scrape → classify → people for new targets
  4. Loop pages by 4 until KPI reached
  5. Create SmartLead campaign automatically
"""
import asyncio
import logging
from datetime import datetime, timezone
from math import ceil
from typing import Any, Dict, Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gathering import GatheringRun, ApprovalGate, CompanySourceLink
from app.models.pipeline import DiscoveredCompany, ExtractedContact
from app.models.gathering import CompanyScrape
from app.models.project import Project
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)

# Defaults (used when run.target_count / run.contacts_per_company are NULL)
DEFAULT_TARGET_COUNT = 100
DEFAULT_CONTACTS_PER_COMPANY = 3
PAGES_PER_BATCH = 4
EXPLORATION_PER_PAGE = 25    # Iteration 1: small sample for filter improvement
SCALE_PER_PAGE = 100         # Iteration 2+: full speed after improvement

# Background task registry — tracks running orchestrator tasks by run_id
_running_tasks: Dict[int, asyncio.Task] = {}


def is_pipeline_running(run_id: int) -> bool:
    """Check if a background pipeline task is active for this run."""
    task = _running_tasks.get(run_id)
    return task is not None and not task.done()


class PipelineOrchestrator:
    """Runs the full pipeline until target contacts KPI is reached."""

    def __init__(self, session: AsyncSession, run: GatheringRun, openai_key: str,
                 apollo_service=None, apify_proxy: Optional[str] = None):
        self.session = session
        self.run = run
        self.openai_key = openai_key
        self.apollo = apollo_service
        self.apify_proxy = apify_proxy
        self.total_people = 0
        self.total_targets = 0
        self.total_companies = 0
        self.pages_fetched = 0
        self.iterations = []
        self._stop = False

    @classmethod
    def resume(cls, session: AsyncSession, run: GatheringRun, openai_key: str,
               apollo_service=None, apify_proxy: Optional[str] = None):
        """Create orchestrator initialized from DB-persisted state (for resume)."""
        orch = cls(session, run, openai_key, apollo_service, apify_proxy)
        orch.total_people = run.total_people_found or 0
        orch.total_targets = run.total_targets_found or 0
        orch.total_companies = run.new_companies_count or 0
        orch.pages_fetched = run.pages_fetched or 0
        return orch

    def _read_kpis(self):
        """Read KPI targets from the run (may change mid-run via set_pipeline_kpi)."""
        return (
            self.run.target_people or DEFAULT_TARGET_COUNT,
            self.run.max_people_per_company or DEFAULT_CONTACTS_PER_COMPANY,
        )

    async def _persist_progress(self, iteration: int):
        """Write current progress to DB so frontend + pipeline_status can read it."""
        self.run.total_targets_found = self.total_targets
        self.run.total_people_found = self.total_people
        self.run.pages_fetched = self.pages_fetched
        self.run.current_iteration = iteration
        await self.session.flush()

    async def _check_pause_and_reload_kpis(self) -> bool:
        """Reload run from DB to check pause flag + re-read KPIs. Returns True if paused."""
        await self.session.refresh(self.run)
        if self.run.status == "paused":
            logger.info(f"Pipeline run {self.run.id} paused by user request")
            return True
        return False

    async def run_until_kpi(self, initial_filters: Dict) -> Dict:
        """Main loop: gather companies + people until target_count contacts found."""
        filters = dict(initial_filters)
        target_people, people_per_company = self._read_kpis()

        result = {
            "status": "running",
            "iterations": [],
            "total_targets": 0,
            "total_people": 0,
            "total_companies": 0,
            "credits_used": 0,
        }

        # Set started_at if not already set
        if not self.run.started_at:
            self.run.started_at = datetime.now(timezone.utc)
            await self.session.flush()

        # === ITERATION 1: Exploration (1 page) ===
        logger.info("Pipeline orchestrator: Iteration 1 — exploration (1 page)")
        iter1 = await self._gather_batch(filters, pages=1, iteration_label="Exploration (1 page)")
        result["iterations"].append(iter1)
        result["credits_used"] += iter1.get("credits", 0)
        await self._persist_progress(1)

        if self._stop or await self._check_pause_and_reload_kpis():
            return self._finalize(result)

        # Start people extraction for any targets found
        people_per_company = self._read_kpis()[1]
        asyncio.create_task(self._extract_people_for_new_targets(people_per_company))

        # === EXPLORATION: Enrich top 5 → optimize filters (1 MAX — per default_requirements.md) ===
        # Exploration runs ONCE after iteration 1, never again. Scale phase uses optimized filters.
        exploration_done = self.pages_fetched > 1  # Skip if resuming past exploration
        if self.total_targets >= 1 and not exploration_done:
            logger.info(f"Pipeline orchestrator: Exploring (enriching top {min(5, self.total_targets)} targets)")
            try:
                from app.services.exploration_service import run_exploration
                exploration = await run_exploration(
                    query=filters.get("q_organization_keyword_tags", [""])[0] if filters.get("q_organization_keyword_tags") else "",
                    initial_filters=filters,
                    offer_text="",
                    apollo_key=self.apollo.api_key if self.apollo else "",
                    openai_key=self.openai_key,
                    apify_proxy_password=self.apify_proxy,
                )
                optimized = exploration.get("optimized_filters")
                if optimized and optimized.get("q_organization_keyword_tags"):
                    filters = optimized
                    logger.info(f"Filters optimized: {len(optimized.get('q_organization_keyword_tags', []))} keywords")
                result["credits_used"] += exploration.get("credits_used", 0)
            except Exception as e:
                logger.warning(f"Exploration failed, continuing with original filters: {e}")

        # === ITERATIONS 2+: Scale (4 pages per batch) ===
        batch_num = 2
        while not self._stop:
            # Re-read KPIs (user may have changed them via set_pipeline_kpi)
            target_people, people_per_company = self._read_kpis()

            if self.total_people >= target_people:
                self._stop = True
                logger.info(f"KPI reached: {self.total_people} people >= {target_people}")
                break

            # Check pause
            if await self._check_pause_and_reload_kpis():
                return self._finalize(result)

            logger.info(f"Pipeline orchestrator: Iteration {batch_num} — {PAGES_PER_BATCH} pages (people: {self.total_people}/{target_people})")
            iter_n = await self._gather_batch(
                filters, pages=PAGES_PER_BATCH,
                iteration_label=f"Scale batch {batch_num} ({PAGES_PER_BATCH} pages)"
            )
            result["iterations"].append(iter_n)
            result["credits_used"] += iter_n.get("credits", 0)

            # Extract people for new targets
            await self._extract_people_for_new_targets(people_per_company)

            # Update people count
            self.total_people = await self._count_people()

            # Persist progress
            await self._persist_progress(batch_num)

            logger.info(f"After iteration {batch_num}: {self.total_targets} targets, {self.total_people}/{target_people} people")

            batch_num += 1

            # Safety: max 20 iterations (500 pages = 12,500 companies)
            if batch_num > 20:
                logger.warning("Max iterations reached (20)")
                break

        return self._finalize(result)

    async def _gather_batch(self, filters: Dict, pages: int, iteration_label: str) -> Dict:
        """Gather N pages from Apollo, scrape, classify."""
        from app.services.gathering_service import GatheringService
        svc = GatheringService()

        batch_filters = dict(filters)
        batch_filters["max_pages"] = pages
        batch_filters["page_offset"] = self.pages_fetched + 1
        batch_filters["per_page"] = EXPLORATION_PER_PAGE if batch_num == 1 else SCALE_PER_PAGE

        # Gather — use adapter directly to append to existing run
        try:
            adapter = svc._get_adapter(self.run.source_type, apollo_service=self.apollo)
            if adapter:
                # Set page offset to skip already-fetched pages
                batch_filters["page"] = self.pages_fetched + 1
                results = await adapter.gather(batch_filters)

                # Dedup + store new companies
                from app.models.gathering import CompanySourceLink
                existing_domains = set()
                existing_result = await self.session.execute(
                    select(DiscoveredCompany.domain)
                    .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
                    .where(CompanySourceLink.gathering_run_id == self.run.id)
                )
                existing_domains = {r[0] for r in existing_result.all()}

                new_count = 0
                for company_data in (results or []):
                    domain = company_data.get("domain", "").lower().strip()
                    if not domain or domain in existing_domains:
                        self.run.duplicate_count = (self.run.duplicate_count or 0) + 1
                        continue
                    # Check DB too (across all runs in this project)
                    db_exists = (await self.session.execute(
                        select(DiscoveredCompany.id).where(
                            DiscoveredCompany.project_id == self.run.project_id,
                            DiscoveredCompany.domain == domain,
                        )
                    )).scalar_one_or_none()
                    if db_exists:
                        existing_domains.add(domain)
                        self.run.duplicate_count = (self.run.duplicate_count or 0) + 1
                        continue
                    existing_domains.add(domain)

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
                    new_count += 1

                self.run.new_companies_count = (self.run.new_companies_count or 0) + new_count
                self.run.filters = batch_filters
                await self.session.flush()
                logger.info(f"Batch gathered: {new_count} new companies (total: {self.run.new_companies_count})")
        except Exception as e:
            logger.warning(f"Gathering batch failed: {e}")
            return {"label": iteration_label, "error": str(e), "credits": 0}

        self.pages_fetched += pages
        credits = pages  # 1 credit per page for Apollo API

        # Count new companies
        new_count = self.run.new_companies_count or 0
        self.total_companies = new_count

        # Scrape new companies
        try:
            self.run.current_phase = "scrape"
            from app.services.scraper_service import ScraperService
            scraper = ScraperService(apify_proxy_password=self.apify_proxy)
            await svc.scrape(self.session, self.run, scraper_service=scraper)
        except Exception as e:
            logger.warning(f"Scraping failed: {e}")

        # Classify
        try:
            self.run.current_phase = "analyze"
            await svc.analyze(self.session, self.run, openai_key=self.openai_key)
        except Exception as e:
            logger.warning(f"Analysis failed: {e}")

        # Count targets
        targets = (await self.session.execute(
            select(sa_func.count(DiscoveredCompany.id))
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .where(CompanySourceLink.gathering_run_id == self.run.id, DiscoveredCompany.is_target == True)
        )).scalar() or 0
        self.total_targets = targets

        return {
            "label": iteration_label,
            "pages": pages,
            "page_range": f"{self.pages_fetched - pages + 1}-{self.pages_fetched}",
            "companies": new_count,
            "targets": targets,
            "credits": credits,
            "filters": batch_filters,
        }

    async def _extract_people_for_new_targets(self, people_per_company: int = DEFAULT_CONTACTS_PER_COMPANY):
        """Find people (contacts) for target companies that don't have contacts yet."""
        if not self.apollo:
            return

        target_people, _ = self._read_kpis()

        # Get target companies without contacts
        targets_without_people = await self.session.execute(
            select(DiscoveredCompany)
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .outerjoin(ExtractedContact, ExtractedContact.discovered_company_id == DiscoveredCompany.id)
            .where(
                CompanySourceLink.gathering_run_id == self.run.id,
                DiscoveredCompany.is_target == True,
                ExtractedContact.id == None,  # No contacts yet
            )
        )
        companies = targets_without_people.scalars().all()

        if not companies:
            return

        logger.info(f"Extracting people for {len(companies)} target companies (max {people_per_company}/company)")

        # Get people filters from offer
        project = await self.session.get(Project, self.run.project_id)
        person_titles = None
        person_seniorities = ["c_suite", "vp", "director"]

        if project and project.target_segments and self.openai_key:
            try:
                from app.services.offer_analyzer import infer_people_roles
                roles = await infer_people_roles(project.target_segments, self.openai_key)
                person_titles = roles.get("person_titles")
                person_seniorities = roles.get("person_seniorities", person_seniorities)
            except Exception:
                pass

        # Search people for each target company — PARALLEL (5 concurrent)
        import asyncio as _aio
        sem = _aio.Semaphore(5)
        found_contacts = []

        async def _search_one(company):
            async with sem:
                try:
                    people = await self.apollo.enrich_by_domain(
                        company.domain, limit=people_per_company, titles=person_titles,
                    )
                    for person in people:
                        found_contacts.append(ExtractedContact(
                            project_id=self.run.project_id,
                            discovered_company_id=company.id,
                            email=person.get("email"),
                            first_name=person.get("first_name"),
                            last_name=person.get("last_name"),
                            job_title=person.get("title") or person.get("job_title"),
                            linkedin_url=person.get("linkedin_url"),
                            source_data=person,
                        ))
                except Exception as e:
                    logger.debug(f"People search {company.domain}: {e}")

        await _aio.gather(*[_search_one(c) for c in companies])
        for contact in found_contacts:
            self.session.add(contact)
        self.total_people += len(found_contacts)
        if found_contacts:
            await self.session.flush()
            logger.info(f"Extracted {len(found_contacts)} contacts from {len(companies)} target companies")

        await self.session.flush()

    async def _count_people(self) -> int:
        """Count total extracted contacts for this run's target companies."""
        result = await self.session.execute(
            select(sa_func.count(ExtractedContact.id))
            .join(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .where(
                CompanySourceLink.gathering_run_id == self.run.id,
                DiscoveredCompany.is_target == True,
            )
        )
        return result.scalar() or 0

    def _finalize(self, result: Dict) -> Dict:
        tp = self.run.target_people or DEFAULT_TARGET_COUNT
        mpc = self.run.max_people_per_company or DEFAULT_CONTACTS_PER_COMPANY
        result["status"] = "completed" if self.total_people >= tp else "insufficient"
        result["total_targets"] = self.total_targets
        result["total_people"] = self.total_people
        result["total_companies"] = self.total_companies
        result["pages_fetched"] = self.pages_fetched
        result["kpi_met"] = self.total_people >= tp
        result["kpi"] = {
            "target_people": tp,
            "max_people_per_company": mpc,
            "target_companies": self.run.target_companies or ceil(tp / mpc),
        }
        result["message"] = (
            f"Pipeline {'complete' if result['kpi_met'] else 'paused' if self.run.status == 'paused' else 'incomplete'}: "
            f"{self.total_targets} target companies, {self.total_people}/{tp} contacts.\n"
            f"Pages fetched: {self.pages_fetched} ({self.total_companies} total companies).\n"
            f"Credits used: {result.get('credits_used', 0)}.\n"
        )
        return result


async def run_pipeline_background(run_id: int, filters: dict, user_id: int):
    """Background task — creates own DB session, runs orchestrator."""
    from app.db import async_session_maker
    try:
        async with async_session_maker() as session:
            run = await session.get(GatheringRun, run_id)
            if not run:
                logger.error(f"Background pipeline: run {run_id} not found")
                return

            # Get services
            from app.services.user_context import UserServiceContext
            ctx = UserServiceContext(user_id, session)
            apollo_svc = await ctx.get_apollo_service()
            openai_key = await ctx.get_key("openai")
            if not openai_key:
                from app.config import settings as _cfg
                openai_key = _cfg.OPENAI_API_KEY

            import os
            apify_proxy = os.environ.get("APIFY_PROXY_PASSWORD")

            # Check if resuming
            if run.pages_fetched and run.pages_fetched > 0:
                orchestrator = PipelineOrchestrator.resume(
                    session, run, openai_key, apollo_svc, apify_proxy
                )
            else:
                orchestrator = PipelineOrchestrator(
                    session, run, openai_key, apollo_svc, apify_proxy
                )

            result = await orchestrator.run_until_kpi(filters)

            # Mark complete (unless paused — then status stays "paused")
            if run.status != "paused":
                run.status = "completed" if result.get("kpi_met") else "insufficient"
                run.completed_at = datetime.now(timezone.utc)
                elapsed = (run.completed_at - run.started_at).total_seconds() if run.started_at else None
                if elapsed:
                    run.duration_seconds = int(elapsed)
            await session.commit()

            logger.info(f"Background pipeline {run_id} finished: {result.get('status')} — {result.get('total_people')} people")

            # ── Auto-notify via Telegram when pipeline completes ──
            if result.get("kpi_met") or run.status in ("completed", "insufficient"):
                await _notify_pipeline_complete(session, run, user_id, result)

            # ── Auto-generate campaign sequence when KPI met (DRAFT — user must approve) ──
            if result.get("kpi_met"):
                await _auto_generate_campaign(session, run, user_id, openai_key)

    except Exception as e:
        logger.exception(f"Background pipeline {run_id} failed: {e}")
        try:
            async with async_session_maker() as session:
                run = await session.get(GatheringRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_message = str(e)[:1000]
                    await session.commit()
        except Exception:
            pass
    finally:
        _running_tasks.pop(run_id, None)


def start_pipeline_background(run_id: int, filters: dict, user_id: int) -> asyncio.Task:
    """Spawn a background pipeline task and register it."""
    task = asyncio.create_task(run_pipeline_background(run_id, filters, user_id))
    _running_tasks[run_id] = task
    return task


async def _notify_pipeline_complete(session, run, user_id: int, result: dict):
    """Send Telegram notification when pipeline finishes."""
    try:
        import os, httpx
        bot_token = os.environ.get("TELEGRAM_NOTIFY_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return

        # Get user's telegram chat_id
        from sqlalchemy import select as _sel
        from app.models.integration import MCPIntegrationSetting
        from app.services.encryption import decrypt_value
        tg_result = await session.execute(
            _sel(MCPIntegrationSetting).where(
                MCPIntegrationSetting.user_id == user_id,
                MCPIntegrationSetting.integration_name == "telegram",
            )
        )
        tg = tg_result.scalar_one_or_none()
        if not tg or not tg.api_key_encrypted:
            return
        chat_id = decrypt_value(tg.api_key_encrypted)

        project = await session.get(Project, run.project_id)
        project_name = project.name if project else "Unknown"
        tp = run.target_people or 100
        pf = run.total_people_found or 0
        tf = run.total_targets_found or 0
        kpi_met = result.get("kpi_met", False)

        status_emoji = "✅" if kpi_met else "⚠️"
        msg = (
            f"{status_emoji} Pipeline #{run.id} ({project_name}) {'complete' if kpi_met else 'stopped'}!\n\n"
            f"People: {pf}/{tp}\n"
            f"Target companies: {tf}\n"
            f"Pages: {run.pages_fetched or 0}\n"
            f"Credits: {run.credits_used or 0}\n\n"
            f"Pipeline: http://46.62.210.24:3000/pipeline/{run.id}\n"
            f"CRM: http://46.62.210.24:3000/crm?pipeline={run.id}&project_id={run.project_id}"
        )
        if kpi_met:
            msg += "\n\nSequence generation starting — check campaign DRAFT shortly."

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": msg},
            )
        logger.info(f"Pipeline completion notification sent to chat {chat_id}")
    except Exception as e:
        logger.debug(f"Pipeline completion notification failed: {e}")


async def _auto_generate_campaign(session, run, user_id: int, openai_key: str):
    """Auto-generate SmartLead sequence when KPI met. Creates DRAFT — user must approve."""
    try:
        project = await session.get(Project, run.project_id)
        if not project:
            return

        # Generate sequence
        from app.services.campaign_intelligence import generate_sequence
        seq_result = await generate_sequence(
            session=session,
            project=project,
            openai_key=openai_key,
            campaign_name=f"{project.name} - Pipeline #{run.id}",
        )

        if seq_result and seq_result.get("sequence_id"):
            logger.info(f"Auto-generated sequence #{seq_result['sequence_id']} for pipeline {run.id}")
            # Store reference on run for easy lookup
            run.notes = (run.notes or "") + f"\nAuto-sequence: #{seq_result['sequence_id']}"
            await session.flush()
    except Exception as e:
        logger.warning(f"Auto campaign generation failed for pipeline {run.id}: {e}")
