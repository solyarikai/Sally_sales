"""Service for auto-calculating outreach statistics from integrations."""
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case

from app.models import Contact, Project, Campaign, Meeting, OutreachStats

logger = logging.getLogger(__name__)


class OutreachStatsService:
    """
    Auto-calculates outreach statistics by SEGMENT.

    Segment is extracted from campaign names (e.g., "Mifort Partners BizDevs" -> "Partners").

    For each campaign:
    - Find contacts belonging to that campaign via platform_state
    - Count sent/replied/positive in the selected period
    - Group by segment extracted from campaign name
    """

    async def sync_project_stats(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Sync stats for a project by scanning campaigns and their contacts."""
        results = {
            "synced_channels": [],
            "errors": [],
            "stats": []
        }

        project = await db.get(Project, project_id)
        if not project:
            results["errors"].append(f"Project {project_id} not found")
            return results

        # Delete old auto-generated stats for this period (keep manual entries)
        await db.execute(
            OutreachStats.__table__.delete().where(
                and_(
                    OutreachStats.project_id == project_id,
                    OutreachStats.period_start == period_start,
                    OutreachStats.period_end == period_end,
                    OutreachStats.is_manual == 0,
                )
            )
        )
        await db.commit()
        logger.info(f"Cleared auto-generated stats for project {project_id}, period {period_start} - {period_end}")

        period_start_dt = datetime.combine(period_start, datetime.min.time())
        period_end_dt = datetime.combine(period_end, datetime.max.time())

        # Sync Email (SmartLead campaigns)
        try:
            email_stats = await self._sync_email_stats(
                db, project_id, company_id, period_start, period_end,
                period_start_dt, period_end_dt,
            )
            results["stats"].extend(email_stats)
            if email_stats:
                results["synced_channels"].append("email")
        except Exception as e:
            logger.error(f"Error syncing email stats: {e}", exc_info=True)
            results["errors"].append(f"Email sync error: {str(e)}")

        # Sync LinkedIn (GetSales campaigns)
        try:
            linkedin_stats = await self._sync_linkedin_stats(
                db, project_id, company_id, period_start, period_end,
                period_start_dt, period_end_dt,
            )
            results["stats"].extend(linkedin_stats)
            if linkedin_stats:
                results["synced_channels"].append("linkedin")
        except Exception as e:
            logger.error(f"Error syncing LinkedIn stats: {e}", exc_info=True)
            results["errors"].append(f"LinkedIn sync error: {str(e)}")

        # Sync meetings
        try:
            await self._sync_meeting_counts(db, project_id, period_start, period_end)
            results["synced_channels"].append("meetings")
        except Exception as e:
            logger.error(f"Error syncing meeting stats: {e}", exc_info=True)
            results["errors"].append(f"Meetings sync error: {str(e)}")

        return results

    async def _sync_email_stats(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
        period_start_dt: datetime,
        period_end_dt: datetime,
    ) -> List[Dict]:
        """
        Sync email stats from SmartLead campaigns.
        Uses campaign-level stats (leads_count, sl_reply_count) and groups by segment.
        """
        stats_list = []

        # Get all email campaigns for this project
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id == project_id,
                    Campaign.channel == "email",
                    Campaign.status != "archived",
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        if not campaigns:
            logger.info(f"No email campaigns for project {project_id}")
            return stats_list

        # Group by segment
        segment_data: Dict[str, Dict] = {}

        for campaign in campaigns:
            segment = self._extract_segment_from_campaign(campaign.name)

            if segment not in segment_data:
                segment_data[segment] = {
                    "contacts_sent": 0,
                    "replies_count": 0,
                    "positive_replies": 0,
                    "campaign_names": [],
                }

            # Use campaign-level stats
            segment_data[segment]["contacts_sent"] += campaign.leads_count or 0
            segment_data[segment]["replies_count"] += campaign.sl_reply_count or 0
            segment_data[segment]["campaign_names"].append(campaign.name)

        # Get positive contacts and distribute by segment based on their campaigns
        positive_contacts_result = await db.execute(
            select(Contact).where(
                and_(
                    Contact.project_id == project_id,
                    Contact.deleted_at.is_(None),
                    Contact.source.ilike("%smartlead%"),
                    Contact.status.in_(["replied", "negotiating_meeting", "qualified"]),
                )
            )
        )
        positive_contacts = positive_contacts_result.scalars().all()

        # Build campaign ID to segment mapping
        campaign_to_segment: Dict[str, str] = {}
        for campaign in campaigns:
            if campaign.external_id:
                campaign_to_segment[campaign.external_id] = self._extract_segment_from_campaign(campaign.name)

        # Count positive contacts per segment
        for contact in positive_contacts:
            contact_campaign_ids = self._get_contact_campaign_ids(contact, "smartlead")
            matched_segments: Set[str] = set()

            for cid in contact_campaign_ids:
                if cid in campaign_to_segment:
                    matched_segments.add(campaign_to_segment[cid])

            # If no match, try campaign names in platform_state
            if not matched_segments:
                ps = contact.platform_state or {}
                sl_data = ps.get("smartlead") or {}
                sl_campaigns = sl_data.get("campaigns") or []
                for sc in sl_campaigns:
                    if isinstance(sc, dict):
                        camp_name = sc.get("name")
                        if camp_name:
                            segment = self._extract_segment_from_campaign(camp_name)
                            if segment in segment_data:
                                matched_segments.add(segment)

            # Distribute to matched segments
            for segment in matched_segments:
                if segment in segment_data:
                    segment_data[segment]["positive_replies"] += 1

        # Create stats for each segment with activity
        for segment, data in segment_data.items():
            if data["contacts_sent"] == 0:
                continue

            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel="email",
                segment=segment,
                data={
                    "contacts_sent": data["contacts_sent"],
                    "contacts_accepted": data["contacts_sent"],
                    "replies_count": data["replies_count"],
                    "positive_replies": data["positive_replies"],
                },
                data_source="smartlead"
            )
            stats_list.append(stat.to_dict())
            logger.info(
                f"EMAIL segment '{segment}': "
                f"sent={data['contacts_sent']}, replied={data['replies_count']}, "
                f"positive={data['positive_replies']}, campaigns={len(data['campaign_names'])}"
            )

        return stats_list

    async def _sync_linkedin_stats(
        self,
        db: AsyncSession,
        project_id: int,
        company_id: int,
        period_start: date,
        period_end: date,
        period_start_dt: datetime,
        period_end_dt: datetime,
    ) -> List[Dict]:
        """
        Sync LinkedIn stats by iterating through campaigns and matching contacts.

        For each GetSales campaign:
        1. Find contacts where platform_state.getsales.campaigns contains the campaign ID
        2. Count sent/replied/positive
        3. Group by segment extracted from campaign name
        """
        stats_list = []

        # Get LinkedIn campaigns for this project
        campaigns_result = await db.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id == project_id,
                    Campaign.channel == "linkedin",
                    Campaign.status != "archived",
                )
            )
        )
        campaigns = campaigns_result.scalars().all()

        if not campaigns:
            logger.info(f"No LinkedIn campaigns for project {project_id}")
            return stats_list

        # Build campaign ID to segment mapping
        campaign_to_segment: Dict[str, str] = {}
        segment_data: Dict[str, Dict] = {}

        for campaign in campaigns:
            segment = self._extract_segment_from_campaign(campaign.name)
            if campaign.external_id:
                campaign_to_segment[campaign.external_id] = segment

            if segment not in segment_data:
                segment_data[segment] = {
                    "contacts_sent": 0,
                    "replies_count": 0,
                    "positive_replies": 0,
                    "campaign_ids": [],
                    "campaign_names": [],
                }
            if campaign.external_id:
                segment_data[segment]["campaign_ids"].append(campaign.external_id)
            segment_data[segment]["campaign_names"].append(campaign.name)

        # Get all LinkedIn contacts for this project that were active in the period
        contacts_result = await db.execute(
            select(Contact).where(
                and_(
                    Contact.project_id == project_id,
                    Contact.deleted_at.is_(None),
                    Contact.source.ilike("%getsales%"),
                    or_(
                        and_(
                            Contact.created_at >= period_start_dt,
                            Contact.created_at <= period_end_dt,
                        ),
                        and_(
                            Contact.last_reply_at >= period_start_dt,
                            Contact.last_reply_at <= period_end_dt,
                        ),
                    )
                )
            )
        )
        contacts = contacts_result.scalars().all()

        logger.info(f"Found {len(contacts)} LinkedIn contacts for project {project_id} in period")

        # Process each contact and assign to segments
        for contact in contacts:
            # Get campaign IDs this contact belongs to
            contact_campaign_ids = self._get_contact_campaign_ids(contact, "getsales")

            # Find matching segments
            matched_segments: Set[str] = set()
            for cid in contact_campaign_ids:
                if cid in campaign_to_segment:
                    matched_segments.add(campaign_to_segment[cid])

            # If no match via campaign ID, try matching by campaign name in platform_state
            if not matched_segments:
                ps = contact.platform_state or {}
                gs_data = ps.get("getsales") or {}
                gs_campaigns = gs_data.get("campaigns") or []
                for gc in gs_campaigns:
                    if isinstance(gc, dict):
                        camp_name = gc.get("name")
                        if camp_name:
                            segment = self._extract_segment_from_campaign(camp_name)
                            if segment in segment_data:
                                matched_segments.add(segment)

            # If still no match, assign to "General"
            if not matched_segments:
                if "General" not in segment_data:
                    segment_data["General"] = {
                        "contacts_sent": 0,
                        "replies_count": 0,
                        "positive_replies": 0,
                        "campaign_ids": [],
                        "campaign_names": [],
                    }
                matched_segments.add("General")

            # Count for each matched segment
            is_created_in_period = (
                contact.created_at and
                period_start_dt <= contact.created_at <= period_end_dt
            )
            is_replied_in_period = (
                contact.last_reply_at and
                period_start_dt <= contact.last_reply_at <= period_end_dt
            )
            is_positive = contact.status in ["interested", "meeting_request", "positive", "qualified"]

            for segment in matched_segments:
                if is_created_in_period:
                    segment_data[segment]["contacts_sent"] += 1
                if is_replied_in_period:
                    segment_data[segment]["replies_count"] += 1
                if is_positive and is_replied_in_period:
                    segment_data[segment]["positive_replies"] += 1

        # Create stats for each segment with activity
        for segment, data in segment_data.items():
            if data["contacts_sent"] == 0 and data["replies_count"] == 0:
                continue

            stat = await self._upsert_stat(
                db, company_id, project_id, period_start, period_end,
                channel="linkedin",
                segment=segment,
                data={
                    "contacts_sent": data["contacts_sent"],
                    "contacts_accepted": data["contacts_sent"],
                    "replies_count": data["replies_count"],
                    "positive_replies": data["positive_replies"],
                },
                data_source="getsales"
            )
            stats_list.append(stat.to_dict())
            logger.info(
                f"LINKEDIN segment '{segment}': "
                f"sent={data['contacts_sent']}, replied={data['replies_count']}, "
                f"positive={data['positive_replies']}, campaigns={len(data['campaign_names'])}"
            )

        return stats_list

    def _get_contact_campaign_ids(self, contact: Contact, platform: str) -> Set[str]:
        """Extract campaign IDs from contact's platform_state and raw data."""
        campaign_ids: Set[str] = set()

        # From platform_state
        ps = contact.platform_state or {}
        platform_data = ps.get(platform) or {}
        campaigns = platform_data.get("campaigns") or []
        for camp in campaigns:
            if isinstance(camp, dict) and camp.get("id"):
                campaign_ids.add(str(camp["id"]))

        # From raw data
        if platform == "getsales" and contact.getsales_raw:
            flows = contact.getsales_raw.get("flows") or []
            for flow in flows:
                if isinstance(flow, dict) and flow.get("flow_uuid"):
                    campaign_ids.add(flow["flow_uuid"])
        elif platform == "smartlead" and contact.smartlead_raw:
            raw_camps = contact.smartlead_raw.get("campaigns") or []
            for rc in raw_camps:
                if isinstance(rc, dict) and rc.get("campaign_id"):
                    campaign_ids.add(str(rc["campaign_id"]))

        return campaign_ids

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
        - "Mifort Partners BizDevs" -> "Partners"
        - "Mifort Partners CEOs" -> "Partners"
        - "Mifort FinTech Clay 0303" -> "FinTech"
        - "Mifort iGaming Marketing" -> "iGaming"
        - "Mifort IT Partners Founders" -> "IT Partners"
        """
        if not campaign_name:
            return "General"

        name = campaign_name.strip()

        # Remove project prefix (Mifort, Mifort., etc.)
        name = re.sub(r'^Mifort\.?\s*', '', name, flags=re.IGNORECASE)

        # Remove date patterns
        name = re.sub(r'\s+\d{4}$', '', name)
        name = re.sub(r'\s+\d{2}\.\d{2}$', '', name)
        name = re.sub(r'\s+\d{2}/\d{2}$', '', name)

        # Remove "Clay" suffix
        name = re.sub(r'\s+Clay\s*\d*$', '', name, flags=re.IGNORECASE)

        # Remove trailing numbers
        name = re.sub(r'\s+\d+$', '', name)

        # Remove job title suffixes to group by segment
        name = re.sub(r'\s+(Marketing|BizDevs?|CEOs?|CTOs?|Founders?|VPs?|Directors?|CMOs?|COOs?|CFOs?)$', '', name, flags=re.IGNORECASE)

        # Clean up
        name = ' '.join(name.split())

        if not name:
            return "General"

        if len(name) > 50:
            name = name[:50].rsplit(' ', 1)[0]

        return name


# Singleton
outreach_stats_service = OutreachStatsService()
