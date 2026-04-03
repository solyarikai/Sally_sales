"""Project Report Service — AI functions for plan parsing, progress tracking, and report generation.

Functions:
- parse_plan_into_items: Extract actionable items from a plan using GPT
- analyze_report_against_plan: Compare report with plan items, update statuses
- generate_client_report: Generate professional client-facing report
- get_progress_status: Get progress statistics for a project
"""
import logging
import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.project_report import (
    ProjectReport, ProjectPlan, ProjectProgressItem,
    ProjectReportSubscription, ProgressStatus
)
from app.models.contact import Project

logger = logging.getLogger(__name__)


async def _call_openai(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> Optional[str]:
    """Call OpenAI API with given messages."""
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set")
        return None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            logger.error(f"OpenAI error: {data}")
            return None
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        return None


async def parse_plan_into_items(plan_content: str, project_name: str = None) -> List[Dict[str, Any]]:
    """Parse a plan text into actionable items using GPT.

    Args:
        plan_content: Raw plan text (can be multi-line, markdown, etc.)
        project_name: Optional project name for context

    Returns:
        List of parsed items: [{item, due_date, priority, category}]
    """
    system_prompt = """You are a project management assistant. Extract actionable items from the given plan.

For each item, extract:
- item: The task description (clear, actionable)
- due_date: Date in YYYY-MM-DD format if mentioned, null otherwise
- priority: "high", "medium", or "low" based on urgency/importance
- category: Category like "development", "design", "testing", "documentation", "deployment", "meeting", "research"

Return ONLY valid JSON array. No explanations.

Example output:
[
  {"item": "Implement user authentication", "due_date": "2026-03-20", "priority": "high", "category": "development"},
  {"item": "Design landing page mockups", "due_date": null, "priority": "medium", "category": "design"}
]"""

    user_prompt = f"Parse this plan into actionable items:\n\n{plan_content}"
    if project_name:
        user_prompt = f"Project: {project_name}\n\n{user_prompt}"

    result = await _call_openai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    if not result:
        return []

    try:
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        items = json.loads(result)
        if not isinstance(items, list):
            return []
        return items
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse plan items JSON: {e}")
        return []


async def analyze_report_against_plan(
    session: AsyncSession,
    project_id: int,
    report_text: str,
    report_id: int = None,
) -> Dict[str, Any]:
    """Analyze a report against the active plan items.

    Compares report content with pending/in-progress items.
    Updates item statuses and links completed items to the report.

    Args:
        session: Database session
        project_id: Project ID
        report_text: Report text to analyze
        report_id: Optional report ID to link completed items

    Returns:
        {matches: [{item_id, item_text, status_change, confidence}],
         unplanned_work: [str],
         summary: str}
    """
    # Get active plan items
    items_result = await session.execute(
        select(ProjectProgressItem).where(
            ProjectProgressItem.project_id == project_id,
            ProjectProgressItem.status.in_(["pending", "in_progress"]),
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "matches": [],
            "unplanned_work": [],
            "summary": "No active plan items to track against.",
        }

    # Build item list for AI
    items_text = "\n".join([
        f"- ID {item.id}: {item.item_text} (status: {item.status})"
        for item in items
    ])

    system_prompt = """You analyze project reports against plan items.

Given a report and list of plan items, identify:
1. Which items the report mentions progress on (even partial)
2. Work mentioned that's not in the plan (unplanned)

For each match, provide:
- item_id: The ID from the plan
- status_change: "in_progress" if started, "completed" if done
- confidence: 0.0-1.0 how confident you are in this match

Return ONLY valid JSON:
{
  "matches": [{"item_id": 123, "status_change": "completed", "confidence": 0.9}],
  "unplanned_work": ["Fixed critical bug in payment processing"],
  "summary": "Brief summary of what was accomplished"
}"""

    user_prompt = f"""Plan items:
{items_text}

Report:
{report_text}

Analyze which items the report addresses."""

    result = await _call_openai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    if not result:
        return {
            "matches": [],
            "unplanned_work": [],
            "summary": "Failed to analyze report.",
        }

    try:
        # Extract JSON
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        analysis = json.loads(result)
    except json.JSONDecodeError:
        return {
            "matches": [],
            "unplanned_work": [],
            "summary": "Failed to parse analysis.",
        }

    # Update item statuses based on matches
    matches = analysis.get("matches", [])
    updated_matches = []

    for match in matches:
        item_id = match.get("item_id")
        status_change = match.get("status_change")
        confidence = match.get("confidence", 0.5)

        if not item_id or not status_change:
            continue

        # Find the item
        item = next((i for i in items if i.id == item_id), None)
        if not item:
            continue

        # Update status
        old_status = item.status
        item.status = status_change
        item.ai_match_confidence = confidence
        item.updated_at = datetime.utcnow()

        if status_change == "completed":
            item.completed_at = datetime.utcnow()
            if report_id:
                item.completed_by_report_id = report_id

        updated_matches.append({
            "item_id": item_id,
            "item_text": item.item_text,
            "old_status": old_status,
            "new_status": status_change,
            "confidence": confidence,
        })

    await session.flush()

    return {
        "matches": updated_matches,
        "unplanned_work": analysis.get("unplanned_work", []),
        "summary": analysis.get("summary", ""),
    }


async def generate_client_report(
    session: AsyncSession,
    project_id: int,
    start_date: date,
    end_date: date,
    include_plan_status: bool = True,
) -> Dict[str, Any]:
    """Generate a professional client-facing report for a date range.

    Args:
        session: Database session
        project_id: Project ID
        start_date: Start date of report period
        end_date: End date of report period
        include_plan_status: Whether to include plan progress status

    Returns:
        {report_text: str, period: str, reports_count: int, items_completed: int}
    """
    # Get project
    project_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = project_result.scalar_one_or_none()
    if not project:
        return {"error": "Project not found"}

    # Get reports in date range
    reports_result = await session.execute(
        select(ProjectReport).where(
            ProjectReport.project_id == project_id,
            ProjectReport.report_date >= start_date,
            ProjectReport.report_date <= end_date,
        ).order_by(ProjectReport.report_date.asc())
    )
    reports = reports_result.scalars().all()

    # Build reports summary
    reports_text = ""
    for report in reports:
        reports_text += f"\n--- {report.report_date.strftime('%d.%m.%Y')} ---\n{report.report_text}\n"

    # Get plan status if requested
    plan_status_text = ""
    items_completed = 0
    if include_plan_status:
        status = await get_progress_status(session, project_id)
        items_completed = status.get("completed", 0)
        plan_status_text = f"""
Plan Progress:
- Total items: {status.get('total', 0)}
- Completed: {status.get('completed', 0)}
- In Progress: {status.get('in_progress', 0)}
- Pending: {status.get('pending', 0)}
- Blocked: {status.get('blocked', 0)}
- Completion: {status.get('completion_percent', 0):.0f}%
"""

    if not reports and not plan_status_text:
        return {
            "report_text": f"No reports found for {project.name} in the specified period.",
            "period": f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
            "reports_count": 0,
            "items_completed": 0,
        }

    # Generate professional report using GPT-4o
    system_prompt = """You are a professional project manager writing a client report.

Create a clear, professional report that:
1. Summarizes key accomplishments
2. Highlights completed milestones
3. Notes any blockers or risks
4. Uses professional but friendly tone
5. Is structured with clear sections

Write in the language of the original reports (likely Russian).
Keep it concise but comprehensive."""

    user_prompt = f"""Generate a client report for project "{project.name}".

Period: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}

Daily Reports:
{reports_text if reports_text else "No daily reports available."}

{plan_status_text}

Create a professional summary report for the client."""

    report_text = await _call_openai(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model="gpt-4o",
        max_tokens=3000,
    )

    if not report_text:
        # Fallback to simple compilation
        report_text = f"""# Progress Report: {project.name}
Period: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}

## Daily Updates
{reports_text if reports_text else "No updates available."}

{plan_status_text}
"""

    return {
        "report_text": report_text,
        "period": f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
        "reports_count": len(reports),
        "items_completed": items_completed,
    }


async def get_progress_status(session: AsyncSession, project_id: int) -> Dict[str, Any]:
    """Get progress statistics for a project.

    Args:
        session: Database session
        project_id: Project ID

    Returns:
        {total, completed, in_progress, pending, blocked, completion_percent, by_category}
    """
    # Get all items for the project (from active plans)
    items_result = await session.execute(
        select(ProjectProgressItem).join(ProjectPlan).where(
            ProjectProgressItem.project_id == project_id,
            ProjectPlan.is_active == True,
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
            "blocked": 0,
            "completion_percent": 0,
            "by_category": {},
        }

    # Count by status
    status_counts = {
        "completed": 0,
        "in_progress": 0,
        "pending": 0,
        "blocked": 0,
    }
    by_category = {}

    for item in items:
        status = item.status or "pending"
        status_counts[status] = status_counts.get(status, 0) + 1

        category = item.category or "uncategorized"
        if category not in by_category:
            by_category[category] = {"total": 0, "completed": 0}
        by_category[category]["total"] += 1
        if status == "completed":
            by_category[category]["completed"] += 1

    total = len(items)
    completed = status_counts["completed"]
    completion_percent = (completed / total * 100) if total > 0 else 0

    return {
        "total": total,
        "completed": completed,
        "in_progress": status_counts["in_progress"],
        "pending": status_counts["pending"],
        "blocked": status_counts["blocked"],
        "completion_percent": completion_percent,
        "by_category": by_category,
    }


async def generate_report_summary(report_text: str) -> Optional[str]:
    """Generate a brief AI summary of a report.

    Args:
        report_text: The full report text

    Returns:
        Brief summary (1-2 sentences)
    """
    system_prompt = """Summarize the project update in 1-2 sentences.
Focus on key accomplishments and any blockers.
Respond in the same language as the input."""

    result = await _call_openai(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": report_text},
        ],
        max_tokens=150,
    )

    return result


def format_progress_for_telegram(status: Dict[str, Any]) -> str:
    """Format progress status dict for Telegram display.

    Args:
        status: Progress status dict from get_progress_status()

    Returns:
        Formatted string with emoji indicators
    """
    if status["total"] == 0:
        return "📋 Нет активных пунктов плана."

    # Build progress bar
    pct = status['completion_percent']
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)

    lines = [
        f"📊 *Прогресс: {pct:.0f}%*",
        f"`[{bar}]`",
        "",
        f"✅ Выполнено: {status['completed']}",
        f"🔄 В процессе: {status['in_progress']}",
        f"⏳ Ожидает: {status['pending']}",
    ]

    if status["blocked"] > 0:
        lines.append(f"🚫 Заблокировано: {status['blocked']}")

    # Add category breakdown if multiple categories
    if len(status.get("by_category", {})) > 1:
        lines.append("")
        lines.append("*По категориям:*")
        for cat, counts in status["by_category"].items():
            cat_pct = (counts["completed"] / counts["total"] * 100) if counts["total"] > 0 else 0
            lines.append(f"  • {cat}: {counts['completed']}/{counts['total']} ({cat_pct:.0f}%)")

    return "\n".join(lines)


async def format_progress_for_telegram_async(session: AsyncSession, project_id: int) -> str:
    """Async version - fetches status and formats for Telegram.

    Args:
        session: Database session
        project_id: Project ID

    Returns:
        Formatted string with emoji indicators
    """
    status = await get_progress_status(session, project_id)
    return format_progress_for_telegram(status)


async def get_lead_projects(session: AsyncSession, chat_id: str) -> List[Dict[str, Any]]:
    """Get list of projects where user is a lead.

    Args:
        session: Database session
        chat_id: Telegram chat ID

    Returns:
        List of {project_id, project_name, last_reported_at}
    """
    result = await session.execute(
        select(ProjectReportSubscription, Project.name).join(
            Project, ProjectReportSubscription.project_id == Project.id
        ).where(
            ProjectReportSubscription.chat_id == chat_id,
            ProjectReportSubscription.role == "lead",
            ProjectReportSubscription.is_active == True,
            Project.deleted_at.is_(None),
        )
    )

    projects = []
    for sub, name in result.all():
        projects.append({
            "project_id": sub.project_id,
            "project_name": name,
            "last_reported_at": sub.last_reported_at,
        })

    return projects


async def get_report_history(
    session: AsyncSession,
    project_id: int,
    chat_id: str = None,
    days: int = 7,
) -> List[Dict[str, Any]]:
    """Get report history for a project.

    Args:
        session: Database session
        project_id: Project ID
        chat_id: Optional filter by lead
        days: Number of days to look back

    Returns:
        List of report summaries
    """
    since = date.today() - timedelta(days=days)

    query = select(ProjectReport).where(
        ProjectReport.project_id == project_id,
        ProjectReport.report_date >= since,
    )

    if chat_id:
        query = query.where(ProjectReport.lead_chat_id == chat_id)

    query = query.order_by(ProjectReport.report_date.desc())

    result = await session.execute(query)
    reports = result.scalars().all()

    return [
        {
            "id": r.id,
            "date": r.report_date.isoformat(),
            "lead_name": r.lead_first_name or r.lead_username or "Unknown",
            "summary": r.ai_summary or (r.report_text[:100] + "..." if len(r.report_text) > 100 else r.report_text),
            "forwarded": r.forwarded_to_boss,
        }
        for r in reports
    ]
