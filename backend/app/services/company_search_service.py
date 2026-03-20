"""
Company Search Service — Orchestrator for the AI-driven company search pipeline.

Full pipeline:
1. Load project, get target_segments
2. Generate queries via GPT-4o-mini using target_segments
3. Create SearchJob, run Yandex search
4. For each new domain found, scrape HTML via httpx
5. Clean HTML → structured text with language detection
6. Analyze via GPT-4o-mini with multi-criteria scoring rubric
7. Post-process: hard validation rules override GPT output
8. Store results with scores, is_target flag, GPT reasoning
9. Auto-review batch for quality assurance
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.contact import Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchResult,
    DomainSource, ProjectSearchKnowledge, ProjectBlacklist,
)
from app.services.search_service import search_service
from app.services.domain_service import domain_service

logger = logging.getLogger(__name__)

# Global GPT analysis semaphore — shared across ALL concurrent segments
# Caps total concurrent GPT-4o-mini analysis calls to prevent OpenAI 429s
_gpt_analysis_semaphore = asyncio.Semaphore(25)

# Cost constants
YANDEX_COST_PER_1K_REQUESTS = 0.25  # $0.25 per 1,000 requests
GOOGLE_SERP_COST_PER_1K_REQUESTS = 3.50  # ~$3.50 per 1,000 requests via Apify SERP proxy
OPENAI_COST_PER_1M_INPUT_TOKENS = 0.15  # GPT-4o-mini: ~$0.15 per 1M input tokens
OPENAI_COST_PER_1M_OUTPUT_TOKENS = 0.60  # GPT-4o-mini: ~$0.60 per 1M output tokens
# Gemini 2.5 Pro pricing (blended avg since we track total tokens, not input/output separately)
GEMINI_COST_PER_1M_TOKENS = 2.50  # ~$1.25 input + $10 output; blended estimate ~$2.50


class CompanySearchService:
    """Orchestrates the full search pipeline for a project."""

    # ------------------------------------------------------------------
    # HTML-to-text extraction (Phase 1a)
    # ------------------------------------------------------------------

    STRIP_TAGS = {"script", "style", "nav", "header", "footer", "aside",
                  "noscript", "iframe", "svg", "form", "button"}
    NOISE_CLASSES = re.compile(
        r"nav|menu|sidebar|footer|cookie|popup|modal|banner",
        re.IGNORECASE,
    )

    def _extract_clean_text(self, content: str, domain: str, is_html: bool = True) -> Dict[str, Any]:
        """
        Extract clean text with metadata and language detection.

        Args:
            content: Raw HTML (from direct scraping) or clean text (from Crona)
            domain: Domain name for context
            is_html: True if content is raw HTML, False if already clean text (Crona)

        Returns: {"title", "description", "text", "language", "cyrillic_ratio"}
        """
        title = ""
        description = ""

        if is_html:
            soup = BeautifulSoup(content, "lxml")

            # Extract meta before stripping
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)[:200]

            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = (meta_desc.get("content") or "")[:500]

            # Strip noisy tags
            for tag_name in self.STRIP_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Remove elements with nav/menu/sidebar/footer/cookie/popup/modal/banner classes
            for el in soup.find_all(attrs={"class": self.NOISE_CLASSES}):
                el.decompose()
            for el in soup.find_all(attrs={"id": self.NOISE_CLASSES}):
                el.decompose()

            text = soup.get_text(separator="\n", strip=True)
        else:
            # Crona already returns clean text
            text = content

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text[:6000]  # Cap for GPT context

        # Language detection via Cyrillic ratio
        total_chars = max(len(text), 1)
        cyrillic_count = len(re.findall(r"[а-яА-ЯёЁ]", text))
        cyrillic_ratio = cyrillic_count / total_chars

        if cyrillic_ratio > 0.15:
            language = "ru"
        elif cyrillic_ratio < 0.02:
            language = "en"
        else:
            language = "other"

        return {
            "title": title,
            "description": description,
            "text": text,
            "language": language,
            "cyrillic_ratio": round(cyrillic_ratio, 3),
        }

    # ------------------------------------------------------------------
    # Post-processing validation (Phase 1c)
    # ------------------------------------------------------------------

    NEGATIVE_INDICATORS = re.compile(
        r"не (соответствует|подходит|относится|является|связан)"
        r"|doesn'?t match|not (a match|relevant|related|target)"
        r"|no (match|relevance|relation)"
        r"|irrelevant|unrelated|wrong (industry|segment|sector)",
        re.IGNORECASE,
    )

    # False positive detection patterns for construction-related projects
    FITOUT_INDICATORS = re.compile(
        r"fit[\s-]?out|отделк|отделочн|ремонт(?!.*строительств)|renovation(?!.*construction)"
        r"|interior design|дизайн интерьер|интерьерн|interior fit"
        r"|finishing works|чистов|декор(?:ирование|атор)|furnish"
        r"|обои|покраск|штукатур|сантехник|электрик",
        re.IGNORECASE,
    )

    ARCH_ONLY_INDICATORS = re.compile(
        r"architect(?:ural|ure)?\s+(?:studio|firm|bureau|бюро)"
        r"|архитектурн\w+\s+(?:бюро|студия|мастерская)"
        r"|(?:only|только)\s+(?:design|проект)"
        r"|design\s+(?:studio|firm|company)(?!\s*(?:and|&)\s*(?:build|construct))"
        r"|проектн\w+\s+(?:бюро|компания|организация)",
        re.IGNORECASE,
    )

    CONSTRUCTION_INDICATORS = re.compile(
        r"строительств|construction|build(?:er|ing)|застройщик|подрядчик"
        r"|девелопер|developer|general\s+contractor|генподрядчик"
        r"|villa\s+(?:build|construct|develop)"
        r"|ground[\s-]?up|с\s*нуля|новое\s+строительство",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_construction_target(target_segments_lower: str) -> bool:
        """Check if target segments are construction-related (where fit-out false positives apply).

        Uses specific phrases to avoid false triggers on non-construction projects
        (e.g. 'software developer', 'build tools' won't match).
        """
        return any(kw in target_segments_lower for kw in [
            "строительств", "construction", "builder", "building",
            "застройщик", "подрядчик", "general contractor",
            "property developer", "real estate developer",
            "девелопер", "villa", "вилл",
        ])

    def _validate_analysis(
        self,
        analysis: Dict[str, Any],
        clean_text: Dict[str, Any],
        target_segments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Hard rules that override GPT output to catch obvious errors.
        Modifies analysis in-place and returns it.
        """
        scores = analysis.get("scores", {})
        cyrillic_ratio = clean_text.get("cyrillic_ratio", 0.0)
        reasoning = analysis.get("reasoning", "")

        # Detect if target geography allows non-Russian (English) sites
        ts_lower = (target_segments or "").lower()
        allows_english = any(kw in ts_lower for kw in [
            "dubai", "дубай", "дубае", "абу-даби", "abu dhabi", "uae", "оаэ",
            "английск", "english",
            # International HNWI hubs
            "cyprus", "кипр", "monaco", "монако", "london", "лондон",
            "switzerland", "швейцар", "israel", "израил",
            "singapore", "сингапур", "montenegro", "черногор",
            "serbia", "серби", "turkey", "турц", "istanbul", "стамбул",
            "international", "международн",
            # Additional hubs
            "latvia", "латви", "riga", "рига",
            "estonia", "эстони", "tallinn", "таллин",
            "georgia", "грузи", "tbilisi", "тбилиси",
            "portugal", "португал", "lisbon", "лиссабон",
            # Gaming / crypto / global digital platforms
            "gaming", "skins", "crypto", "payment gateway",
            "germany", "france", "sweden", "canada", "australia", "japan",
            "finland", "denmark", "norway", "austria", "belgium", "ireland",
        ])

        # Rule 1: Non-Russian site with Russian-only target → force language_match=0
        # Skip this rule for projects targeting Dubai/UAE where English sites are normal
        if cyrillic_ratio < 0.1 and not allows_english:
            scores["language_match"] = 0.0
            if analysis.get("is_target"):
                analysis["is_target"] = False
                analysis["confidence"] = 0.0
                analysis["reasoning"] = (
                    f"[AUTO-REJECTED: non-Russian site, cyrillic_ratio={cyrillic_ratio}] "
                    + reasoning
                )

        # Rule 2: Confidence must not exceed minimum score
        score_values = [v for v in scores.values() if isinstance(v, (int, float))]
        if score_values:
            min_score = min(score_values)
            if analysis.get("confidence", 0) > min_score:
                analysis["confidence"] = min_score

        # Rule 3: Reasoning says "doesn't match" but is_target=True → override
        if analysis.get("is_target") and self.NEGATIVE_INDICATORS.search(reasoning):
            analysis["is_target"] = False
            analysis["confidence"] = min(analysis.get("confidence", 0), 0.2)
            analysis["reasoning"] = f"[AUTO-CORRECTED: reasoning contradicts is_target] {reasoning}"

        # Rule 4: False positive detection for fit-out/interior/renovation/competitor companies
        # Only apply for construction-related target segments (ArchiStruct-like)
        if analysis.get("is_target") and self._is_construction_target(ts_lower):
            company_info = analysis.get("company_info", {})
            ci_text = (
                f"{company_info.get('name', '')} {company_info.get('description', '')} "
                f"{' '.join(company_info.get('services', []))} {company_info.get('industry', '')} "
                f"{reasoning}"
            ).lower()

            # Fit-out / interior design / renovation only (not ground-up construction)
            fitout_only = self.FITOUT_INDICATORS.search(ci_text) and not self.CONSTRUCTION_INDICATORS.search(ci_text)
            if fitout_only:
                scores["industry_match"] = min(scores.get("industry_match", 1.0), 0.2)
                scores["service_match"] = min(scores.get("service_match", 1.0), 0.2)
                analysis["is_target"] = False
                analysis["confidence"] = 0.0
                analysis["reasoning"] = f"[AUTO-REJECTED: fit-out/interior only, no construction] {reasoning}"

            # Architecture/design only (no build capability)
            arch_only = self.ARCH_ONLY_INDICATORS.search(ci_text) and not self.CONSTRUCTION_INDICATORS.search(ci_text)
            if arch_only and not fitout_only:
                scores["industry_match"] = min(scores.get("industry_match", 1.0), 0.3)
                scores["service_match"] = min(scores.get("service_match", 1.0), 0.3)
                analysis["is_target"] = False
                analysis["confidence"] = 0.0
                analysis["reasoning"] = f"[AUTO-REJECTED: architecture/design only, no build] {reasoning}"

        # Rule 5: Ukraine exclusion — always reject Ukraine-based companies
        # Check both company_info location and reasoning for Ukraine indicators
        if analysis.get("is_target"):
            company_info = analysis.get("company_info", {})
            location = (company_info.get("location", "") or "").lower()
            all_text = f"{location} {reasoning.lower()} {(company_info.get('description', '') or '').lower()}"
            ukraine_indicators = [
                "ukraine", "україна", "украина", "украін",
                "kyiv", "київ", "киев",
                "odessa", "одеса", "одесса",
                "kharkiv", "харків", "харьков",
                "lviv", "львів", "львов",
                "dnipro", "дніпро", "днепр",
                "zaporizhzhia", "запоріжжя", "запорожье",
            ]
            if any(ind in all_text for ind in ukraine_indicators):
                analysis["is_target"] = False
                analysis["confidence"] = 0.0
                analysis["reasoning"] = f"[AUTO-REJECTED: Ukraine-based company excluded] {reasoning}"

        analysis["scores"] = scores
        return analysis

    async def demote_by_keywords(
        self,
        session: AsyncSession,
        project_id: int,
        anti_keywords: List[str],
    ) -> int:
        """
        Demote SearchResults whose company_info or domain contains any anti_keyword.
        Sets is_target=False for matching results. Returns count of demoted results.
        """
        if not anti_keywords:
            return 0

        # Load targets in batches to avoid memory issues on large projects
        result = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == project_id,
                SearchResult.is_target == True,
            ).limit(5000)  # Safety cap
        )
        targets = list(result.scalars().all())
        demoted = 0
        lower_keywords = [kw.lower() for kw in anti_keywords]

        for sr in targets:
            ci = sr.company_info or {}
            searchable = " ".join([
                sr.domain or "",
                ci.get("name", ""),
                ci.get("description", ""),
                ci.get("industry", ""),
                " ".join(ci.get("services", [])),
            ]).lower()

            if any(kw in searchable for kw in lower_keywords):
                sr.is_target = False
                sr.confidence = 0.0
                sr.reasoning = f"[DEMOTED by keyword filter: {', '.join(anti_keywords)}] {sr.reasoning or ''}"
                demoted += 1

        if demoted > 0:
            await session.commit()
            logger.info(f"Demoted {demoted} results in project {project_id} by keywords: {anti_keywords}")

        return demoted

    async def _count_project_targets(self, session: AsyncSession, project_id: int) -> int:
        """Count confirmed/unrejected targets for a project."""
        result = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == project_id,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            )
        )
        return result.scalar() or 0

    async def _build_skip_set(self, session: AsyncSession, project_id: int) -> set:
        """
        Build the full set of domains to skip for a project.
        Sources:
        1. Already-processed: SearchResult entries within SEARCH_DOMAIN_RECHECK_DAYS
        2. Blacklisted: ProjectBlacklist entries
        3. Already target: confirmed targets (don't re-scrape)
        4. Already in CRM campaigns: domains from contacts table (already outreached)
        """
        from datetime import timedelta
        from app.models.contact import Contact
        from sqlalchemy import func as sqlfunc

        cutoff = datetime.utcnow() - timedelta(days=settings.SEARCH_DOMAIN_RECHECK_DAYS)

        skip = set()

        # 1. Already analyzed within recheck window
        result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == project_id,
                SearchResult.analyzed_at >= cutoff,
            )
        )
        for row in result.fetchall():
            skip.add(row[0])

        # 2. Blacklisted
        result = await session.execute(
            select(ProjectBlacklist.domain).where(
                ProjectBlacklist.project_id == project_id,
            )
        )
        for row in result.fetchall():
            skip.add(row[0])

        # 3. Confirmed targets (already analyzed as target, don't re-process)
        result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == project_id,
                SearchResult.is_target == True,
            )
        )
        for row in result.fetchall():
            skip.add(row[0])

        # 4. Domains already in CRM contacts (already outreached via SmartLead/campaigns)
        result = await session.execute(
            select(sqlfunc.distinct(sqlfunc.lower(Contact.domain))).where(
                Contact.domain.isnot(None),
                Contact.domain != '',
            )
        )
        for row in result.fetchall():
            if row[0]:
                skip.add(row[0])

        return skip

    async def run_segment_search(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        segment_key: str,
        geo_key: str,
        search_engine: SearchEngine = SearchEngine.YANDEX_API,
        ai_expand_rounds: int = 2,
        ai_expand_count: int = 30,
    ) -> dict:
        """
        Run search for a specific segment + geo combination.
        Phase A: Template queries (deterministic, zero AI cost).
        Phase B: AI expansion via gpt-4o-mini (when templates exhausted).
        Returns stats dict.
        """
        from app.services.query_templates import build_segment_queries, build_doc_keyword_queries
        from app.services.search_config_service import search_config_service

        # Load project for target_segments
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        knowledge_data = await self._load_project_knowledge(session, project_id)

        # Load per-project search config (segments/geos/templates from DB)
        config = await search_config_service.get_or_create_config(session, project_id)
        segments_data = config.get("segments") if config else None
        doc_keywords_data = config.get("doc_keywords") if config else None

        # Collect all used queries for this project (dedup across jobs)
        existing_result = await session.execute(
            select(SearchQuery.query_text).join(SearchJob).where(
                SearchJob.project_id == project_id
            )
        )
        existing_queries = set(
            (r[0] or "").strip().lower() for r in existing_result.fetchall()
        )

        # Phase A: Doc keywords first (curated phrases from keyword docs)
        tagged_queries = build_doc_keyword_queries(
            segment_key=segment_key,
            geo_key=geo_key,
            existing_queries=existing_queries,
            doc_keywords_data=doc_keywords_data,
        )
        doc_count = len(tagged_queries)

        # Phase A2: Template queries (deterministic, variable-expanded)
        # Use templates to fill up when doc keywords are exhausted
        template_queries_ru = build_segment_queries(
            segment_key=segment_key,
            geo_key=geo_key,
            language="ru",
            existing_queries=existing_queries,
            segments_data=segments_data,
        )
        template_queries_en = build_segment_queries(
            segment_key=segment_key,
            geo_key=geo_key,
            language="en",
            existing_queries=existing_queries,
            segments_data=segments_data,
        )
        # Dedup templates against doc keywords already added
        doc_query_texts = set(q["query"].strip().lower() for q in tagged_queries)
        for tq in template_queries_ru + template_queries_en:
            if tq["query"].strip().lower() not in doc_query_texts:
                tagged_queries.append(tq)
                doc_query_texts.add(tq["query"].strip().lower())

        template_count = len(tagged_queries) - doc_count

        # Cap queries per geo to keep runs efficient (process in batches across runs)
        MAX_QUERIES_PER_GEO = 100
        if len(tagged_queries) > MAX_QUERIES_PER_GEO:
            logger.info(
                f"Capping {segment_key}/{geo_key} from {len(tagged_queries)} to {MAX_QUERIES_PER_GEO} queries"
            )
            tagged_queries = tagged_queries[:MAX_QUERIES_PER_GEO]
            template_count = len(tagged_queries) - doc_count

        stats = {
            "segment": segment_key,
            "geo": geo_key,
            "template_queries": template_count,
            "doc_keyword_queries": doc_count,
            "ai_queries": 0,
            "total_queries": len(tagged_queries),
            "targets_found": 0,
            "domains_found": 0,
            "job_id": None,
        }

        if not tagged_queries:
            logger.info(f"No new queries for {segment_key}/{geo_key}")
            return stats

        # Create a SearchJob for this segment+geo
        job_config = {
            "segment": segment_key,
            "geo": geo_key,
            "max_pages": settings.SEARCH_MAX_PAGES,
            "workers": settings.SEARCH_WORKERS,
            "target_segments": project.target_segments,
            "query_source": "template+doc_keywords",
        }
        job = SearchJob(
            company_id=company_id,
            status=SearchJobStatus.PENDING,
            search_engine=search_engine,
            queries_total=0,
            project_id=project_id,
            config=job_config,
        )
        session.add(job)
        await session.flush()
        stats["job_id"] = job.id

        # Add all queries to DB with segment/geo tags
        for tq in tagged_queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=tq["query"],
                segment=tq["segment"],
                geo=tq["geo"],
                language=tq["language"],
            )
            session.add(sq)
        job.queries_total = len(tagged_queries)
        await session.commit()

        # Execute search
        logger.info(
            f"Running {segment_key}/{geo_key}: {template_count} templates + {doc_count} doc keywords = {len(tagged_queries)} queries on {search_engine.value}"
        )
        await search_service.run_search_job(session, job.id)
        await session.refresh(job)

        # Scrape and analyze new domains
        skip_set = await self._build_skip_set(session, project_id)
        new_domains = await self._get_new_domains_from_job(session, job, skip_set)

        if new_domains:
            await self._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=project.target_segments,
            )

        await session.commit()

        # Count targets found
        target_count_result = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        targets_this_job = target_count_result.scalar() or 0
        stats["targets_found"] = targets_this_job
        stats["domains_found"] = job.domains_found or 0

        # Phase B: AI Expansion (if not enough targets)
        for ai_round in range(ai_expand_rounds):
            if targets_this_job > 0 and ai_round > 0:
                # Some targets found — stop expanding
                break

            logger.info(
                f"AI expansion round {ai_round + 1} for {segment_key}/{geo_key} "
                f"(targets so far: {targets_this_job})"
            )

            # Get seed queries for AI
            seed_queries = [tq["query"] for tq in tagged_queries[:20]]
            # Get confirmed targets for this segment
            confirmed_result = await session.execute(
                select(SearchResult.domain).where(
                    SearchResult.search_job_id == job.id,
                    SearchResult.is_target == True,
                ).limit(15)
            )
            confirmed_domains = [r[0] for r in confirmed_result.fetchall()]

            # Use gpt-4o-mini for expansion
            ai_queries = await search_service.generate_segment_queries(
                session=session,
                segment=segment_key,
                geo=geo_key,
                language="ru",  # Start with Russian
                keywords=seed_queries,
                count=ai_expand_count,
                existing_queries=list(existing_queries),
                target_segments=project.target_segments,
                good_queries=(knowledge_data or {}).get("good_query_patterns", []),
                confirmed_targets=confirmed_domains,
            )

            if not ai_queries:
                break

            # Add AI queries to DB
            for aq in ai_queries:
                sq = SearchQuery(
                    search_job_id=job.id,
                    query_text=aq["query"],
                    segment=aq["segment"],
                    geo=aq["geo"],
                    language=aq["language"],
                )
                session.add(sq)
                existing_queries.add(aq["query"].strip().lower())

            job.queries_total = (job.queries_total or 0) + len(ai_queries)
            config = dict(job.config or {})
            config["query_source"] = "template+ai"
            config["ai_rounds"] = ai_round + 1
            job.config = config
            await session.commit()

            stats["ai_queries"] += len(ai_queries)
            stats["total_queries"] += len(ai_queries)

            # Execute AI queries
            await search_service.run_search_job(session, job.id)
            await session.refresh(job)

            # Scrape new domains
            skip_set = await self._build_skip_set(session, project_id)
            new_ai_domains = await self._get_new_domains_from_job(session, job, skip_set)
            if new_ai_domains:
                await self._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=new_ai_domains,
                    target_segments=project.target_segments,
                )
            await session.commit()

            # Recount targets
            target_count_result = await session.execute(
                select(func.count()).select_from(SearchResult).where(
                    SearchResult.search_job_id == job.id,
                    SearchResult.is_target == True,
                )
            )
            targets_this_job = target_count_result.scalar() or 0
            stats["targets_found"] = targets_this_job
            stats["domains_found"] = job.domains_found or 0

        # Mark job complete
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await session.commit()

        logger.info(
            f"Segment search done: {segment_key}/{geo_key} — "
            f"{stats['template_queries']} template + {stats['ai_queries']} AI queries, "
            f"{stats['targets_found']} targets, {stats['domains_found']} domains"
        )
        return stats

    async def run_project_search(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        max_queries: int = 500,
        target_goal: Optional[int] = None,
        job_id: Optional[int] = None,
        search_engine: Optional[SearchEngine] = None,
    ) -> SearchJob:
        """
        Iterative search pipeline: generates batches of queries, searches, scrapes,
        and analyzes until target_goal targets are found or limits are reached.

        If job_id is provided, uses that existing job (updates it).
        Otherwise creates a new one.
        Returns the SearchJob with results populated.
        """
        target_goal = target_goal or settings.SEARCH_TARGET_GOAL

        # 1. Load project
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if not project.target_segments:
            raise ValueError(f"Project {project_id} has no target_segments configured")

        target_segments = project.target_segments

        # Load project knowledge for feedback loop
        knowledge_data = await self._load_project_knowledge(session, project_id)

        good_queries = (knowledge_data or {}).get("good_query_patterns", [])
        bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

        # Count existing targets
        existing_targets = await self._count_project_targets(session, project_id)
        logger.info(f"Project {project_id}: {existing_targets}/{target_goal} targets already found")

        # Get or create SearchJob
        job_config = {
            "max_queries": max_queries,
            "target_goal": target_goal,
            "target_segments": target_segments,
            "max_pages": settings.SEARCH_MAX_PAGES,
            "workers": settings.SEARCH_WORKERS,
            "openai_tokens_used": 0,
            "queries_generated": 0,
        }

        if job_id:
            result = await session.execute(
                select(SearchJob).where(SearchJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            job.config = job_config
        else:
            job = SearchJob(
                company_id=company_id,
                status=SearchJobStatus.PENDING,
                search_engine=search_engine or SearchEngine.YANDEX_API,
                queries_total=0,
                project_id=project_id,
                config=job_config,
            )
            session.add(job)
            await session.flush()

        await session.commit()

        # Collect all query texts used so far (for dedup across iterations)
        all_used_queries: List[str] = []

        # Get confirmed target domains for query generation feedback
        confirmed_targets_result = await session.execute(
            select(SearchResult.domain, SearchResult.company_info).where(
                SearchResult.project_id == project_id,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            ).limit(50)
        )
        confirmed_target_examples = [
            row[0] for row in confirmed_targets_result.fetchall()
        ]

        iteration = 0
        total_queries_used = 0
        consecutive_zero_target_iterations = 0

        while existing_targets < target_goal and iteration < settings.SEARCH_MAX_ITERATIONS:
            # Check for cancellation before each iteration
            await session.refresh(job)
            if job.status == SearchJobStatus.CANCELLED:
                logger.info(f"Job {job.id} cancelled — stopping search at iteration {iteration}")
                return job

            iteration += 1
            batch_size = min(settings.SEARCH_BATCH_QUERIES, max_queries - total_queries_used)
            if batch_size <= 0:
                logger.info(f"Iteration {iteration}: query budget exhausted ({total_queries_used}/{max_queries})")
                break

            # Google SERP cost guardrail: hard stop at budget limit
            if job.search_engine == SearchEngine.GOOGLE_SERP:
                google_cost_limit = 50.0  # Default $50
                if project and project.auto_enrich_config:
                    google_cost_limit = project.auto_enrich_config.get("google_cost_limit_usd", 50.0)
                estimated_cost = (total_queries_used / 1000) * GOOGLE_SERP_COST_PER_1K_REQUESTS
                if estimated_cost >= google_cost_limit:
                    logger.warning(
                        f"Google SERP cost limit reached: ${estimated_cost:.2f} >= ${google_cost_limit:.2f} "
                        f"({total_queries_used} queries). Stopping search."
                    )
                    break

            logger.info(
                f"Iteration {iteration}: generating {batch_size} queries "
                f"({existing_targets}/{target_goal} targets, {total_queries_used}/{max_queries} queries used)"
            )

            # Generate queries with feedback (model=None → auto-detect Gemini/OpenAI)
            queries = await search_service.generate_queries(
                session=session,
                count=batch_size,
                model=None,
                target_segments=target_segments,
                project_id=project_id,
                existing_queries=all_used_queries,
                good_queries=good_queries,
                bad_queries=bad_queries,
                confirmed_targets=confirmed_target_examples,
            )

            if not queries:
                logger.warning(f"Iteration {iteration}: no queries generated, stopping")
                break

            # Track query generation tokens and model
            qg_tokens = search_service.last_query_gen_tokens
            config = dict(job.config or {})
            config["query_gen_tokens"] = config.get("query_gen_tokens", 0) + qg_tokens.get("total", 0)
            config["query_gen_model"] = search_service.last_query_gen_model

            all_used_queries.extend(queries)
            total_queries_used += len(queries)

            # Update job totals
            job.queries_total = (job.queries_total or 0) + len(queries)
            config["queries_generated"] = total_queries_used
            config["iteration"] = iteration
            job.config = config

            # Add queries to DB
            for q_text in queries:
                sq = SearchQuery(search_job_id=job.id, query_text=q_text)
                session.add(sq)
            await session.commit()

            # Run search for this batch
            engine_name = job.search_engine.value if job.search_engine else "unknown"
            logger.info(f"Iteration {iteration}: running {engine_name} search with {len(queries)} queries")
            await search_service.run_search_job(session, job.id)
            await session.refresh(job)

            # Build skip set and get new domains
            skip_set = await self._build_skip_set(session, project_id)
            new_domains = await self._get_new_domains_from_job(session, job, skip_set)

            logger.info(
                f"Iteration {iteration}: {len(new_domains)} new domains to analyze "
                f"({len(skip_set)} in skip set)"
            )

            if new_domains:
                await self._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=new_domains,
                    target_segments=target_segments,
                )

            await session.commit()

            # Refresh target count
            prev_targets = existing_targets
            existing_targets = await self._count_project_targets(session, project_id)
            new_targets_this_iter = existing_targets - prev_targets

            # Stall detection: break if 5 consecutive iterations yield zero new targets
            if new_targets_this_iter == 0:
                consecutive_zero_target_iterations += 1
                if consecutive_zero_target_iterations >= 5:
                    logger.warning(
                        f"Iteration {iteration}: 5 consecutive iterations with zero new targets — "
                        f"search exhausted. Breaking at {existing_targets}/{target_goal} targets."
                    )
                    break
            else:
                consecutive_zero_target_iterations = 0

            # Reload knowledge for next iteration
            knowledge_data = await self._load_project_knowledge(session, project_id)
            good_queries = (knowledge_data or {}).get("good_query_patterns", [])
            bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

            logger.info(
                f"Iteration {iteration} complete: "
                f"{existing_targets}/{target_goal} targets found "
                f"(+{new_targets_this_iter} this iter, "
                f"{consecutive_zero_target_iterations} consecutive zero-yield iters)"
            )

        # Mark job complete
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        config = dict(job.config or {})
        config["iterations_run"] = iteration
        config["final_targets"] = existing_targets
        job.config = config
        await session.commit()

        logger.info(
            f"Project search complete: {iteration} iterations, "
            f"{existing_targets}/{target_goal} targets, "
            f"{total_queries_used} queries used"
        )
        return job

    async def _load_project_knowledge(self, session: AsyncSession, project_id: int) -> Optional[Dict[str, Any]]:
        """Load project knowledge for feedback loop."""
        try:
            k_result = await session.execute(
                select(ProjectSearchKnowledge).where(
                    ProjectSearchKnowledge.project_id == project_id
                )
            )
            knowledge = k_result.scalar_one_or_none()
            if knowledge:
                return {
                    "good_query_patterns": knowledge.good_query_patterns or [],
                    "bad_query_patterns": knowledge.bad_query_patterns or [],
                    "confirmed_domains": knowledge.confirmed_domains or [],
                    "rejected_domains": knowledge.rejected_domains or [],
                    "industry_keywords": knowledge.industry_keywords or [],
                    "anti_keywords": knowledge.anti_keywords or [],
                }
        except Exception as e:
            logger.warning(f"Failed to load project knowledge: {e}")
        return None

    async def _get_new_domains_from_job(
        self,
        session: AsyncSession,
        job: SearchJob,
        skip_set: Optional[set] = None,
    ) -> List[str]:
        """
        Get list of new domains found by the job, excluding the skip set.

        The skip set contains:
        - Already-analyzed domains (within SEARCH_DOMAIN_RECHECK_DAYS)
        - Blacklisted domains
        - Already confirmed targets
        """
        from app.models.domain import Domain, DomainStatus

        if skip_set is None:
            skip_set = await self._build_skip_set(session, job.project_id)

        # Get active domains that were sourced from search
        result = await session.execute(
            select(Domain.domain).where(
                Domain.status == DomainStatus.ACTIVE,
                Domain.source.in_([DomainSource.SEARCH_YANDEX, DomainSource.SEARCH_GOOGLE]),
            ).order_by(Domain.last_seen.desc()).limit(job.domains_new or 500)
        )
        all_domains = [row[0] for row in result.fetchall()]

        # Filter out skip set
        new_domains = [d for d in all_domains if d not in skip_set]
        skipped = len(all_domains) - len(new_domains)
        if skipped > 0:
            logger.info(
                f"Job {job.id}: {len(all_domains)} candidate domains, "
                f"{skipped} skipped (already analyzed/blacklisted/target), "
                f"{len(new_domains)} to process"
            )
        return new_domains

    async def scrape_domain(self, domain: str, proxy_url: Optional[str] = None) -> Optional[str]:
        """
        Scrape website HTML via httpx, optionally through a proxy.
        Returns HTML content or None if scraping fails.
        """
        url = f"https://{domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

        try:
            client_kwargs = dict(
                timeout=20,
                follow_redirects=True,
                verify=False,
            )
            if proxy_url:
                client_kwargs["proxy"] = proxy_url

            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 200:
                    return resp.text[:50000]
                else:
                    logger.warning(f"Scrape {domain}: HTTP {resp.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Scrape {domain} failed: {e}")
            return None

    def _build_apify_proxy_url(self, session_id: str = "") -> Optional[str]:
        """Build Apify residential proxy URL for website scraping."""
        if not settings.APIFY_PROXY_PASSWORD:
            return None
        import random
        if not session_id:
            session_id = f"scrape_{random.randint(10000, 99999)}"
        return (
            f"http://groups-RESIDENTIAL,session-{session_id}:"
            f"{settings.APIFY_PROXY_PASSWORD}@"
            f"{settings.APIFY_PROXY_HOST}:{settings.APIFY_PROXY_PORT}"
        )

    async def analyze_company(
        self,
        content: str,
        target_segments: str,
        domain: str,
        knowledge: Optional[Dict[str, Any]] = None,
        is_html: bool = True,
        custom_system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GPT-4o-mini analyzes scraped website against target segments using
        a multi-criteria scoring rubric. Kept on GPT-4o-mini (cheap, high volume).

        Args:
            content: Raw HTML or clean text (from Crona)
            target_segments: Project target segments description
            domain: Domain name
            knowledge: Optional project knowledge for prompt injection
            is_html: True if content is raw HTML, False if clean text (Crona)

        Returns: {is_target, confidence, reasoning, company_info, scores}
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return {"is_target": False, "confidence": 0, "reasoning": "No OpenAI API key",
                    "company_info": {}, "scores": {}}

        # Extract/structure text with language detection
        clean = self._extract_clean_text(content, domain, is_html=is_html)

        # Build context block from clean text
        context_parts = [f"DOMAIN: {domain}"]
        if clean["title"]:
            context_parts.append(f"TITLE: {clean['title']}")
        if clean["description"]:
            context_parts.append(f"META DESCRIPTION: {clean['description']}")
        context_parts.append(f"DETECTED LANGUAGE: {clean['language']} (cyrillic ratio: {clean['cyrillic_ratio']})")
        context_parts.append(f"WEBSITE TEXT:\n{clean['text']}")
        website_context = "\n".join(context_parts)

        # Build knowledge context if available
        knowledge_context = ""
        if knowledge:
            parts = []
            if knowledge.get("anti_keywords"):
                parts.append(f"KNOWN FALSE POSITIVE PATTERNS (auto-reject if matching):\n{', '.join(knowledge['anti_keywords'][:30])}")
            if knowledge.get("rejected_domains"):
                parts.append(f"PREVIOUSLY REJECTED DOMAINS (similar = likely false positive):\n{', '.join(knowledge['rejected_domains'][:50])}")
            if knowledge.get("industry_keywords"):
                parts.append(f"CONFIRMED TARGET CHARACTERISTICS:\n{', '.join(knowledge['industry_keywords'][:30])}")
            if parts:
                knowledge_context = "\n\n".join(parts) + "\n\n"

        # Use custom system prompt if provided (gathering pipeline v2 via negativa)
        # Otherwise fall back to the legacy scoring rubric
        if custom_system_prompt:
            system_prompt = custom_system_prompt
            prompt = f"""{knowledge_context}{website_context}"""
            # For custom prompts, the target_segments IS the system prompt
            # so we don't need to inject it again
        else:
            pass  # Fall through to legacy prompt below

        if not custom_system_prompt:
            system_prompt = """You are an expert at analyzing company websites to determine if they match a B2B target customer segment. You use a strict multi-criteria scoring system.

CRITICAL RULES — violations mean AUTOMATIC FAILURE:
1. Website language must be compatible with target geography. For Russian market: non-Russian site = language_match 0. For UAE/Dubai market: English OR Russian OR Arabic are all acceptable.
2. If your reasoning says the company doesn't match → confidence MUST be < 0.3, is_target MUST be false
3. Aggregators, directories, news sites, job boards, freelancer platforms, property listing portals → ALWAYS is_target = false
4. Mega-corporations and publicly-traded developers (e.g. DAMAC, Emaar, Nakheel, Aldar, Meraas, Dubai Properties) → is_target = false unless the target segment EXPLICITLY includes them
5. Ukraine-based companies → ALWAYS is_target = false. Any company located in Ukraine or primarily serving the Ukrainian market must be excluded.
6. Target companies should work with HNWI (high net worth individuals) — not only luxury-focused but ANY company that facilitates cross-border financial operations, real estate, migration, legal services for wealthy clients.
7. When in doubt → score LOW. False positives are WORSE than false negatives.
8. confidence = MINIMUM of all individual scores (never higher)

Respond ONLY with valid JSON."""

            prompt = f"""{knowledge_context}TARGET SEGMENT: {target_segments}

{website_context}

Score each criterion 0.0–1.0, then set confidence = MINIMUM of all scores.

Respond with JSON:
{{
  "scores": {{
    "language_match": 0.0-1.0,
    "industry_match": 0.0-1.0,
    "service_match": 0.0-1.0,
    "company_type": 0.0-1.0,
    "geography_match": 0.0-1.0
  }},
  "is_target": true/false,
  "matched_segment": "one of: real_estate, investment, legal, migration, family_office, crypto, importers, other_hnwi, not_target",
  "confidence": 0.0-1.0,
  "reasoning": "1-2 sentence explanation",
  "company_info": {{
    "name": "the ACTUAL company name from the WEBSITE (NOT the client/searcher name from TARGET SEGMENT)",
    "description": "what they do",
    "services": ["list", "of", "services"],
    "location": "location if found",
    "industry": "detected industry"
  }}
}}

SCORING GUIDE:
- language_match: 1.0 if site language is compatible with target geography/clients. If target mentions Russian-speaking clients: Russian-language sites score 1.0, English sites in international hubs (Cyprus, Monaco, UAE, etc.) score 0.7-0.8. Pure local-language sites (Thai, Turkish, etc.) without Russian/English = 0.2.
- industry_match: 1.0 if exact match to target segment. 0.7 if adjacent/close. 0.3 if loosely related. 0.0 if completely wrong industry. Read the TARGET SEGMENT carefully and match against THAT, not some generic idea.
- service_match: 1.0 if the company's services directly match what's described in the target segment. 0.5 if partially overlapping. 0.0 for aggregators, directories, listing portals, news sites.
- company_type: 1.0 for real operating B2B companies providing services, 0.5 for small agencies/solo consultants, 0.3 for franchises/reseller pages, 0 for aggregators/news/directories/job boards/portals
- geography_match: 1.0 if serves target geography, 0.5 if partially overlaps, 0 if completely different region

CRITICAL FALSE POSITIVE RULES:
- Aggregators, directories, news sites, job boards, property listing portals, forums → ALWAYS is_target = false
- Blog sites, informational sites, personal blogs → ALWAYS is_target = false
- Companies that don't provide any of the services described in TARGET SEGMENT → is_target = false
- IMPORTANT: "name" in company_info must be the name of the company whose WEBSITE you are analyzing, extracted from the website content (title, logo, about page). NEVER use the client/searcher name from the TARGET SEGMENT description. If you cannot find the company name on the website, use the domain name."""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 600,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            # Retry with backoff on 429
            resp = None
            for attempt in range(4):
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                if resp.status_code == 429:
                    import random as _rng
                    wait = min(2.0 * (2 ** attempt), 20.0) + _rng.uniform(0, 1)
                    logger.warning(f"OpenAI 429 for {domain}, backoff {wait:.1f}s (attempt {attempt + 1}/4)")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            if resp is None or resp.status_code == 429:
                return {"is_target": False, "confidence": 0, "reasoning": "OpenAI rate limited",
                        "company_info": {}, "scores": {}, "tokens_used": 0}

            data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            # Parse JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    result = json.loads(content[start:end + 1])
                else:
                    result = {
                        "is_target": False, "confidence": 0,
                        "reasoning": f"Failed to parse GPT response: {content[:200]}",
                        "company_info": {}, "scores": {},
                    }

            # Ensure scores dict exists
            if "scores" not in result:
                result["scores"] = {}

            # Normalize segment key: v2 prompt uses "segment", legacy uses "matched_segment"
            if "segment" in result and "matched_segment" not in result:
                result["matched_segment"] = result["segment"]
            # Normalize NOT_A_MATCH → is_target=false
            seg = result.get("matched_segment", "") or result.get("segment", "")
            if seg and seg.upper() in ("NOT_A_MATCH", "NOT_TARGET"):
                result["is_target"] = False
                result["matched_segment"] = "NOT_A_MATCH"

            # Phase 1c: Post-processing validation (skip for custom prompts — via negativa handles its own)
            if not custom_system_prompt:
                result = self._validate_analysis(result, clean, target_segments=target_segments)

            result["tokens_used"] = tokens_used
            # Store the exact prompts sent to GPT for full reproducibility
            result["_prompt_sent"] = {
                "system": system_prompt,
                "user": prompt,
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "max_tokens": 600,
            }
            return result

        except Exception as e:
            logger.error(f"GPT analysis failed for {domain}: {e}")
            return {
                "is_target": False, "confidence": 0,
                "reasoning": f"Analysis error: {str(e)}",
                "company_info": {}, "scores": {},
                "tokens_used": 0,
            }

    async def _scrape_and_analyze_domains(
        self,
        session: AsyncSession,
        job: SearchJob,
        domains: List[str],
        target_segments: str,
    ) -> None:
        """
        Scrape and analyze each domain, store results.

        Uses Crona API for batch scraping (JS-rendered, 1 credit/domain) when configured,
        falls back to direct httpx scraping otherwise.
        """
        total_tokens = (job.config or {}).get("openai_tokens_used", 0)
        crona_credits_used = 0

        # Filter out already-analyzed domains for this PROJECT (batch query, not per-domain)
        existing_result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == job.project_id,
                SearchResult.domain.in_(domains),
            )
        )
        existing_domains = {row[0] for row in existing_result.fetchall()}
        to_analyze = [d for d in domains if d not in existing_domains]

        if not to_analyze:
            return

        # --- Scrape phase: choose method based on project config ---
        # Priority: project.auto_enrich_config.scrape_method > crona > apify_proxy > httpx
        from app.services.crona_service import crona_service

        scraped_texts: Dict[str, Optional[str]] = {}
        scrape_method = "httpx"  # default

        # Check project-level scrape method preference
        project_scrape_method = None
        if job.project_id:
            proj_result = await session.execute(
                select(Project).where(Project.id == job.project_id)
            )
            proj = proj_result.scalar_one_or_none()
            if proj and proj.auto_enrich_config:
                project_scrape_method = proj.auto_enrich_config.get("scrape_method")

        if project_scrape_method == "apify_proxy" and settings.APIFY_PROXY_PASSWORD:
            # Apify residential proxy — IP rotation, no JS rendering but handles blocks
            import random
            logger.info(f"Using Apify residential proxy to scrape {len(to_analyze)} domains")
            semaphore = asyncio.Semaphore(10)

            async def scrape_apify(domain: str):
                async with semaphore:
                    proxy_url = self._build_apify_proxy_url(f"s_{random.randint(10000,99999)}")
                    html = await self.scrape_domain(domain, proxy_url=proxy_url)
                    scraped_texts[domain] = html

            await asyncio.gather(*[scrape_apify(d) for d in to_analyze], return_exceptions=True)
            apify_success = sum(1 for v in scraped_texts.values() if v and len(v) >= 50)
            logger.info(f"Apify proxy scraped {len(to_analyze)} domains: {apify_success} with content")
            scrape_method = "apify_proxy"

        elif project_scrape_method != "httpx" and crona_service.is_configured:
            # Crona batch scrape (JS-rendered, handles SPA sites)
            batch_size = 50
            crona_semaphore = asyncio.Semaphore(3)

            async def scrape_crona_batch(batch: List[str]) -> Dict[str, Optional[str]]:
                async with crona_semaphore:
                    return await crona_service.scrape_domains(batch)

            batches = [to_analyze[i:i + batch_size] for i in range(0, len(to_analyze), batch_size)]
            batch_results = await asyncio.gather(
                *[scrape_crona_batch(b) for b in batches],
                return_exceptions=True,
            )
            for result in batch_results:
                if isinstance(result, dict):
                    scraped_texts.update(result)
                elif isinstance(result, Exception):
                    logger.error(f"Crona batch failed: {result}")

            crona_credits_used = crona_service.credits_used
            crona_success = sum(1 for v in scraped_texts.values() if v)
            if crona_success > 0:
                scrape_method = "crona"
                logger.info(f"Crona scraped {len(to_analyze)} domains: {crona_success} success, credits_used={crona_credits_used}")
            else:
                logger.warning(f"Crona returned 0 content (likely out of credits), falling back to httpx")
                scraped_texts.clear()

        if scrape_method == "httpx":
            # Fallback: direct httpx (no proxy, no JS rendering)
            logger.info(f"Using httpx to scrape {len(to_analyze)} domains")
            semaphore = asyncio.Semaphore(10)

            async def scrape_one(domain: str):
                async with semaphore:
                    html = await self.scrape_domain(domain)
                    scraped_texts[domain] = html

            await asyncio.gather(*[scrape_one(d) for d in to_analyze], return_exceptions=True)
            httpx_success = sum(1 for v in scraped_texts.values() if v and len(v) >= 50)
            logger.info(f"httpx scraped {len(to_analyze)} domains: {httpx_success} with content")

        scraped_at = datetime.utcnow()

        # Read domain→query mapping from ALL jobs for this project (not just current)
        # so domains found by earlier jobs also get source_query_id
        domain_to_query: Dict[str, int] = {}
        if job.project_id:
            all_jobs_result = await session.execute(
                select(SearchJob.config).where(
                    SearchJob.project_id == job.project_id,
                    SearchJob.config.isnot(None),
                )
            )
            for (config,) in all_jobs_result.fetchall():
                if config and isinstance(config, dict) and "domain_to_query" in config:
                    for d, qid in config["domain_to_query"].items():
                        if d not in domain_to_query:
                            domain_to_query[d] = qid
        else:
            domain_to_query = (job.config or {}).get("domain_to_query", {})

        # --- Analyze phase: GPT scoring (uses global semaphore) ---

        async def analyze_domain(domain: str):
            nonlocal total_tokens
            async with _gpt_analysis_semaphore:
                content = scraped_texts.get(domain)
                source_qid = domain_to_query.get(domain)

                if not content or len(content) < 50:
                    sr = SearchResult(
                        search_job_id=job.id,
                        project_id=job.project_id,
                        domain=domain,
                        url=f"https://{domain}",
                        is_target=False,
                        confidence=0,
                        reasoning="Failed to scrape website",
                        scraped_at=scraped_at,
                        source_query_id=source_qid,
                    )
                    session.add(sr)
                    return

                # Crona returns clean text; httpx and apify_proxy return HTML
                analysis = await self.analyze_company(
                    content, target_segments, domain,
                    is_html=(scrape_method != "crona"),
                )
                analyzed_at = datetime.utcnow()

                total_tokens += analysis.get("tokens_used", 0)

                sr = SearchResult(
                    search_job_id=job.id,
                    project_id=job.project_id,
                    domain=domain,
                    url=f"https://{domain}",
                    is_target=analysis.get("is_target", False),
                    confidence=analysis.get("confidence", 0),
                    reasoning=analysis.get("reasoning", ""),
                    company_info=analysis.get("company_info", {}),
                    scores=analysis.get("scores", {}),
                    matched_segment=analysis.get("matched_segment"),
                    html_snippet=content[:2000].replace("\x00", "") if content else None,
                    scraped_at=scraped_at,
                    analyzed_at=analyzed_at,
                    source_query_id=source_qid,
                )
                session.add(sr)

        # Process in batches of 20
        batch_size = 20
        for i in range(0, len(to_analyze), batch_size):
            batch = to_analyze[i:i + batch_size]
            tasks = [analyze_domain(d) for d in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.flush()

        # Update job config with token and credit usage
        config = dict(job.config or {})
        config["openai_tokens_used"] = total_tokens
        if scrape_method == "crona":
            config["crona_credits_used"] = config.get("crona_credits_used", 0) + crona_credits_used
        config["scrape_method"] = scrape_method
        config["analysis_model"] = "gpt-4o-mini"
        job.config = config

        # Auto-promote results to pipeline
        try:
            from app.services.pipeline_service import pipeline_service
            promoted = await pipeline_service.promote_search_results(session, job.id)
            logger.info(f"Auto-promoted {promoted} companies to pipeline from job {job.id}")
        except Exception as e:
            logger.error(f"Auto-promote failed for job {job.id}: {e}")

        # Auto-review results for quality assurance (Phase 2)
        try:
            from app.services.review_service import review_service
            review_stats = await review_service.review_batch(session, job.id, target_segments)
            review_tokens = review_stats.get("review_tokens_used", 0)
            if review_tokens:
                config = dict(job.config or {})
                config["review_tokens"] = config.get("review_tokens", 0) + review_tokens
                config["openai_tokens_used"] = config.get("openai_tokens_used", 0) + review_tokens
                job.config = config
            logger.info(f"Auto-review for job {job.id}: {review_stats}")
        except Exception as e:
            logger.error(f"Auto-review failed for job {job.id}: {e}")

        # Auto-enrichment: extract contacts & optionally Apollo-enrich target companies
        try:
            await self._auto_enrich_targets(session, job)
        except Exception as e:
            logger.error(f"Auto-enrich failed for job {job.id}: {e}")

    async def _auto_enrich_targets(self, session: AsyncSession, job) -> None:
        """Auto-extract contacts (and optionally Apollo-enrich) for target companies if project config allows."""
        if not job.project_id:
            return

        from app.models.contact import Project
        from app.models.pipeline import DiscoveredCompany
        from app.services.pipeline_service import pipeline_service

        proj_result = await session.execute(
            select(Project).where(Project.id == job.project_id)
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            return

        # Use saved config or defaults (auto_extract=True by default for new projects)
        cfg = project.auto_enrich_config or {
            "auto_extract": True,
            "auto_apollo": False,
            "apollo_titles": ["CEO", "Founder", "Managing Director", "Owner"],
            "apollo_max_people": 5,
            "apollo_max_credits": 50,
        }
        if not cfg.get("auto_extract"):
            return

        # Get target company IDs from this job
        target_q = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.search_job_id == job.id,
                DiscoveredCompany.is_target == True,
            )
        )
        target_ids = [row[0] for row in target_q.fetchall()]
        if not target_ids:
            logger.info(f"Auto-enrich: no target companies in job {job.id}")
            return

        # Auto-extract contacts
        extract_stats = await pipeline_service.extract_contacts_batch(
            session=session,
            discovered_company_ids=target_ids,
            company_id=job.company_id,
        )
        logger.info(f"Auto-extract for job {job.id}: {extract_stats}")

        # Auto Apollo enrichment (opt-in)
        if cfg.get("auto_apollo"):
            apollo_stats = await pipeline_service.enrich_apollo_batch(
                session=session,
                discovered_company_ids=target_ids,
                company_id=job.company_id,
                max_people=cfg.get("apollo_max_people", 5),
                titles=cfg.get("apollo_titles"),
                max_credits=cfg.get("apollo_max_credits", 50),
            )
            logger.info(f"Auto-Apollo for job {job.id}: {apollo_stats}")

    async def get_project_results(
        self,
        session: AsyncSession,
        project_id: int,
        targets_only: bool = False,
    ) -> List[SearchResult]:
        """Get analyzed results for a project."""
        query = select(SearchResult).where(
            SearchResult.project_id == project_id,
        )
        if targets_only:
            query = query.where(SearchResult.is_target == True)
        query = query.order_by(
            SearchResult.is_target.desc(),
            SearchResult.confidence.desc(),
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_project_spending(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> Dict[str, Any]:
        """Calculate spending for a project's search jobs (Yandex + Google + AI + Crona)."""
        from app.models.domain import SearchEngine

        result = await session.execute(
            select(SearchJob).where(SearchJob.project_id == project_id)
        )
        jobs = result.scalars().all()

        yandex_queries = 0
        google_queries = 0
        total_queries = 0
        total_ai_tokens = 0
        total_crona_credits = 0
        total_query_gen_tokens = 0
        total_review_tokens = 0
        gemini_analysis_tokens = 0
        openai_analysis_tokens = 0

        for job in jobs:
            job_queries = job.queries_total or 0
            total_queries += job_queries
            # Split queries by search engine
            if job.search_engine == SearchEngine.GOOGLE_SERP:
                google_queries += job_queries
            elif job.search_engine == SearchEngine.YANDEX_API:
                yandex_queries += job_queries
            else:
                # Apollo/Clay searches don't have query costs per se
                pass

            config = job.config or {}
            job_tokens = config.get("openai_tokens_used", 0)
            total_ai_tokens += job_tokens
            total_crona_credits += config.get("crona_credits_used", 0)
            total_query_gen_tokens += config.get("query_gen_tokens", 0)
            total_review_tokens += config.get("review_tokens", 0)

            # Split analysis tokens by model used
            analysis_model = config.get("analysis_model", "gpt-4o-mini")
            job_analysis_tokens = max(0, job_tokens - config.get("review_tokens", 0))
            if "gemini" in analysis_model:
                gemini_analysis_tokens += job_analysis_tokens
            else:
                openai_analysis_tokens += job_analysis_tokens

        # Determine query gen model (check latest job)
        query_gen_model = "gpt-4o-mini"
        if jobs:
            latest_config = jobs[-1].config or {}
            query_gen_model = latest_config.get("query_gen_model", "gpt-4o-mini")
        query_gen_is_gemini = "gemini" in query_gen_model

        # Search costs: split by engine
        yandex_requests = yandex_queries * settings.SEARCH_MAX_PAGES
        yandex_cost = (yandex_requests / 1000) * YANDEX_COST_PER_1K_REQUESTS

        google_requests = google_queries * settings.SEARCH_MAX_PAGES
        google_cost = (google_requests / 1000) * GOOGLE_SERP_COST_PER_1K_REQUESTS

        # AI cost estimate — split by model
        openai_tokens = openai_analysis_tokens + total_review_tokens
        gemini_tokens = gemini_analysis_tokens
        if query_gen_is_gemini:
            gemini_tokens += total_query_gen_tokens
        else:
            openai_tokens += total_query_gen_tokens

        openai_cost = (openai_tokens / 1_000_000) * OPENAI_COST_PER_1M_INPUT_TOKENS
        gemini_cost = (gemini_tokens / 1_000_000) * GEMINI_COST_PER_1M_TOKENS

        # Crona cost: 1 credit = ~$0.001 (approximate)
        crona_cost = total_crona_credits * 0.001

        ai_cost = openai_cost + gemini_cost
        search_cost = yandex_cost + google_cost
        return {
            "queries_count": total_queries,
            "yandex_queries": yandex_queries,
            "google_queries": google_queries,
            "yandex_cost": round(yandex_cost, 4),
            "google_cost": round(google_cost, 4),
            "openai_tokens_used": openai_tokens,
            "openai_cost_estimate": round(openai_cost, 4),
            "gemini_tokens_used": gemini_tokens,
            "gemini_cost_estimate": round(gemini_cost, 4),
            "ai_cost_estimate": round(ai_cost, 4),
            "openai_analysis_tokens": openai_analysis_tokens,
            "gemini_analysis_tokens": gemini_analysis_tokens,
            "openai_query_gen_tokens": total_query_gen_tokens if not query_gen_is_gemini else 0,
            "gemini_query_gen_tokens": total_query_gen_tokens if query_gen_is_gemini else 0,
            "openai_review_tokens": total_review_tokens,
            "crona_credits_used": total_crona_credits,
            "crona_cost": round(crona_cost, 4),
            "total_estimate": round(search_cost + ai_cost + crona_cost, 4),
        }


# Module-level singleton
company_search_service = CompanySearchService()
