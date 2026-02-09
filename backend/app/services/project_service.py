"""
Project Service — Auto-create projects for agency names based on campaign matching.
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, String

from app.models.contact import Contact, Project

logger = logging.getLogger(__name__)

# 14 agency names for auto-project creation
AGENCY_NAMES = [
    "easystaff global",  # Process before "easystaff" — both can overlap
    "inxy",
    "squarefi",
    "easystaff",
    "tfp",
    "2ndcapital",
    "paybis",
    "palark",
    "gwc",
    "deliryo",
    "rizult",
    "maincard",
    "crowdcontrol",
    "mifort",
]


async def get_all_campaign_names(session: AsyncSession) -> List[Dict[str, Any]]:
    """Fetch all unique campaign names from contacts.campaigns JSON."""
    result = await session.execute(
        select(Contact.campaigns).where(
            and_(
                Contact.campaigns.isnot(None),
                Contact.deleted_at.is_(None)
            )
        )
    )

    campaigns = []
    seen = set()
    for row in result.scalars():
        if not row:
            continue
        for camp in row:
            name = camp.get("name")
            source = camp.get("source")
            if name and (name, source) not in seen:
                seen.add((name, source))
                campaigns.append({"name": name, "source": source})

    return campaigns


async def auto_create_projects(
    session: AsyncSession,
    company_id: int = 1,
) -> Dict[str, Any]:
    """
    Auto-create projects for the 14 agency names.

    For each agency name:
    1. Find campaigns containing that name (case-insensitive)
    2. Create Project with campaign_filters = matching campaign names
    3. Skip if project with same name already exists
    """
    all_campaigns = await get_all_campaign_names(session)

    created = []
    skipped = []
    no_campaigns = []

    for agency in AGENCY_NAMES:
        # Check if project already exists
        existing = await session.execute(
            select(Project.id).where(
                and_(
                    Project.company_id == company_id,
                    Project.name == agency,
                    Project.deleted_at.is_(None),
                )
            ).limit(1)
        )
        if existing.scalar():
            skipped.append(agency)
            continue

        # Find matching campaigns (case-insensitive)
        matching = [
            c["name"]
            for c in all_campaigns
            if agency.lower() in c["name"].lower()
        ]

        if not matching:
            no_campaigns.append(agency)
            continue

        project = Project(
            company_id=company_id,
            name=agency,
            description=f"Auto-created project for {agency} campaigns",
            campaign_filters=matching,
        )
        session.add(project)
        created.append({"name": agency, "campaigns": matching})

    await session.flush()

    return {
        "created": created,
        "skipped": skipped,
        "no_campaigns": no_campaigns,
    }
