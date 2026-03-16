"""Service for auto-calculating outreach statistics from integrations."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models import Contact, Project, Campaign, Meeting, OutreachStats
from app.services.smartlead_service import smartlead_service

logger = logging.getLogger(__name__)


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
        Returns summary of what was synced.
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

        # Sync Email from SmartLead
        try:
            email_stats = await self._sync_email_stats(db, project, company_id, period_start, period_end)
            results["stats"].extend(email_stats)
            results["synced_channels"].append("email")
        except Exception as e:
            logger.error(f"Error syncing email stats: {e}")
            results["errors"].append(f"Email sync error: {str(e)}")

        # Sync LinkedIn from contacts (GetSales data)
        try:
            linkedin_stats = await self._sync_linkedin_stats(db, project_id, company_id, period_start, period_end)
            results["stats"].extend(linkedin_stats)
            results["synced_channels"].append("linkedin")
        except Exception as e:
            logger.error(f"Error syncing LinkedIn stats: {e}")
            results["errors"].append(f"LinkedIn sync error: {str(e)}")

        # Sync meetings from Calendly
        try:
            await self._sync_meeting_counts(db, project_id, period_start, period_end)
            results["synced_channels"].append("meetings")
        except Exception as e:
            logger.error(f"Error syncing meeting stats: {e}")
            results["errors"].append(f"Meetings sync error: {str(e)}")

        return results

    async def _sync_email_stats(
        self,
        db: AsyncSession,
        project: Project,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """Sync email stats from SmartLead campaigns."""
        stats_list = []

        # Get campaigns for this project from SmartLead
        # We'll aggregate by segment (campaign name pattern)
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id == project.id,
                    Campaign.platform == "email"
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        # Group campaigns by segment (extract from campaign name)
        segment_stats: Dict[str, Dict] = {}

        for campaign in campaigns:
            # Extract segment from campaign name (e.g., "Mifort - FinTech - Wave 1" -> "FinTech")
            segment = self._extract_segment_from_campaign(campaign.name)

            if segment not in segment_stats:
                segment_stats[segment] = {
                    "contacts_sent": 0,
                    "replies_count": 0,
                    "positive_replies": 0,
                }

            # Get stats from SmartLead API if we have campaign ID
            if campaign.smartlead_campaign_id:
                try:
                    sl_stats = await smartlead_service.get_campaign_stats(campaign.smartlead_campaign_id)
                    if sl_stats:
                        segment_stats[segment]["contacts_sent"] += sl_stats.get("sent_count", 0)
                        segment_stats[segment]["replies_count"] += sl_stats.get("reply_count", 0)
                except Exception as e:
                    logger.warning(f"Failed to get SmartLead stats for campaign {campaign.id}: {e}")

        # Count positive replies from contacts
        for segment in segment_stats:
            positive_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project.id,
                        Contact.channel == "email",
                        Contact.segment.ilike(f"%{segment}%"),
                        Contact.status.in_(["interested", "meeting_request", "positive"]),
                        Contact.last_reply_at >= datetime.combine(period_start, datetime.min.time()),
                        Contact.last_reply_at <= datetime.combine(period_end, datetime.max.time()),
                    )
                )
            )
            segment_stats[segment]["positive_replies"] = positive_count or 0

        # Upsert stats
        for segment, data in segment_stats.items():
            stat = await self._upsert_stat(
                db, company_id, project.id, period_start, period_end,
                channel="email",
                segment=segment,
                data=data,
                data_source="smartlead"
            )
            stats_list.append(stat.to_dict())

        return stats_list

    async def _sync_linkedin_stats(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> List[Dict]:
        """Sync LinkedIn stats from contacts (GetSales data)."""
        stats_list = []

        # Get all segments for LinkedIn contacts in this period
        segments_result = await db.execute(
            select(Contact.segment, func.count(Contact.id).label("count")).where(
                and_(
                    Contact.project_id == project_id,
                    Contact.channel == "linkedin",
                    Contact.created_at >= datetime.combine(period_start, datetime.min.time()),
                    Contact.created_at <= datetime.combine(period_end, datetime.max.time()),
                )
            ).group_by(Contact.segment)
        )
        segments = segments_result.all()

        for segment_row in segments:
            segment = segment_row.segment or "Unknown"

            # Count contacts sent (created in period)
            contacts_sent = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.channel == "linkedin",
                        Contact.segment == segment_row.segment,
                        Contact.created_at >= datetime.combine(period_start, datetime.min.time()),
                        Contact.created_at <= datetime.combine(period_end, datetime.max.time()),
                    )
                )
            )

            # Count accepts (has linkedin_connected or similar)
            contacts_accepted = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.channel == "linkedin",
                        Contact.segment == segment_row.segment,
                        Contact.status.in_(["connected", "accepted", "replied", "interested", "meeting_request"]),
                        Contact.created_at >= datetime.combine(period_start, datetime.min.time()),
                        Contact.created_at <= datetime.combine(period_end, datetime.max.time()),
                    )
                )
            )

            # Count replies
            replies_count = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.channel == "linkedin",
                        Contact.segment == segment_row.segment,
                        Contact.last_reply_at.isnot(None),
                        Contact.last_reply_at >= datetime.combine(period_start, datetime.min.time()),
                        Contact.last_reply_at <= datetime.combine(period_end, datetime.max.time()),
                    )
                )
            )

            # Count positive replies
            positive_replies = await db.scalar(
                select(func.count(Contact.id)).where(
                    and_(
                        Contact.project_id == project_id,
                        Contact.channel == "linkedin",
                        Contact.segment == segment_row.segment,
                        Contact.status.in_(["interested", "meeting_request", "positive"]),
                        Contact.last_reply_at >= datetime.combine(period_start, datetime.min.time()),
                        Contact.last_reply_at <= datetime.combine(period_end, datetime.max.time()),
                    )
                )
            )

            data = {
                "contacts_sent": contacts_sent or 0,
                "contacts_accepted": contacts_accepted or 0,
                "replies_count": replies_count or 0,
                "positive_replies": positive_replies or 0,
            }

            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel="linkedin",
                segment=segment,
                data=data,
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
        # Get meeting counts by channel/segment
        meeting_counts = await db.execute(
            select(
                Meeting.channel,
                Meeting.segment,
                func.count(Meeting.id).label("scheduled"),
                func.sum(
                    func.cast(Meeting.status == "completed", Integer)
                ).label("completed")
            ).where(
                and_(
                    Meeting.project_id == project_id,
                    Meeting.scheduled_at >= datetime.combine(period_start, datetime.min.time()),
                    Meeting.scheduled_at <= datetime.combine(period_end, datetime.max.time()),
                )
            ).group_by(Meeting.channel, Meeting.segment)
        )

        for row in meeting_counts:
            if not row.channel:
                continue

            # Update corresponding outreach_stats record
            stat_result = await db.execute(
                select(OutreachStats).where(
                    and_(
                        OutreachStats.project_id == project_id,
                        OutreachStats.channel == row.channel,
                        OutreachStats.segment == (row.segment or "Unknown"),
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
        """Extract segment name from campaign name.

        Examples:
        - "Mifort - FinTech - Wave 1" -> "FinTech"
        - "iGaming Marketing Campaign" -> "iGaming Marketing"
        - "General" -> "General"
        """
        if not campaign_name:
            return "Unknown"

        parts = campaign_name.split(" - ")
        if len(parts) >= 2:
            # Return second part (usually the segment)
            return parts[1].strip()

        # Try to extract without delimiter
        return campaign_name.strip()


# Singleton
outreach_stats_service = OutreachStatsService()
