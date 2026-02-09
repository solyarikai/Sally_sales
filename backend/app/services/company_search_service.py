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
    DomainSource, ProjectSearchKnowledge,
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

    async def run_project_search(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        max_queries: int = 100,
        job_id: Optional[int] = None,
    ) -> SearchJob:
        """
        Full pipeline: generate queries -> Yandex search -> filter -> scrape -> analyze.

        If job_id is provided, uses that existing job (updates it).
        Otherwise creates a new one.
        Returns the SearchJob with results populated.
        """
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

        # Load project knowledge for feedback loop (Phase 4)
        knowledge_data = None
        try:
            k_result = await session.execute(
                select(ProjectSearchKnowledge).where(
                    ProjectSearchKnowledge.project_id == project_id
                )
            )
            knowledge = k_result.scalar_one_or_none()
            if knowledge:
                knowledge_data = {
                    "good_query_patterns": knowledge.good_query_patterns or [],
                    "bad_query_patterns": knowledge.bad_query_patterns or [],
                    "confirmed_domains": knowledge.confirmed_domains or [],
                    "rejected_domains": knowledge.rejected_domains or [],
                    "industry_keywords": knowledge.industry_keywords or [],
                    "anti_keywords": knowledge.anti_keywords or [],
                }
        except Exception as e:
            logger.warning(f"Failed to load project knowledge: {e}")

        # 2. Generate queries via GPT-4o-mini (with knowledge feedback)
        logger.info(f"Generating {max_queries} queries for project {project_id}: {target_segments}")

        # Feed effective/ineffective queries from past jobs (Phase 3d)
        good_queries = (knowledge_data or {}).get("good_query_patterns", [])
        bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

        queries = await search_service.generate_queries(
            session=session,
            count=max_queries,
            model="gpt-4o-mini",
            target_segments=target_segments,
            project_id=project_id,
            good_queries=good_queries,
            bad_queries=bad_queries,
        )
        logger.info(f"Generated {len(queries)} queries")

        if not queries:
            raise ValueError("Query generation returned no results")

        # 3. Get or create SearchJob
        query_gen_prompt = f"target_segments: {target_segments}"
        job_config = {
            "max_queries": max_queries,
            "target_segments": target_segments,
            "query_generation_prompt": query_gen_prompt,
            "max_pages": settings.SEARCH_MAX_PAGES,
            "workers": settings.SEARCH_WORKERS,
            "openai_tokens_used": 0,
            "queries_generated": len(queries),
        }

        if job_id:
            # Use existing placeholder job
            result = await session.execute(
                select(SearchJob).where(SearchJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            job.queries_total = len(queries)
            job.config = job_config
        else:
            job = SearchJob(
                company_id=company_id,
                status=SearchJobStatus.PENDING,
                search_engine=SearchEngine.YANDEX_API,
                queries_total=len(queries),
                project_id=project_id,
                config=job_config,
            )
            session.add(job)
            await session.flush()

        for q_text in queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
            )
            session.add(sq)

        await session.commit()

        # 4. Run Yandex search (updates job status/counters)
        logger.info(f"Starting Yandex search job {job.id} with {len(queries)} queries")
        await search_service.run_search_job(session, job.id)

        # Reload job to get updated stats
        await session.refresh(job)

        # 5. Scrape and analyze new domains
        new_domains = await self._get_new_domains_from_job(session, job)
        logger.info(f"Job {job.id} found {len(new_domains)} new domains to analyze")

        if new_domains:
            await self._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=target_segments,
            )

        await session.commit()
        return job

    async def _get_new_domains_from_job(
        self,
        session: AsyncSession,
        job: SearchJob,
    ) -> List[str]:
        """Get list of new (non-trash, non-duplicate) domains found by the job."""
        from app.models.domain import Domain, DomainStatus
        # Get active domains that were sourced from search
        result = await session.execute(
            select(Domain.domain).where(
                Domain.status == DomainStatus.ACTIVE,
                Domain.source.in_([DomainSource.SEARCH_YANDEX, DomainSource.SEARCH_GOOGLE]),
            ).order_by(Domain.last_seen.desc()).limit(job.domains_new or 500)
        )
        return [row[0] for row in result.fetchall()]

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

        # Filter out already-analyzed domains
        to_analyze = []
        for domain in domains:
            existing = await session.execute(
                select(func.count()).select_from(SearchResult).where(
                    SearchResult.search_job_id == job.id,
                    SearchResult.domain == domain,
                )
            )
            if (existing.scalar() or 0) == 0:
                to_analyze.append(domain)

        if not to_analyze:
            return

        # --- Scrape phase: Crona batch or direct httpx fallback ---
        from app.services.crona_service import crona_service

        scraped_texts: Dict[str, Optional[str]] = {}
        used_crona = False

        if crona_service.is_configured:
            # Batch scrape via Crona (JS-rendered, handles SPA sites)
            batch_size = 50  # Crona handles batches well
            for i in range(0, len(to_analyze), batch_size):
                batch = to_analyze[i:i + batch_size]
                batch_results = await crona_service.scrape_domains(batch)
                scraped_texts.update(batch_results)
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

        # --- Analyze phase: GPT scoring ---
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent GPT calls

        async def analyze_domain(domain: str):
            nonlocal total_tokens
            async with semaphore:
                content = scraped_texts.get(domain)

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
                )
                session.add(sr)

        # Process in batches of 10
        batch_size = 10
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
            logger.info(f"Auto-review for job {job.id}: {review_stats}")
        except Exception as e:
            logger.error(f"Auto-review failed for job {job.id}: {e}")

    async def get_project_results(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> List[SearchResult]:
        """Get all analyzed results for a project."""
        result = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == project_id,
            ).order_by(
                SearchResult.is_target.desc(),
                SearchResult.confidence.desc(),
            )
        )
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

        for job in jobs:
            total_queries += job.queries_total or 0
            config = job.config or {}
            total_openai_tokens += config.get("openai_tokens_used", 0)
            total_crona_credits += config.get("crona_credits_used", 0)

        # Yandex cost: each query = 1 request per page, default 3 pages
        yandex_requests = total_queries * settings.SEARCH_MAX_PAGES
        yandex_cost = (yandex_requests / 1000) * YANDEX_COST_PER_1K_REQUESTS

        # OpenAI cost estimate
        openai_cost = (total_openai_tokens / 1_000_000) * OPENAI_COST_PER_1M_INPUT_TOKENS

        return {
            "queries_count": total_queries,
            "yandex_cost": round(yandex_cost, 4),
            "openai_tokens_used": total_openai_tokens,
            "openai_cost_estimate": round(openai_cost, 4),
            "crona_credits_used": total_crona_credits,
            "total_estimate": round(yandex_cost + openai_cost, 4),
        }


# Module-level singleton
company_search_service = CompanySearchService()
