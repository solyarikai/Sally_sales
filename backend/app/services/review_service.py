"""
Review Service — Auto-review + manual review + knowledge accumulation.

Phase 2: Auto-reviews search results in batches via GPT-4o for quality assurance.
Phase 3: Tracks query effectiveness after review.
Phase 4: Accumulates project knowledge from review outcomes.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.domain import (
    SearchJob, SearchQuery, SearchResult,
    ProjectSearchKnowledge, ProjectBlacklist,
)

logger = logging.getLogger(__name__)


class ReviewService:
    """Handles auto-review, manual review, and knowledge accumulation."""

    # ------------------------------------------------------------------
    # Phase 2a: Auto-review batch
    # ------------------------------------------------------------------

    async def review_batch(
        self,
        session: AsyncSession,
        job_id: int,
        target_segments: str,
    ) -> Dict[str, int]:
        """
        Second-pass quality check on search results using GPT-4o.

        Sends batches of ~20 results for a quick review pass.
        Verdicts: CONFIRM / REJECT / FLAG.

        Returns: {"confirmed": N, "rejected": N, "flagged": N}
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.warning("No OpenAI API key, skipping auto-review")
            return {"confirmed": 0, "rejected": 0, "flagged": 0}

        # Load results that need review
        result = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.review_status.is_(None),
            ).order_by(SearchResult.confidence.desc())
        )
        results = list(result.scalars().all())

        if not results:
            return {"confirmed": 0, "rejected": 0, "flagged": 0, "review_tokens_used": 0}

        stats = {"confirmed": 0, "rejected": 0, "flagged": 0}
        self._last_review_tokens = 0

        # Process in batches of 20
        batch_size = 20
        for i in range(0, len(results), batch_size):
            batch = results[i:i + batch_size]
            verdicts = await self._review_batch_gpt(batch, target_segments, api_key)
            await self._apply_review_results(session, batch, verdicts)

            for v in verdicts:
                verdict = v.get("verdict", "flagged").lower()
                if verdict in stats:
                    stats[verdict] += 1

        await session.flush()

        # Phase 3: compute query effectiveness after review
        await self.compute_query_effectiveness(session, job_id)

        # Phase 4: update project knowledge
        job_result = await session.execute(
            select(SearchJob.project_id).where(SearchJob.id == job_id)
        )
        project_id = job_result.scalar_one_or_none()
        if project_id:
            await self.update_project_knowledge(session, project_id)

        stats["review_tokens_used"] = self._last_review_tokens
        logger.info(f"Auto-review for job {job_id}: {stats}")
        return stats

    async def _review_batch_gpt(
        self,
        results: List[SearchResult],
        target_segments: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        """Send batch of results to GPT-4o for review."""
        items = []
        for r in results:
            scores = r.scores or {}
            items.append({
                "id": r.id,
                "domain": r.domain,
                "is_target": r.is_target,
                "confidence": r.confidence,
                "reasoning": (r.reasoning or "")[:200],
                "scores": scores,
                "company_name": (r.company_info or {}).get("name", ""),
                "industry": (r.company_info or {}).get("industry", ""),
            })

        prompt = f"""Review these search results for quality. Target segment: {target_segments}

RESULTS:
{json.dumps(items, ensure_ascii=False, indent=1)}

For each result, provide a verdict:
- CONFIRM: clearly matches target segment, scores and reasoning are consistent
- REJECT: clearly does NOT match (wrong industry, wrong geography, aggregator, etc.)
- FLAG: uncertain, needs human review

Return JSON array with one object per result:
[{{"id": 123, "verdict": "CONFIRM|REJECT|FLAG", "note": "brief reason"}}]

RULES:
- If is_target=true but scores show language_match<0.3, verdict=REJECT
- If reasoning says "doesn't match" but is_target=true, verdict=REJECT
- CRM tools, job boards, news sites, directories → always REJECT
- When in doubt → FLAG (don't auto-confirm uncertain results)"""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a search quality reviewer. Return ONLY valid JSON array."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            self._last_review_tokens = getattr(self, "_last_review_tokens", 0) + usage.get("total_tokens", 0)

            try:
                verdicts = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("[")
                end = content.rfind("]")
                if start != -1 and end != -1:
                    verdicts = json.loads(content[start:end + 1])
                else:
                    logger.warning("Failed to parse review response, flagging all")
                    return [{"id": r.id, "verdict": "FLAG", "note": "Parse error"} for r in results]

            return verdicts if isinstance(verdicts, list) else []

        except Exception as e:
            logger.error(f"GPT review failed: {e}")
            return [{"id": r.id, "verdict": "FLAG", "note": f"Review error: {str(e)[:100]}"} for r in results]

    async def _apply_review_results(
        self,
        session: AsyncSession,
        results: List[SearchResult],
        verdicts: List[Dict[str, Any]],
    ) -> None:
        """Apply review verdicts to SearchResult records."""
        verdict_map = {v["id"]: v for v in verdicts if "id" in v}
        now = datetime.utcnow()

        for r in results:
            v = verdict_map.get(r.id)
            if not v:
                continue

            verdict = v.get("verdict", "FLAG").upper()
            note = v.get("note", "")

            if verdict == "CONFIRM":
                r.review_status = "confirmed"
            elif verdict == "REJECT":
                r.review_status = "rejected"
                # Override is_target for rejected results
                if r.is_target:
                    r.is_target = False
                    r.confidence = min(r.confidence or 0, 0.2)
            else:
                r.review_status = "flagged"

            r.review_note = note
            r.reviewed_at = now

        # Auto-blacklist rejected domains
        try:
            for r in results:
                if r.review_status == "rejected" and r.project_id and r.domain:
                    # Upsert into ProjectBlacklist
                    existing = await session.execute(
                        select(ProjectBlacklist).where(
                            ProjectBlacklist.project_id == r.project_id,
                            ProjectBlacklist.domain == r.domain,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        session.add(ProjectBlacklist(
                            project_id=r.project_id,
                            domain=r.domain,
                            reason=r.review_note or "Auto-rejected by review",
                            source="auto_review",
                        ))
        except Exception as e:
            logger.warning(f"Failed to auto-blacklist rejected domains: {e}")

        # Also update corresponding DiscoveredCompany records for rejections
        try:
            from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
            for r in results:
                if r.review_status == "rejected" and r.discovered_company_id:
                    dc_result = await session.execute(
                        select(DiscoveredCompany).where(
                            DiscoveredCompany.id == r.discovered_company_id
                        )
                    )
                    dc = dc_result.scalar_one_or_none()
                    if dc:
                        dc.status = DiscoveredCompanyStatus.REJECTED
        except Exception as e:
            logger.warning(f"Failed to update DiscoveredCompany on rejection: {e}")

    # ------------------------------------------------------------------
    # Phase 2d: Manual review
    # ------------------------------------------------------------------

    async def manual_review(
        self,
        session: AsyncSession,
        result_id: int,
        verdict: str,
        note: Optional[str] = None,
    ) -> SearchResult:
        """Apply a human review verdict to a single result."""
        result = await session.execute(
            select(SearchResult).where(SearchResult.id == result_id)
        )
        sr = result.scalar_one_or_none()
        if not sr:
            raise ValueError(f"SearchResult {result_id} not found")

        sr.review_status = verdict
        sr.review_note = note
        sr.reviewed_at = datetime.utcnow()

        if verdict == "rejected":
            sr.is_target = False
            sr.confidence = min(sr.confidence or 0, 0.2)
            # Auto-blacklist on manual rejection
            if sr.project_id and sr.domain:
                existing = await session.execute(
                    select(ProjectBlacklist).where(
                        ProjectBlacklist.project_id == sr.project_id,
                        ProjectBlacklist.domain == sr.domain,
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(ProjectBlacklist(
                        project_id=sr.project_id,
                        domain=sr.domain,
                        reason=note or "Manual rejection",
                        source="manual",
                    ))
        elif verdict == "confirmed":
            sr.is_target = True

        await session.flush()
        return sr

    async def get_review_summary(
        self,
        session: AsyncSession,
        job_id: int,
    ) -> Dict[str, Any]:
        """Get review statistics for a job."""
        total = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job_id,
            )
        )
        total_count = total.scalar() or 0

        confirmed = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.review_status == "confirmed",
            )
        )
        rejected = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.review_status == "rejected",
            )
        )
        flagged = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.review_status == "flagged",
            )
        )
        unreviewed = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.review_status.is_(None),
            )
        )

        return {
            "total": total_count,
            "confirmed": confirmed.scalar() or 0,
            "rejected": rejected.scalar() or 0,
            "flagged": flagged.scalar() or 0,
            "unreviewed": unreviewed.scalar() or 0,
        }

    # ------------------------------------------------------------------
    # Phase 3: Query effectiveness
    # ------------------------------------------------------------------

    async def compute_query_effectiveness(
        self,
        session: AsyncSession,
        job_id: int,
    ) -> None:
        """Compute effectiveness scores for each query in a job."""
        # Get all queries for this job
        q_result = await session.execute(
            select(SearchQuery).where(SearchQuery.search_job_id == job_id)
        )
        queries = list(q_result.scalars().all())

        # Get confirmed results with source_query_id
        results = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job_id,
                SearchResult.source_query_id.isnot(None),
            )
        )
        all_results = list(results.scalars().all())

        # Count targets per query
        query_targets: Dict[int, int] = {}
        for r in all_results:
            if r.review_status == "confirmed" or (r.is_target and r.review_status != "rejected"):
                query_targets[r.source_query_id] = query_targets.get(r.source_query_id, 0) + 1

        for q in queries:
            targets = query_targets.get(q.id, 0)
            q.targets_found = targets
            q.effectiveness_score = targets / max(q.domains_found or 1, 1)

        await session.flush()

    # ------------------------------------------------------------------
    # Phase 4: Project knowledge accumulation
    # ------------------------------------------------------------------

    async def update_project_knowledge(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> ProjectSearchKnowledge:
        """
        Aggregate all reviewed results for a project → extract patterns → update knowledge.
        """
        # Get or create knowledge record
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = result.scalar_one_or_none()
        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=project_id)
            session.add(knowledge)

        # Load all reviewed results for this project
        results = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == project_id,
                SearchResult.review_status.isnot(None),
            )
        )
        reviewed = list(results.scalars().all())

        confirmed = [r for r in reviewed if r.review_status == "confirmed"]
        rejected = [r for r in reviewed if r.review_status == "rejected"]

        # Update stats
        knowledge.total_domains_analyzed = len(reviewed)
        knowledge.total_targets_found = len(confirmed)
        knowledge.total_false_positives = len(rejected)

        # Count jobs
        jobs_result = await session.execute(
            select(func.count()).select_from(SearchJob).where(
                SearchJob.project_id == project_id,
            )
        )
        knowledge.total_jobs_run = jobs_result.scalar() or 0

        # Extract patterns from confirmed targets
        knowledge.confirmed_domains = [r.domain for r in confirmed][:200]
        knowledge.rejected_domains = [r.domain for r in rejected][:200]

        # Extract industry keywords from confirmed targets
        industry_kw = set()
        anti_kw = set()
        for r in confirmed:
            info = r.company_info or {}
            if info.get("industry"):
                industry_kw.add(info["industry"])
            for svc in (info.get("services") or []):
                if svc:
                    industry_kw.add(svc)

        for r in rejected:
            info = r.company_info or {}
            if info.get("industry"):
                anti_kw.add(info["industry"])

        knowledge.industry_keywords = list(industry_kw)[:100]
        knowledge.anti_keywords = list(anti_kw)[:100]

        # Confidence calibration
        if confirmed:
            knowledge.avg_target_confidence = sum(r.confidence or 0 for r in confirmed) / len(confirmed)
        if rejected:
            knowledge.avg_false_positive_confidence = sum(r.confidence or 0 for r in rejected) / len(rejected)

        # Query effectiveness patterns
        queries_result = await session.execute(
            select(SearchQuery).where(
                SearchQuery.search_job_id.in_(
                    select(SearchJob.id).where(SearchJob.project_id == project_id)
                ),
                SearchQuery.effectiveness_score.isnot(None),
            ).order_by(SearchQuery.effectiveness_score.desc())
        )
        all_queries = list(queries_result.scalars().all())

        good_qs = [q.query_text for q in all_queries if (q.effectiveness_score or 0) > 0.3][:50]
        bad_qs = [q.query_text for q in all_queries if (q.effectiveness_score or 0) == 0 and (q.domains_found or 0) > 0][:50]

        knowledge.good_query_patterns = good_qs
        knowledge.bad_query_patterns = bad_qs

        knowledge.updated_at = datetime.utcnow()
        await session.flush()

        logger.info(
            f"Updated knowledge for project {project_id}: "
            f"confirmed={len(confirmed)}, rejected={len(rejected)}, "
            f"good_queries={len(good_qs)}, bad_queries={len(bad_qs)}"
        )
        return knowledge


# Module-level singleton
review_service = ReviewService()
