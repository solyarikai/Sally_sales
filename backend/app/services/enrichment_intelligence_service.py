"""
Enrichment Intelligence Service — Tracks every enrichment attempt and learns what works.

Logs attempts (success/failure/cost), aggregates effectiveness per (project, segment, source),
and recommends optimal enrichment strategy based on historical data.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.pipeline import EnrichmentAttempt, EnrichmentEffectiveness

logger = logging.getLogger(__name__)


class EnrichmentIntelligenceService:

    # ========== Attempt Logging ==========

    async def log_attempt(
        self,
        session: AsyncSession,
        discovered_company_id: int,
        source_type: str,
        method: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> int:
        """Start logging an enrichment attempt. Returns attempt_id."""
        attempt = EnrichmentAttempt(
            discovered_company_id=discovered_company_id,
            source_type=source_type,
            method=method,
            status="IN_PROGRESS",
            config=config,
        )
        session.add(attempt)
        await session.flush()
        return attempt.id

    async def update_attempt(
        self,
        session: AsyncSession,
        attempt_id: int,
        status: str,
        contacts_found: int = 0,
        emails_found: int = 0,
        credits_used: int = 0,
        cost_usd: float = 0.0,
        error_message: Optional[str] = None,
        result_summary: Optional[Dict] = None,
    ) -> None:
        """Finalize an enrichment attempt with results."""
        result = await session.execute(
            select(EnrichmentAttempt).where(EnrichmentAttempt.id == attempt_id)
        )
        attempt = result.scalar_one_or_none()
        if not attempt:
            logger.warning(f"EnrichmentAttempt {attempt_id} not found")
            return

        attempt.status = status
        attempt.contacts_found = contacts_found
        attempt.emails_found = emails_found
        attempt.credits_used = credits_used
        attempt.cost_usd = Decimal(str(cost_usd))
        attempt.error_message = error_message
        attempt.result_summary = result_summary

    # ========== Effectiveness Aggregation ==========

    async def update_effectiveness(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> None:
        """Recompute enrichment_effectiveness from enrichment_attempts for a project."""
        from app.models.pipeline import DiscoveredCompany
        from app.models.domain import SearchResult

        # Aggregate attempts grouped by segment + source_type
        # Join through discovered_company → search_result to get matched_segment
        stats_q = await session.execute(
            select(
                SearchResult.matched_segment.label("segment"),
                EnrichmentAttempt.source_type,
                func.count().label("total_attempts"),
                func.count().filter(EnrichmentAttempt.status == "SUCCESS").label("successful_attempts"),
                func.sum(EnrichmentAttempt.contacts_found).label("total_contacts_found"),
                func.sum(EnrichmentAttempt.credits_used).label("total_credits_used"),
            )
            .join(DiscoveredCompany, EnrichmentAttempt.discovered_company_id == DiscoveredCompany.id)
            .outerjoin(SearchResult, DiscoveredCompany.search_result_id == SearchResult.id)
            .where(DiscoveredCompany.project_id == project_id)
            .group_by(SearchResult.matched_segment, EnrichmentAttempt.source_type)
        )

        rows = stats_q.fetchall()
        now = datetime.utcnow()

        for row in rows:
            segment = row.segment
            source_type = row.source_type
            total = row.total_attempts or 0
            successful = row.successful_attempts or 0
            contacts = row.total_contacts_found or 0
            credits = row.total_credits_used or 0

            success_rate = Decimal(str(successful / total)) if total > 0 else Decimal("0")
            cost_per_contact = Decimal(str(credits / contacts)) if contacts > 0 else Decimal("0")

            # Upsert
            stmt = pg_insert(EnrichmentEffectiveness).values(
                project_id=project_id,
                segment=segment,
                source_type=source_type,
                total_attempts=total,
                successful_attempts=successful,
                total_contacts_found=contacts,
                total_credits_used=credits,
                success_rate=success_rate,
                cost_per_contact=cost_per_contact,
                updated_at=now,
            ).on_conflict_do_update(
                index_elements=["project_id", "segment", "source_type"],
                set_={
                    "total_attempts": total,
                    "successful_attempts": successful,
                    "total_contacts_found": contacts,
                    "total_credits_used": credits,
                    "success_rate": success_rate,
                    "cost_per_contact": cost_per_contact,
                    "updated_at": now,
                },
            )
            await session.execute(stmt)

        # Compute priority_rank per project (lower = better ROI)
        # Rank by: success_rate DESC, cost_per_contact ASC
        all_eff = await session.execute(
            select(EnrichmentEffectiveness)
            .where(EnrichmentEffectiveness.project_id == project_id)
            .order_by(
                EnrichmentEffectiveness.success_rate.desc(),
                EnrichmentEffectiveness.cost_per_contact.asc(),
            )
        )
        for rank, eff in enumerate(all_eff.scalars().all(), 1):
            eff.priority_rank = rank

        await session.flush()

    # ========== Strategy Recommendation ==========

    async def recommend_strategy(
        self,
        session: AsyncSession,
        project_id: int,
        segment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns ordered list of enrichment sources by effectiveness for a given project/segment.
        Lower priority_rank = better ROI.
        """
        filters = [EnrichmentEffectiveness.project_id == project_id]
        if segment:
            filters.append(EnrichmentEffectiveness.segment == segment)

        result = await session.execute(
            select(EnrichmentEffectiveness)
            .where(*filters)
            .order_by(EnrichmentEffectiveness.priority_rank.asc())
        )
        rows = result.scalars().all()

        if not rows:
            # Default strategy when no data exists
            return [
                {"source_type": "WEBSITE_SCRAPE", "priority": 1, "reason": "default_no_data"},
                {"source_type": "SUBPAGE_SCRAPE", "priority": 2, "reason": "default_no_data"},
                {"source_type": "APOLLO_PEOPLE", "priority": 3, "reason": "default_no_data"},
            ]

        return [
            {
                "source_type": row.source_type,
                "priority": row.priority_rank,
                "success_rate": float(row.success_rate) if row.success_rate else 0,
                "cost_per_contact": float(row.cost_per_contact) if row.cost_per_contact else 0,
                "total_contacts": row.total_contacts_found or 0,
                "total_attempts": row.total_attempts or 0,
            }
            for row in rows
        ]

    # ========== Query Helpers ==========

    async def get_attempts_for_company(
        self,
        session: AsyncSession,
        discovered_company_id: int,
    ) -> List[EnrichmentAttempt]:
        """Get all enrichment attempts for a discovered company, newest first."""
        result = await session.execute(
            select(EnrichmentAttempt)
            .where(EnrichmentAttempt.discovered_company_id == discovered_company_id)
            .order_by(EnrichmentAttempt.attempted_at.desc())
        )
        return list(result.scalars().all())

    async def has_recent_success(
        self,
        session: AsyncSession,
        discovered_company_id: int,
        source_type: str,
        days: int = 30,
    ) -> bool:
        """Check if there's a recent successful attempt for this company + source."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(func.count()).select_from(EnrichmentAttempt).where(
                EnrichmentAttempt.discovered_company_id == discovered_company_id,
                EnrichmentAttempt.source_type == source_type,
                EnrichmentAttempt.status == "SUCCESS",
                EnrichmentAttempt.attempted_at >= cutoff,
            )
        )
        return (result.scalar() or 0) > 0

    async def get_effectiveness_stats(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all effectiveness records for a project."""
        result = await session.execute(
            select(EnrichmentEffectiveness)
            .where(EnrichmentEffectiveness.project_id == project_id)
            .order_by(EnrichmentEffectiveness.priority_rank.asc())
        )
        rows = result.scalars().all()
        return [
            {
                "segment": row.segment,
                "source_type": row.source_type,
                "total_attempts": row.total_attempts,
                "successful_attempts": row.successful_attempts,
                "total_contacts_found": row.total_contacts_found,
                "total_credits_used": row.total_credits_used,
                "success_rate": float(row.success_rate) if row.success_rate else 0,
                "cost_per_contact": float(row.cost_per_contact) if row.cost_per_contact else 0,
                "priority_rank": row.priority_rank,
            }
            for row in rows
        ]


# Module-level singleton
enrichment_intelligence_service = EnrichmentIntelligenceService()
