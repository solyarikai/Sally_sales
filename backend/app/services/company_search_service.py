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


# Cost constants
YANDEX_COST_PER_1K_REQUESTS = 0.25  # $0.25 per 1,000 requests
OPENAI_COST_PER_1M_INPUT_TOKENS = 0.15  # GPT-4o-mini: ~$0.15 per 1M input tokens
OPENAI_COST_PER_1M_OUTPUT_TOKENS = 0.60  # GPT-4o-mini: ~$0.60 per 1M output tokens


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

    def _validate_analysis(
        self,
        analysis: Dict[str, Any],
        clean_text: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Hard rules that override GPT output to catch obvious errors.
        Modifies analysis in-place and returns it.
        """
        scores = analysis.get("scores", {})
        cyrillic_ratio = clean_text.get("cyrillic_ratio", 0.0)
        reasoning = analysis.get("reasoning", "")

        # Rule 1: Non-Russian site with Russian target → force language_match=0
        if cyrillic_ratio < 0.1:
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

        analysis["scores"] = scores
        return analysis

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
        """
        from datetime import timedelta
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

        return skip

    async def run_project_search(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        max_queries: int = 500,
        target_goal: Optional[int] = None,
        job_id: Optional[int] = None,
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
                search_engine=SearchEngine.YANDEX_API,
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

        while existing_targets < target_goal and iteration < settings.SEARCH_MAX_ITERATIONS:
            iteration += 1
            batch_size = min(settings.SEARCH_BATCH_QUERIES, max_queries - total_queries_used)
            if batch_size <= 0:
                logger.info(f"Iteration {iteration}: query budget exhausted ({total_queries_used}/{max_queries})")
                break

            logger.info(
                f"Iteration {iteration}: generating {batch_size} queries "
                f"({existing_targets}/{target_goal} targets, {total_queries_used}/{max_queries} queries used)"
            )

            # Generate queries with feedback
            queries = await search_service.generate_queries(
                session=session,
                count=batch_size,
                model="gpt-4o-mini",
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

            # Track query generation tokens
            qg_tokens = search_service.last_query_gen_tokens
            config = dict(job.config or {})
            config["query_gen_tokens"] = config.get("query_gen_tokens", 0) + qg_tokens.get("total", 0)

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

            # Run Yandex search for this batch
            logger.info(f"Iteration {iteration}: running Yandex search with {len(queries)} queries")
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
            existing_targets = await self._count_project_targets(session, project_id)

            # Reload knowledge for next iteration
            knowledge_data = await self._load_project_knowledge(session, project_id)
            good_queries = (knowledge_data or {}).get("good_query_patterns", [])
            bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

            logger.info(
                f"Iteration {iteration} complete: "
                f"{existing_targets}/{target_goal} targets found"
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

    async def scrape_domain(self, domain: str) -> Optional[str]:
        """
        Scrape website HTML via httpx.
        Returns HTML content or None if scraping fails.
        """
        url = f"https://{domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                verify=False,  # Some sites have bad SSL
            ) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 200:
                    return resp.text[:50000]  # Cap at 50KB to avoid huge pages
                else:
                    logger.warning(f"Scrape {domain}: HTTP {resp.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Scrape {domain} failed: {e}")
            return None

    async def analyze_company(
        self,
        content: str,
        target_segments: str,
        domain: str,
        knowledge: Optional[Dict[str, Any]] = None,
        is_html: bool = True,
    ) -> Dict[str, Any]:
        """
        GPT-4o-mini analyzes scraped website against target segments using
        a multi-criteria scoring rubric.

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

        system_prompt = """You are an expert at analyzing company websites to determine if they match a B2B target customer segment. You use a strict multi-criteria scoring system.

CRITICAL RULES — violations mean AUTOMATIC FAILURE:
1. Non-Russian website + Russian target geography → ALL scores = 0, is_target = false
2. If your reasoning says the company doesn't match → confidence MUST be < 0.3, is_target MUST be false
3. Aggregators, directories, news sites, job boards, freelancer platforms → ALWAYS is_target = false
4. When in doubt → score LOW. False positives are WORSE than false negatives.
5. confidence = MINIMUM of all individual scores (never higher)

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
  "confidence": 0.0-1.0,
  "reasoning": "1-2 sentence explanation",
  "company_info": {{
    "name": "company name if found",
    "description": "what they do",
    "services": ["list", "of", "services"],
    "location": "location if found",
    "industry": "detected industry"
  }}
}}

SCORING GUIDE:
- language_match: 0 if site language doesn't match target geography (e.g. English-only site for Russian market)
- industry_match: 0 if clearly wrong industry, 0.5 if adjacent, 1.0 if exact match
- service_match: how well the company's services match the target segment needs
- company_type: 1.0 for real operating companies, 0.5 for consulting/agencies, 0 for aggregators/news/directories/job boards
- geography_match: 1.0 if serves target geography, 0.5 if partially overlaps, 0 if completely different region"""

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
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
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

            # Phase 1c: Post-processing validation
            result = self._validate_analysis(result, clean)

            result["tokens_used"] = tokens_used
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

        # --- Scrape phase: Crona batch or direct httpx fallback ---
        from app.services.crona_service import crona_service

        scraped_texts: Dict[str, Optional[str]] = {}
        used_crona = False

        if crona_service.is_configured:
            # Batch scrape via Crona (JS-rendered, handles SPA sites)
            # Run up to 3 Crona batches in parallel for speed
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
            used_crona = True
            logger.info(f"Crona scraped {len(to_analyze)} domains, credits_used={crona_credits_used}")
        else:
            # Fallback: direct httpx (won't render JS)
            logger.warning("Crona not configured, falling back to direct httpx scraping")
            semaphore = asyncio.Semaphore(3)

            async def scrape_one(domain: str):
                async with semaphore:
                    html = await self.scrape_domain(domain)
                    scraped_texts[domain] = html

            await asyncio.gather(*[scrape_one(d) for d in to_analyze], return_exceptions=True)

        scraped_at = datetime.utcnow()

        # Read domain→query mapping for source_query_id tracking
        domain_to_query = (job.config or {}).get("domain_to_query", {})

        # --- Analyze phase: GPT scoring ---
        semaphore = asyncio.Semaphore(20)  # Max 20 concurrent GPT calls

        async def analyze_domain(domain: str):
            nonlocal total_tokens
            async with semaphore:
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

                # Crona returns clean text; direct httpx returns HTML
                analysis = await self.analyze_company(
                    content, target_segments, domain,
                    is_html=not used_crona,
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
                    html_snippet=content[:2000],
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
        config["crona_credits_used"] = config.get("crona_credits_used", 0) + crona_credits_used
        config["scrape_method"] = "crona" if used_crona else "httpx"
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
        """Calculate spending for a project's search jobs (Yandex + OpenAI + Crona)."""
        result = await session.execute(
            select(SearchJob).where(SearchJob.project_id == project_id)
        )
        jobs = result.scalars().all()

        total_queries = 0
        total_openai_tokens = 0
        total_crona_credits = 0
        total_query_gen_tokens = 0
        total_review_tokens = 0

        for job in jobs:
            total_queries += job.queries_total or 0
            config = job.config or {}
            total_openai_tokens += config.get("openai_tokens_used", 0)
            total_crona_credits += config.get("crona_credits_used", 0)
            total_query_gen_tokens += config.get("query_gen_tokens", 0)
            total_review_tokens += config.get("review_tokens", 0)

        # Analysis tokens = total - query_gen - review
        analysis_tokens = max(0, total_openai_tokens - total_review_tokens)

        # Yandex cost: each query = 1 request per page, default 3 pages
        yandex_requests = total_queries * settings.SEARCH_MAX_PAGES
        yandex_cost = (yandex_requests / 1000) * YANDEX_COST_PER_1K_REQUESTS

        # OpenAI cost estimate (all tokens combined)
        all_tokens = total_openai_tokens + total_query_gen_tokens
        openai_cost = (all_tokens / 1_000_000) * OPENAI_COST_PER_1M_INPUT_TOKENS

        # Crona cost: 1 credit = ~$0.001 (approximate)
        crona_cost = total_crona_credits * 0.001

        return {
            "queries_count": total_queries,
            "yandex_cost": round(yandex_cost, 4),
            "openai_tokens_used": all_tokens,
            "openai_cost_estimate": round(openai_cost, 4),
            "openai_analysis_tokens": analysis_tokens,
            "openai_query_gen_tokens": total_query_gen_tokens,
            "openai_review_tokens": total_review_tokens,
            "crona_credits_used": total_crona_credits,
            "crona_cost": round(crona_cost, 4),
            "total_estimate": round(yandex_cost + openai_cost + crona_cost, 4),
        }


# Module-level singleton
company_search_service = CompanySearchService()
