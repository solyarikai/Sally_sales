"""Pipeline Orchestrator — auto-gathers until 100 target contacts found.

Two parallel processes:
  Process 1: Company gathering (pages from Apollo, 4 at a time)
  Process 2: People extraction (3 contacts per target, runs immediately per target)

Stop condition: Process 2 reaches 100 people → Process 1 stops.

Flow:
  1. Page 1 (25 companies) → scrape → classify → start people for targets
  2. Exploration: enrich top 5 → optimize filters
  3. Pages 2-5 (100 companies) → scrape → classify → people for new targets
  4. Loop pages by 4 until 100 people found
  5. Create SmartLead campaign automatically
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gathering import GatheringRun, ApprovalGate, CompanySourceLink
from app.models.pipeline import DiscoveredCompany, ExtractedContact
from app.models.gathering import CompanyScrape
from app.models.project import Project
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)

TARGET_PEOPLE_KPI = 100
PEOPLE_PER_COMPANY = 3
PAGES_PER_BATCH = 4
COMPANIES_PER_PAGE = 25


class PipelineOrchestrator:
    """Runs the full pipeline until 100 target contacts are gathered."""

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

    async def run_until_kpi(self, initial_filters: Dict) -> Dict:
        """Main loop: gather companies + people until 100 contacts found."""
        filters = dict(initial_filters)
        result = {
            "status": "running",
            "iterations": [],
            "total_targets": 0,
            "total_people": 0,
            "total_companies": 0,
            "credits_used": 0,
        }

        # === ITERATION 1: Exploration (1 page) ===
        logger.info("Pipeline orchestrator: Iteration 1 — exploration (1 page)")
        iter1 = await self._gather_batch(filters, pages=1, iteration_label="Exploration (1 page)")
        result["iterations"].append(iter1)
        result["credits_used"] += iter1.get("credits", 0)

        if self._stop:
            return self._finalize(result)

        # Start people extraction for any targets found
        asyncio.create_task(self._extract_people_for_new_targets())

        # === EXPLORATION: Enrich top 5 → optimize filters ===
        if self.total_targets >= 1:
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
        while not self._stop and self.total_people < TARGET_PEOPLE_KPI:
            logger.info(f"Pipeline orchestrator: Iteration {batch_num} — {PAGES_PER_BATCH} pages (people so far: {self.total_people})")
            iter_n = await self._gather_batch(
                filters, pages=PAGES_PER_BATCH,
                iteration_label=f"Scale batch {batch_num} ({PAGES_PER_BATCH} pages)"
            )
            result["iterations"].append(iter_n)
            result["credits_used"] += iter_n.get("credits", 0)

            # Extract people for new targets
            await self._extract_people_for_new_targets()

            # Update people count
            self.total_people = await self._count_people()
            logger.info(f"After iteration {batch_num}: {self.total_targets} targets, {self.total_people} people")

            if self.total_people >= TARGET_PEOPLE_KPI:
                self._stop = True
                logger.info(f"KPI reached: {self.total_people} people >= {TARGET_PEOPLE_KPI}")

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
        batch_filters["per_page"] = COMPANIES_PER_PAGE

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
            await svc.scrape(self.session, self.run, apify_proxy=self.apify_proxy)
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

    async def _extract_people_for_new_targets(self):
        """Find people (contacts) for target companies that don't have contacts yet."""
        if not self.apollo:
            return

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

        logger.info(f"Extracting people for {len(companies)} target companies")

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

        # Search people for each target company (FREE — /mixed_people/api_search)
        for company in companies:
            if self.total_people >= TARGET_PEOPLE_KPI:
                break
            try:
                people = await self.apollo.enrich_by_domain(
                    company.domain,
                    limit=PEOPLE_PER_COMPANY,
                    titles=person_titles,
                )
                for person in people:
                    contact = ExtractedContact(
                        project_id=self.run.project_id,
                        discovered_company_id=company.id,
                        email=person.get("email"),
                        first_name=person.get("first_name"),
                        last_name=person.get("last_name"),
                        title=person.get("title"),
                        linkedin_url=person.get("linkedin_url"),
                        source_data=person,
                    )
                    self.session.add(contact)
                self.total_people += len(people)
            except Exception as e:
                logger.debug(f"People search for {company.domain} failed: {e}")

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
        result["status"] = "completed" if self.total_people >= TARGET_PEOPLE_KPI else "insufficient"
        result["total_targets"] = self.total_targets
        result["total_people"] = self.total_people
        result["total_companies"] = self.total_companies
        result["pages_fetched"] = self.pages_fetched
        result["kpi_met"] = self.total_people >= TARGET_PEOPLE_KPI
        result["message"] = (
            f"Pipeline complete: {self.total_targets} target companies, {self.total_people} contacts gathered.\n"
            f"Pages fetched: {self.pages_fetched} ({self.total_companies} total companies).\n"
            f"Credits used: {result.get('credits_used', 0)}.\n"
            + (f"KPI MET: {self.total_people} contacts >= {TARGET_PEOPLE_KPI} target.\n"
               if self.total_people >= TARGET_PEOPLE_KPI
               else f"KPI NOT MET: {self.total_people} contacts < {TARGET_PEOPLE_KPI}. Consider broader filters.\n")
        )
        return result
