"""Account API — credits tracking, API keys, usage stats."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_session
from app.models.user import MCPUser
from app.models.integration import MCPIntegrationSetting
from app.models.gathering import GatheringRun
from app.models.usage import MCPUsageLog
from app.models.pipeline import ExtractedContact, DiscoveredCompany
from app.models.campaign import Campaign
from app.auth.dependencies import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])


@router.get("")
@router.get("/")
async def get_account(
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Account overview — credits, usage, API keys status."""
    if not user:
        return {"authenticated": False, "message": "Not logged in"}

    # Integrations
    integrations_result = await session.execute(
        select(MCPIntegrationSetting).where(MCPIntegrationSetting.user_id == user.id)
    )
    integrations = [
        {"name": i.integration_name, "connected": i.is_connected, "info": i.connection_info}
        for i in integrations_result.scalars().all()
    ]

    # Apollo credits used (sum from all gathering runs)
    apollo_credits = (await session.execute(
        select(func.sum(GatheringRun.credits_used)).where(
            GatheringRun.triggered_by.like(f"%user:{user.id}%")
        )
    )).scalar() or 0

    # Filter discovery credits — read actual credits_spent from usage log extra_data
    # Each suggest_apollo_filters call logs credits_spent in extra_data
    filter_logs = await session.execute(
        select(MCPUsageLog.extra_data).where(
            MCPUsageLog.user_id == user.id,
            MCPUsageLog.tool_name == "suggest_apollo_filters",
        )
    )
    filter_discovery_credits = 0
    filter_discovery_calls = 0
    for (extra,) in filter_logs.all():
        filter_discovery_calls += 1
        if isinstance(extra, dict):
            cs = extra.get("credits_spent", {})
            if isinstance(cs, dict):
                filter_discovery_credits += cs.get("total", 0)
            else:
                filter_discovery_credits += 6  # fallback estimate
        else:
            filter_discovery_credits += 6  # fallback estimate

    # People search credits (bulk_match calls)
    people_credits = (await session.execute(
        select(func.count(MCPUsageLog.id)).where(
            MCPUsageLog.user_id == user.id,
            MCPUsageLog.tool_name == "enrich_contacts",
        )
    )).scalar() or 0

    # Total tool calls
    total_tool_calls = (await session.execute(
        select(func.count(MCPUsageLog.id)).where(MCPUsageLog.user_id == user.id)
    )).scalar() or 0

    # Contacts and companies
    total_contacts = (await session.execute(
        select(func.count(ExtractedContact.id)).join(
            DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id, isouter=True
        )
    )).scalar() or 0

    total_companies = (await session.execute(
        select(func.count(DiscoveredCompany.id))
    )).scalar() or 0

    total_campaigns = (await session.execute(
        select(func.count(Campaign.id))
    )).scalar() or 0

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
        "integrations": integrations,
        "credits": {
            "apollo": {
                "search_pages": apollo_credits,
                "filter_discovery": filter_discovery_credits,
                "filter_discovery_calls": filter_discovery_calls,
                "people_enrichment": people_credits,
                "total": apollo_credits + filter_discovery_credits + people_credits,
                "note": "Search: 1 credit/page (100 companies). Enrich: 1 credit/company. People: 1 credit/email.",
            },
            "openai": {
                "tool_calls": total_tool_calls,
                "note": "GPT-4o-mini: ~$0.003 per company analyzed",
            },
            "mcp": {
                "tool_calls": total_tool_calls,
                "note": "MCP platform usage",
            },
        },
        "stats": {
            "total_contacts": total_contacts,
            "total_companies": total_companies,
            "total_campaigns": total_campaigns,
            "total_tool_calls": total_tool_calls,
        },
    }


@router.get("/usage")
async def get_usage(
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Detailed usage breakdown by tool."""
    if not user:
        return {"authenticated": False}

    # Usage by tool
    result = await session.execute(
        select(MCPUsageLog.tool_name, func.count(MCPUsageLog.id))
        .where(MCPUsageLog.user_id == user.id)
        .group_by(MCPUsageLog.tool_name)
        .order_by(func.count(MCPUsageLog.id).desc())
    )
    by_tool = {row[0]: row[1] for row in result.all()}

    # Recent activity
    recent = await session.execute(
        select(MCPUsageLog)
        .where(MCPUsageLog.user_id == user.id)
        .order_by(MCPUsageLog.created_at.desc())
        .limit(20)
    )
    recent_logs = [
        {"tool": log.tool_name, "action": log.action, "at": str(log.created_at)}
        for log in recent.scalars().all()
    ]

    return {
        "by_tool": by_tool,
        "recent": recent_logs,
    }
