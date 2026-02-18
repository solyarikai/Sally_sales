"""
Chat Notification Service — inserts system messages into project chat
when pipeline events, budget warnings, or errors occur.

Provides proactive intelligence: the chat shows what happened without the user asking.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.db import async_session_maker
from app.models.chat import ProjectChatMessage

logger = logging.getLogger(__name__)


class ChatNotificationService:
    """Insert system messages into project chat for background events."""

    async def on_pipeline_phase_complete(
        self,
        project_id: int,
        phase: str,
        stats: Optional[Dict[str, Any]] = None,
    ):
        """Notify chat that a pipeline phase completed."""
        stats_str = ""
        if stats:
            parts = []
            if "targets_found" in stats:
                parts.append(f"{stats['targets_found']} targets")
            if "contacts_found" in stats:
                parts.append(f"{stats['contacts_found']} contacts")
            if "people_found" in stats:
                parts.append(f"{stats['people_found']} people enriched")
            if "credits_used" in stats:
                parts.append(f"{stats['credits_used']} credits")
            if "leads_pushed" in stats:
                parts.append(f"{stats['leads_pushed']} leads pushed")
            if parts:
                stats_str = f" — {', '.join(parts)}"

        phase_labels = {
            "search": "Search",
            "extraction": "Contact Extraction",
            "enrichment": "Apollo Enrichment",
            "verification": "Email Verification",
            "crm_promote": "CRM Promotion",
            "smartlead_push": "SmartLead Push",
            "SEARCH": "Search",
            "EXTRACTION": "Contact Extraction",
            "ENRICHMENT": "Apollo Enrichment",
            "VERIFICATION": "Email Verification",
            "CRM_PROMOTE": "CRM Promotion",
            "SMARTLEAD_PUSH": "SmartLead Push",
        }
        label = phase_labels.get(phase, phase)

        content = f"{label} phase completed{stats_str}."
        await self._insert_system_message(
            project_id, content,
            action_type="phase_completed",
            action_data={"phase": phase, "stats": stats},
            suggestions=["pipeline status", "show stats"],
        )

    async def on_pipeline_complete(
        self,
        project_id: int,
        total_cost_usd: float = 0,
    ):
        """Notify chat that the full pipeline completed."""
        cost_str = f" Total cost: ${total_cost_usd:.2f}" if total_cost_usd > 0 else ""
        content = f"Pipeline completed successfully.{cost_str}"
        await self._insert_system_message(
            project_id, content,
            action_type="pipeline_completed",
            suggestions=["show stats", "show funnel", "push to smartlead"],
        )

    async def on_budget_warning(
        self,
        project_id: int,
        spent: float,
        limit: float,
    ):
        """Notify chat of budget threshold approaching."""
        pct = round(100 * spent / max(limit, 0.01), 1)
        content = f"Budget warning: ${spent:.2f} spent of ${limit:.2f} limit ({pct}% used)."
        await self._insert_system_message(
            project_id, content,
            action_type="budget_warning",
            action_data={"spent": spent, "limit": limit, "percent": pct},
            suggestions=["show cost breakdown", "stop"],
        )

    async def on_error(
        self,
        project_id: int,
        context: str,
        error_message: str,
        suggestion: Optional[str] = None,
    ):
        """Notify chat of an error."""
        content = f"Error in {context}: {error_message[:300]}"
        suggestions = [suggestion] if suggestion else ["pipeline status", "show stats"]
        await self._insert_system_message(
            project_id, content,
            action_type="error",
            action_data={"context": context, "error": error_message[:500]},
            suggestions=suggestions,
        )

    async def generate_daily_digest(self, project_id: int) -> str:
        """Generate a summary of what happened today."""
        from sqlalchemy import select, func, text as sql_text

        async with async_session_maker() as session:
            # Count today's events
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # New targets today
            result = await session.execute(sql_text("""
                SELECT
                    COUNT(*) FILTER (WHERE dc.created_at >= :today) as new_targets,
                    COUNT(*) FILTER (WHERE dc.apollo_enriched_at >= :today) as enriched_today,
                    COUNT(*) as total_targets
                FROM discovered_companies dc
                WHERE dc.project_id = :pid AND dc.is_target = true
            """), {"pid": project_id, "today": today_start})
            row = result.fetchone()

            parts = [f"**Daily Digest** (Project {project_id})"]
            if row:
                parts.append(f"- New targets today: **{row.new_targets}** (total: {row.total_targets})")
                if row.enriched_today > 0:
                    parts.append(f"- Enriched today: **{row.enriched_today}**")

            # Cost today
            result = await session.execute(sql_text("""
                SELECT COALESCE(SUM(cost_usd), 0) as today_cost
                FROM cost_events WHERE project_id = :pid AND created_at >= :today
            """), {"pid": project_id, "today": today_start})
            cost_row = result.fetchone()
            if cost_row and float(cost_row.today_cost) > 0:
                parts.append(f"- Today's spend: **${float(cost_row.today_cost):.2f}**")

            content = "\n".join(parts)

            await self._insert_system_message(
                project_id, content,
                action_type="daily_digest",
                suggestions=["show stats", "show funnel"],
            )

            return content

    async def _insert_system_message(
        self,
        project_id: int,
        content: str,
        action_type: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list] = None,
    ):
        """Insert a system message into the chat."""
        try:
            async with async_session_maker() as session:
                msg = ProjectChatMessage(
                    project_id=project_id,
                    role="system",
                    content=content,
                    action_type=action_type,
                    action_data=action_data,
                    suggestions=suggestions,
                )
                session.add(msg)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to insert system chat message: {e}")


# Singleton
chat_notification_service = ChatNotificationService()
