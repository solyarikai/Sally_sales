"""
Cost Control Service — centralized pricing, cost tracking, and budget enforcement.

All API costs flow through this service for unified tracking and budget control.
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import async_session_maker

logger = logging.getLogger(__name__)


# ---- Per-unit pricing ----
PRICING: Dict[str, float] = {
    "yandex_query": 0.00025,        # $0.25 per 1K queries
    "google_query": 0.0035,         # $3.50 per 1K queries
    "apollo_credit": 0.03,          # $0.03 per credit
    "crona_credit": 0.005,          # $0.005 per credit
    "findymail_credit": 0.05,       # $0.05 per credit
    "gemini_1k_tokens": 0.00125,    # $1.25 per 1M tokens
    "openai_4o_mini_1k": 0.000375,  # $0.375 per 1M tokens
}


class CostService:
    """Centralized cost tracking and budget enforcement."""

    async def record_cost(
        self,
        session: AsyncSession,
        project_id: int,
        service: str,
        units: int = 1,
        pipeline_run_id: Optional[int] = None,
        description: Optional[str] = None,
    ) -> float:
        """Record a cost event. Returns the cost in USD."""
        from app.models.pipeline_run import CostEvent

        unit_price = PRICING.get(service, 0)
        cost_usd = round(unit_price * units, 6)

        event = CostEvent(
            project_id=project_id,
            pipeline_run_id=pipeline_run_id,
            service=service,
            units=units,
            cost_usd=Decimal(str(cost_usd)),
            description=description,
        )
        session.add(event)

        # Update pipeline run total cost if applicable
        if pipeline_run_id:
            from app.models.pipeline_run import PipelineRun
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == pipeline_run_id)
            )
            run = result.scalar_one_or_none()
            if run:
                run.total_cost_usd = (run.total_cost_usd or Decimal("0")) + Decimal(str(cost_usd))

        return cost_usd

    async def check_budget(
        self,
        session: AsyncSession,
        project_id: int,
        estimated_cost: float,
    ) -> bool:
        """Check if a project has budget for the estimated cost. Returns True if OK."""
        from app.models.pipeline_run import PipelineRun, PipelineRunStatus

        # Find the active pipeline run with a budget limit
        result = await session.execute(
            select(PipelineRun).where(
                PipelineRun.project_id == project_id,
                PipelineRun.status == PipelineRunStatus.RUNNING,
                PipelineRun.budget_limit_usd.isnot(None),
            ).order_by(PipelineRun.created_at.desc()).limit(1)
        )
        run = result.scalar_one_or_none()
        if not run or not run.budget_limit_usd:
            return True  # No budget limit set

        current_cost = float(run.total_cost_usd or 0)
        return (current_cost + estimated_cost) <= float(run.budget_limit_usd)

    async def get_spending_breakdown(
        self,
        session: AsyncSession,
        project_id: int,
        pipeline_run_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get cost breakdown by service for a project or specific run."""
        from app.models.pipeline_run import CostEvent

        filters = [CostEvent.project_id == project_id]
        if pipeline_run_id:
            filters.append(CostEvent.pipeline_run_id == pipeline_run_id)

        result = await session.execute(
            select(
                CostEvent.service,
                func.sum(CostEvent.units).label("total_units"),
                func.sum(CostEvent.cost_usd).label("total_cost"),
                func.count(CostEvent.id).label("event_count"),
            )
            .where(*filters)
            .group_by(CostEvent.service)
            .order_by(func.sum(CostEvent.cost_usd).desc())
        )
        rows = result.fetchall()

        services = {}
        total = 0.0
        for r in rows:
            cost = float(r.total_cost or 0)
            services[r.service] = {
                "units": r.total_units or 0,
                "cost_usd": round(cost, 4),
                "events": r.event_count or 0,
            }
            total += cost

        return {
            "project_id": project_id,
            "pipeline_run_id": pipeline_run_id,
            "total_cost_usd": round(total, 4),
            "by_service": services,
        }

    async def record_cost_standalone(
        self,
        project_id: int,
        service: str,
        units: int = 1,
        pipeline_run_id: Optional[int] = None,
        description: Optional[str] = None,
    ) -> float:
        """Record cost using a new session (for use outside request context)."""
        async with async_session_maker() as session:
            cost = await self.record_cost(
                session, project_id, service, units,
                pipeline_run_id=pipeline_run_id,
                description=description,
            )
            await session.commit()
            return cost


# Singleton
cost_service = CostService()
