"""Service for auto-calculating outreach statistics from integrations."""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case

from app.models import Contact, Project, Campaign, Meeting, OutreachStats

logger = logging.getLogger(__name__)


class OutreachStatsService:
    """
    Auto-calculates outreach statistics from:
    - SmartLead campaigns (email) - from campaigns table
    - GetSales (LinkedIn) - from contacts table
    - Calendly (meetings) - from meetings table

    Manual channels (Telegram, WhatsApp) are not auto-calculated.
    """

    async def sync_project_stats(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """
        Sync all stats for a project for a given period.
        """
        results = {
            "synced_channels": [],
            "errors": [],
            "stats": []
        }

        # Get project
        project = await db.get(Project, project_id)
        if not project:
            results["errors"].append(f"Project {project_id} not found")
            return results

        # Sync Email from SmartLead campaigns
        try:
            email_stats = await self._sync_email_from_campaigns(db, project_id, company_id, period_start, period_end)
            results["stats"].extend(email_stats)
            results["synced_channels"].append("email")
        except Exception as e:
            logger.error(f"Error syncing email stats: {e}", exc_info=True)
            results["errors"].append(f"Email sync error: {str(e)}")

        # Sync LinkedIn from contacts (GetSales data)
        try:
            linkedin_stats = await self._sync_linkedin_from_contacts(db, project_id, company_id, period_start, period_end)
            results["stats"].extend(linkedin_stats)
            results["synced_channels"].append("linkedin")
        except Exception as e:
            logger.error(f"Error syncing LinkedIn stats: {e}", exc_info=True)
            results["errors"].append(f"LinkedIn sync error: {str(e)}")

        # Sync meetings from Calendly
        try:
            await self._sync_meeting_counts(db, project_id, period_start, period_end)
            results["synced_channels"].append("meetings")
        except Exception as e:
            logger.error(f"Error syncing meeting stats: {e}", exc_info=True)
            results["errors"].append(f"Meetings sync error: {str(e)}")

        return results

    async def _sync_email_from_campaigns(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """
        Sync email stats from campaigns table.
        Uses leads_count for sent, sl_reply_count for replies.
        Extracts segment from campaign name.
        """
        stats_list = []

        # Get all email campaigns for this project
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id == project_id,
                    Campaign.channel == "email",
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        # Group by segment (extracted from campaign name)
        segment_data: Dict[str, Dict] = {}

        for campaign in campaigns:
            segment = self._extract_segment_from_campaign(campaign.name)

            if segment not in segment_data:
                segment_data[segment] = {
                    "contacts_sent": 0,
                    "replies_count": 0,
                    "positive_replies": 0,
                    "campaigns": [],
                }

            # Add campaign stats
            segment_data[segment]["contacts_sent"] += campaign.leads_count or 0
            segment_data[segment]["replies_count"] += campaign.sl_reply_count or 0
            segment_data[segment]["campaigns"].append(campaign.name)

        # Count positive replies from contacts for each segment
        for segment in segment_data:
            # Try to match contacts by campaign names
            campaign_names = segment_data[segment]["campaigns"]

            # Simple approach: count positive contacts where source contains smartlead
            # and segment matches (if available) or just count all positive for the project
            positive_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.source.ilike("%smartlead%"),
                        Contact.status.in_(["interested", "meeting_request", "positive", "qualified"]),
                    )
                )
            )
            # Distribute positive replies proportionally
            total_replies = sum(s["replies_count"] for s in segment_data.values())
            if total_replies > 0:
                proportion = segment_data[segment]["replies_count"] / total_replies
                segment_data[segment]["positive_replies"] = int((positive_count or 0) * proportion)

        # Create/update stats for each segment
        for segment, data in segment_data.items():
            if data["contacts_sent"] == 0:
                continue  # Skip empty segments

            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel="email",
                segment=segment,
                data={
                    "contacts_sent": data["contacts_sent"],
                    "contacts_accepted": data["contacts_sent"],  # N/A for email
                    "replies_count": data["replies_count"],
                    "positive_replies": data["positive_replies"],
                },
                data_source="smartlead"
            )
            stats_list.append(stat.to_dict())

        return stats_list

    async def _sync_linkedin_from_contacts(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """
        Sync LinkedIn stats from contacts table.
        Looks for contacts with source containing 'getsales'.
        """
        stats_list = []

        # Get LinkedIn campaigns to extract segments
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id == project_id,
                    Campaign.channel == "linkedin",
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        # Get segments from campaigns or use "General"
        segments = set()
        for campaign in campaigns:
            segment = self._extract_segment_from_campaign(campaign.name)
            segments.add(segment)

        if not segments:
            segments.add("General")

        # For each segment, count contacts
        for segment in segments:
            # Count total LinkedIn contacts
            total_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.source.ilike("%getsales%"),
                        Contact.is_active == True,
                    )
                )
            )

            # Count replied
            replied_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.source.ilike("%getsales%"),
                        Contact.last_reply_at.isnot(None),
                    )
                )
            )

            # Count positive
            positive_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.source.ilike("%getsales%"),
                        Contact.status.in_(["interested", "meeting_request", "positive", "qualified"]),
                    )
                )
            )

            # Distribute across segments proportionally (simple approach for now)
            num_segments = len(segments)

            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel="linkedin",
                segment=segment,
                data={
                    "contacts_sent": (total_count or 0) // num_segments,
                    "contacts_accepted": (total_count or 0) // num_segments,
                    "replies_count": (replied_count or 0) // num_segments,
                    "positive_replies": (positive_count or 0) // num_segments,
                },
                data_source="getsales"
            )
            stats_list.append(stat.to_dict())

        return stats_list

    async def _sync_meeting_counts(
        self,
        db: AsyncSession,
        project_id: int,
        period_start: date,
        period_end: date,
    ):
        """Update meeting counts in existing stats from meetings table."""
        period_start_dt = datetime.combine(period_start, datetime.min.time())
        period_end_dt = datetime.combine(period_end, datetime.max.time())

        # Get meeting counts by channel/segment
        meeting_query = select(
            Meeting.channel,
            Meeting.segment,
            func.count(Meeting.id).label("scheduled"),
            func.sum(case((Meeting.status == "completed", 1), else_=0)).label("completed")
        ).where(
            and_(
                Meeting.project_id == project_id,
                Meeting.scheduled_at >= period_start_dt,
                Meeting.scheduled_at <= period_end_dt,
            )
        ).group_by(Meeting.channel, Meeting.segment)

        result = await db.execute(meeting_query)
        rows = result.all()

        for row in rows:
            if not row.channel:
                continue

            # Update corresponding outreach_stats record
            stat_result = await db.execute(
                select(OutreachStats).where(
                    and_(
                        OutreachStats.project_id == project_id,
                        OutreachStats.channel == row.channel,
                        OutreachStats.segment == (row.segment or "General"),
                        OutreachStats.period_start == period_start,
                        OutreachStats.period_end == period_end,
                    )
                )
            )
            stat = stat_result.scalar_one_or_none()

            if stat:
                stat.meetings_scheduled = row.scheduled or 0
                stat.meetings_completed = row.completed or 0
                stat.calculate_rates()

        await db.commit()

    async def _upsert_stat(
        self,
        db: AsyncSession,
        company_id: int,
        project_id: int,
        period_start: date,
        period_end: date,
        channel: str,
        segment: str,
        data: Dict,
        data_source: str,
    ) -> OutreachStats:
        """Create or update an outreach stats record."""
        # Try to find existing
        result = await db.execute(
            select(OutreachStats).where(
                and_(
                    OutreachStats.project_id == project_id,
                    OutreachStats.channel == channel,
                    OutreachStats.segment == segment,
                    OutreachStats.period_start == period_start,
                    OutreachStats.period_end == period_end,
                )
            )
        )
        stat = result.scalar_one_or_none()

        if stat:
            # Update existing (but don't overwrite manual entries)
            if not stat.is_manual:
                stat.contacts_sent = data.get("contacts_sent", stat.contacts_sent)
                stat.contacts_accepted = data.get("contacts_accepted", stat.contacts_accepted)
                stat.replies_count = data.get("replies_count", stat.replies_count)
                stat.positive_replies = data.get("positive_replies", stat.positive_replies)
                stat.meetings_scheduled = data.get("meetings_scheduled", stat.meetings_scheduled)
                stat.data_source = data_source
                stat.last_synced_at = datetime.utcnow()
                stat.calculate_rates()
        else:
            # Create new
            stat = OutreachStats(
                company_id=company_id,
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                channel=channel,
                segment=segment,
                contacts_sent=data.get("contacts_sent", 0),
                contacts_accepted=data.get("contacts_accepted", 0),
                replies_count=data.get("replies_count", 0),
                positive_replies=data.get("positive_replies", 0),
                meetings_scheduled=data.get("meetings_scheduled", 0),
                is_manual=0,
                data_source=data_source,
                last_synced_at=datetime.utcnow(),
            )
            stat.calculate_rates()
            db.add(stat)

        await db.commit()
        await db.refresh(stat)
        return stat

    def _extract_segment_from_campaign(self, campaign_name: str) -> str:
        """
        Extract segment name from campaign name.

        Examples:
        - "Mifort Marketing iGaming Casino" -> "iGaming Casino"
        - "Mifort. iGaming conf Marketing" -> "iGaming conf Marketing"
        - "Mifort Partners BizDevs" -> "Partners BizDevs"
        - "Mifort FinTech Clay 0303" -> "FinTech"
        """
        if not campaign_name:
            return "General"

        # Remove common prefixes
        name = campaign_name.strip()

        # Remove "Mifort" prefix and variations
        name = re.sub(r'^Mifort\.?\s*', '', name, flags=re.IGNORECASE)

        # Remove date patterns like "0303", "0603"
        name = re.sub(r'\s+\d{4}$', '', name)

        # Remove "Clay" suffix
        name = re.sub(r'\s+Clay\s*\d*$', '', name, flags=re.IGNORECASE)

        # Remove trailing numbers
        name = re.sub(r'\s+\d+$', '', name)

        # Clean up
        name = name.strip()

        if not name:
            return "General"

        # Limit length
        if len(name) > 50:
            name = name[:50]

        return name


# Singleton
outreach_stats_service = OutreachStatsService()
