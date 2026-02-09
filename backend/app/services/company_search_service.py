"""
Company Search Service — Orchestrator for the AI-driven company search pipeline.

Full pipeline:
1. Load project, get target_segments
2. Generate queries via GPT-4o-mini using target_segments
3. Create SearchJob, run Yandex search
4. For each new domain found, scrape HTML via httpx
5. Analyze scraped HTML via GPT-4o-mini to verify target fit
6. Store results with is_target flag + GPT reasoning
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.models.contact import Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchResult,
    DomainSource,
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

        # 2. Generate queries via GPT-4o-mini
        logger.info(f"Generating {max_queries} queries for project {project_id}: {target_segments}")
        queries = await search_service.generate_queries(
            session=session,
            count=max_queries,
            model="gpt-4o-mini",
            target_segments=target_segments,
            project_id=project_id,
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
        html: str,
        target_segments: str,
        domain: str,
    ) -> Dict[str, Any]:
        """
        GPT-4o-mini analyzes scraped HTML against target segments.
        Returns: {is_target, confidence, reasoning, company_info}
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return {"is_target": False, "confidence": 0, "reasoning": "No OpenAI API key", "company_info": {}}

        # Truncate HTML for context window
        html_excerpt = html[:8000] if html else ""

        prompt = f"""Analyze this website and determine if the company matches the target segment.

TARGET SEGMENT: {target_segments}

WEBSITE DOMAIN: {domain}

WEBSITE HTML (excerpt):
{html_excerpt}

Analyze the website content and respond with JSON:
{{
  "is_target": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation why this is or isn't a target",
  "company_info": {{
    "name": "company name if found",
    "description": "brief description of what they do",
    "services": ["list", "of", "services"],
    "location": "location if found",
    "industry": "detected industry"
  }}
}}

IMPORTANT:
- is_target=true only if the company clearly operates in or serves the target segment
- confidence should reflect how sure you are (0.8+ for clear matches)
- Be strict: aggregators, news sites, and irrelevant companies should be false
- Respond with ONLY valid JSON, nothing else"""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing company websites to determine if they match a target customer segment. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
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
                # Try to extract JSON from response
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    result = json.loads(content[start:end + 1])
                else:
                    result = {
                        "is_target": False,
                        "confidence": 0,
                        "reasoning": f"Failed to parse GPT response: {content[:200]}",
                        "company_info": {},
                    }

            result["tokens_used"] = tokens_used
            return result

        except Exception as e:
            logger.error(f"GPT analysis failed for {domain}: {e}")
            return {
                "is_target": False,
                "confidence": 0,
                "reasoning": f"Analysis error: {str(e)}",
                "company_info": {},
                "tokens_used": 0,
            }

    async def _scrape_and_analyze_domains(
        self,
        session: AsyncSession,
        job: SearchJob,
        domains: List[str],
        target_segments: str,
    ) -> None:
        """Scrape and analyze each domain, store results."""
        total_tokens = (job.config or {}).get("openai_tokens_used", 0)
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent scrapes

        async def process_domain(domain: str):
            nonlocal total_tokens
            async with semaphore:
                # Check if already analyzed
                existing = await session.execute(
                    select(func.count()).select_from(SearchResult).where(
                        SearchResult.search_job_id == job.id,
                        SearchResult.domain == domain,
                    )
                )
                if (existing.scalar() or 0) > 0:
                    return

                # Scrape
                html = await self.scrape_domain(domain)
                scraped_at = datetime.utcnow()

                if not html:
                    # Store as failed scrape
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

                # Analyze with GPT
                analysis = await self.analyze_company(html, target_segments, domain)
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
                    html_snippet=html[:2000],
                    scraped_at=scraped_at,
                    analyzed_at=analyzed_at,
                )
                session.add(sr)

        # Process in batches of 10
        batch_size = 10
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            tasks = [process_domain(d) for d in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            await session.flush()

        # Update job config with token usage
        config = dict(job.config or {})
        config["openai_tokens_used"] = total_tokens
        job.config = config

        # Auto-promote results to pipeline
        try:
            from app.services.pipeline_service import pipeline_service
            promoted = await pipeline_service.promote_search_results(session, job.id)
            logger.info(f"Auto-promoted {promoted} companies to pipeline from job {job.id}")
        except Exception as e:
            logger.error(f"Auto-promote failed for job {job.id}: {e}")

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
        """Calculate spending for a project's search jobs."""
        result = await session.execute(
            select(SearchJob).where(SearchJob.project_id == project_id)
        )
        jobs = result.scalars().all()

        total_queries = 0
        total_openai_tokens = 0

        for job in jobs:
            total_queries += job.queries_total or 0
            config = job.config or {}
            total_openai_tokens += config.get("openai_tokens_used", 0)

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
            "total_estimate": round(yandex_cost + openai_cost, 4),
        }


# Module-level singleton
company_search_service = CompanySearchService()
