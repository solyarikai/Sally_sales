"""Service for auto-calculating outreach statistics from integrations."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, literal_column

from app.models import Contact, Project, Campaign, Meeting, OutreachStats

logger = logging.getLogger(__name__)


# Map source values to channels
SOURCE_TO_CHANNEL = {
    "getsales": "linkedin",
    "smartlead": "email",
    "getsales+smartlead": "email",  # Primary was email
    "smartlead+getsales": "linkedin",  # Primary was LinkedIn
}


class OutreachStatsService:
    """
    Auto-calculates outreach statistics from:
    - SmartLead (email campaigns)
    - GetSales (LinkedIn) - via contacts table
    - Calendly (meetings) - via meetings table

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
        Creates stats based on actual contact data grouped by source/segment.
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

        try:
            stats = await self._sync_from_contacts(db, project_id, company_id, period_start, period_end)
            results["stats"].extend(stats)
            results["synced_channels"].extend(["email", "linkedin"])
        except Exception as e:
            logger.error(f"Error syncing contact stats: {e}", exc_info=True)
            results["errors"].append(f"Contact sync error: {str(e)}")

        # Sync meetings from Calendly
        try:
            await self._sync_meeting_counts(db, project_id, period_start, period_end)
            results["synced_channels"].append("meetings")
        except Exception as e:
            logger.error(f"Error syncing meeting stats: {e}", exc_info=True)
            results["errors"].append(f"Meetings sync error: {str(e)}")

        return results

    async def _sync_from_contacts(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """
        Sync stats directly from contacts table.
        Groups by source (mapped to channel) and segment.
        """
        stats_list = []
        period_start_dt = datetime.combine(period_start, datetime.min.time())
        period_end_dt = datetime.combine(period_end, datetime.max.time())

        # Get aggregated contact stats by source
        query = select(
            Contact.source,
            Contact.segment,
            func.count(Contact.id).label("total_contacts"),
            func.sum(case((Contact.last_reply_at.isnot(None), 1), else_=0)).label("replied"),
            func.sum(case(
                (Contact.status.in_(["interested", "meeting_request", "positive", "qualified"]), 1),
                else_=0
            )).label("positive"),
            func.sum(case(
                (Contact.status.in_(["meeting_scheduled", "meeting_held"]), 1),
                else_=0
            )).label("meetings"),
        ).where(
            and_(
                Contact.project_id == project_id,
                Contact.created_at >= period_start_dt,
                Contact.created_at <= period_end_dt,
                Contact.is_active == True,
            )
        ).group_by(Contact.source, Contact.segment)

        result = await db.execute(query)
        rows = result.all()

        # Process each source/segment combination
        for row in rows:
            source = row.source or "unknown"
            segment = row.segment or "General"  # Default segment if empty

            # Determine channel from source
            channel = self._get_channel_from_source(source)
            if not channel:
                continue  # Skip unknown sources

            # Get or create stat
            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel=channel,
                segment=segment,
                data={
                    "contacts_sent": row.total_contacts or 0,
                    "contacts_accepted": row.total_contacts or 0,  # For LinkedIn, sent ≈ accepted for now
                    "replies_count": row.replied or 0,
                    "positive_replies": row.positive or 0,
                    "meetings_scheduled": row.meetings or 0,
                },
                data_source="getsales" if channel == "linkedin" else "smartlead"
            )
            stats_list.append(stat.to_dict())

        # If no data found, create summary stats from campaign data
        if not stats_list:
            stats_list = await self._sync_from_campaigns(db, project_id, company_id, period_start, period_end)

        return stats_list

    async def _sync_from_campaigns(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """Fallback: sync from campaigns table if contacts don't have data."""
        stats_list = []

        # Get campaigns for this project
        campaigns_result = await db.execute(
            select(Campaign).where(Campaign.project_id == project_id)
        )
        campaigns = campaigns_result.scalars().all()

        for campaign in campaigns:
            channel = "email" if campaign.platform == "email" else "linkedin"
            segment = self._extract_segment_from_campaign(campaign.name)

            # Check if stat already exists
            existing = await db.execute(
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
            if existing.scalar_one_or_none():
                continue

            # Create placeholder stat
            stat = OutreachStats(
                company_id=company_id,
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                channel=channel,
                segment=segment,
                contacts_sent=0,
                is_manual=0,
                data_source="campaign",
                last_synced_at=datetime.utcnow(),
            )
            stat.calculate_rates()
            db.add(stat)
            await db.commit()
            await db.refresh(stat)
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

    def _get_channel_from_source(self, source: str) -> Optional[str]:
        """Map contact source to channel name."""
        if not source:
            return None

        source_lower = source.lower()

        # Direct mappings
        if source_lower in SOURCE_TO_CHANNEL:
            return SOURCE_TO_CHANNEL[source_lower]

        # Pattern matching
        if "getsales" in source_lower:
            return "linkedin"
        if "smartlead" in source_lower:
            return "email"

        return None

    def _extract_segment_from_campaign(self, campaign_name: str) -> str:
        """Extract segment name from campaign name.

        Examples:
        - "Mifort - FinTech - Wave 1" -> "FinTech"
        - "iGaming Marketing Campaign" -> "iGaming Marketing"
        - "General" -> "General"
        """
        if not campaign_name:
            return "General"

        parts = campaign_name.split(" - ")
        if len(parts) >= 2:
            # Return second part (usually the segment)
            return parts[1].strip()

        # Try to extract without delimiter
        return campaign_name.strip()[:50]  # Limit length


# Singleton
outreach_stats_service = OutreachStatsService()
