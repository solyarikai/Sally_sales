"""
CRM Sync Scheduler - Background job for periodic sync.

Runs CRM sync at configurable intervals with:
- Full sync every 30 minutes
- Reply check via API every 30 minutes (backup to webhooks)
- Webhook setup check every 6 hours (for new campaigns)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db import async_session_maker
from app.services.crm_sync_service import get_crm_sync_service, get_getsales_flow_name
from app.services.cache_service import backfill_reply_cache_from_db

logger = logging.getLogger(__name__)


class CRMScheduler:
    """
    Background scheduler for CRM sync jobs.
    
    Runs periodic sync from Smartlead and GetSales.
    """
    
    def __init__(
        self,
        sync_interval_minutes: int = 30,
        reply_check_interval_minutes: int = 30,
        webhook_check_interval_hours: int = 6,
        report_interval_hours: int = 4,
        prompt_refresh_interval_hours: int = 168,  # Weekly (7 days)
        company_id: int = 1
    ):
        self.sync_interval = sync_interval_minutes * 60
        self.reply_check_interval = reply_check_interval_minutes * 60
        self.webhook_check_interval = webhook_check_interval_hours * 3600
        self.report_interval = report_interval_hours * 3600
        self.prompt_refresh_interval = prompt_refresh_interval_hours * 3600
        self.company_id = company_id
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reply_task: Optional[asyncio.Task] = None
        self._webhook_task: Optional[asyncio.Task] = None
        self._report_task: Optional[asyncio.Task] = None
        self._prompt_refresh_task: Optional[asyncio.Task] = None
        self._last_sync: Optional[datetime] = None
        self._last_reply_check: Optional[datetime] = None
        self._last_webhook_check: Optional[datetime] = None
        self._last_prompt_refresh: Optional[datetime] = None
        self._sync_count = 0
        self._reply_count = 0
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("CRM scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._reply_task = asyncio.create_task(self._run_reply_loop())
        self._webhook_task = asyncio.create_task(self._run_webhook_loop())
        self._report_task = asyncio.create_task(self._run_report_loop())
        self._prompt_refresh_task = asyncio.create_task(self._run_prompt_refresh_loop())
        logger.info(f"CRM scheduler started (sync: {self.sync_interval // 60}min, replies: {self.reply_check_interval // 60}min, webhooks: {self.webhook_check_interval // 3600}h, reports: {self.report_interval // 3600}h, prompt_refresh: {self.prompt_refresh_interval // 3600}h)")
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for task in [self._task, self._reply_task, self._webhook_task, self._report_task, self._prompt_refresh_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("CRM scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self._run_sync()
                self._sync_count += 1
                self._last_sync = datetime.utcnow()
            except Exception as e:
                logger.error(f"CRM sync error: {e}")
            await asyncio.sleep(self.sync_interval)
    
    async def _run_reply_loop(self):
        """Reply check loop - runs every 30 minutes to catch replies via API."""
        await asyncio.sleep(60)  # Initial delay
        while self._running:
            try:
                await self._auto_assign_new_campaigns()
            except Exception as e:
                logger.error(f"Auto-assign campaigns error: {e}")
            try:
                await self._check_replies()
                self._reply_count += 1
                self._last_reply_check = datetime.utcnow()
            except Exception as e:
                logger.error(f"Reply check error: {e}")
            await asyncio.sleep(self.reply_check_interval)
    
    async def _run_webhook_loop(self):
        """Webhook setup loop - runs every 6 hours to configure new campaigns."""
        await asyncio.sleep(300)  # Initial delay (5 min)
        while self._running:
            try:
                await self._setup_webhooks()
                self._last_webhook_check = datetime.utcnow()
            except Exception as e:
                logger.error(f"Webhook setup error: {e}")
            await asyncio.sleep(self.webhook_check_interval)
    
    async def _run_prompt_refresh_loop(self):
        """Prompt refresh loop - runs weekly to regenerate project reply prompts."""
        await asyncio.sleep(3600)  # Initial delay (1 hour)
        while self._running:
            try:
                await self._refresh_project_prompts()
                self._last_prompt_refresh = datetime.utcnow()
            except Exception as e:
                logger.error(f"Prompt refresh error: {e}")
            await asyncio.sleep(self.prompt_refresh_interval)

    async def _refresh_project_prompts(self):
        """Re-generate reply prompts for all projects that have one set."""
        from app.models.contact import Project
        from app.services.conversation_analysis_service import generate_auto_reply_prompt
        from sqlalchemy import select

        logger.info("Starting weekly prompt refresh for projects...")

        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    select(Project).where(
                        Project.reply_prompt_template_id.isnot(None),
                        Project.deleted_at.is_(None),
                    )
                )
                projects = result.scalars().all()

                refreshed = 0
                for project in projects:
                    try:
                        result = await generate_auto_reply_prompt(session, project.id)
                        if result and "error" not in result:
                            refreshed += 1
                            logger.info(f"Refreshed prompt for project '{project.name}'")
                        else:
                            logger.warning(f"Prompt refresh skipped for '{project.name}': {result.get('error') if result else 'no result'}")
                    except Exception as e:
                        logger.warning(f"Prompt refresh failed for '{project.name}': {e}")

                await session.commit()
                logger.info(f"Weekly prompt refresh complete: {refreshed}/{len(projects)} projects refreshed")

            except Exception as e:
                logger.error(f"Prompt refresh failed: {e}")
                raise

    async def _run_sync(self):
        """Run a single sync cycle."""
        logger.info(f"Starting scheduled CRM sync (run #{self._sync_count + 1})")
        
        sync_service = get_crm_sync_service()
        
        async with async_session_maker() as session:
            try:
                results = await sync_service.full_sync(session, self.company_id)
                
                if results.get("smartlead", {}).get("contacts"):
                    sl = results["smartlead"]["contacts"]
                    logger.info(f"Smartlead sync: {sl.get('created', 0)} created, {sl.get('updated', 0)} updated")
                
                if results.get("smartlead", {}).get("replies"):
                    replies = results["smartlead"]["replies"]
                    logger.info(f"Smartlead replies: {replies.get('new_replies', 0)} new")
                
                if results.get("getsales", {}).get("contacts"):
                    gs = results["getsales"]["contacts"]
                    logger.info(f"GetSales sync: {gs.get('created', 0)} created, {gs.get('updated', 0)} updated")
                
                logger.info("Scheduled CRM sync completed")
                
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                raise
    
    async def _auto_assign_new_campaigns(self):
        """Auto-discover new Smartlead campaigns and assign to matching projects."""
        from app.models.contact import Project
        from sqlalchemy import select, and_

        sync_service = get_crm_sync_service()
        if not sync_service.smartlead:
            return

        try:
            all_campaigns = await sync_service.smartlead.get_campaigns()
        except Exception as e:
            logger.warning(f"Failed to fetch campaigns for auto-assign: {e}")
            return

        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    select(Project).where(
                        and_(
                            Project.campaign_filters.isnot(None),
                            Project.deleted_at.is_(None),
                        )
                    )
                )
                projects = result.scalars().all()

                if not projects:
                    return

                # Collect all campaign names already assigned to any project
                assigned_names = set()
                for p in projects:
                    for name in (p.campaign_filters or []):
                        assigned_names.add(name.lower())

                assigned_count = 0
                for campaign in all_campaigns:
                    c_name = campaign.get("name", "")
                    if not c_name or c_name.lower() in assigned_names:
                        continue

                    # Match campaign name against project names (case-insensitive substring)
                    for project in projects:
                        if project.name.lower() in c_name.lower():
                            filters = list(project.campaign_filters or [])
                            filters.append(c_name)
                            project.campaign_filters = filters
                            assigned_names.add(c_name.lower())
                            assigned_count += 1
                            logger.info(f"Auto-assigned campaign '{c_name}' to project '{project.name}'")
                            break

                if assigned_count > 0:
                    await session.commit()
                    logger.info(f"Auto-assigned {assigned_count} new campaigns to projects")
                    # Trigger webhook setup for new campaigns
                    try:
                        await setup_crm_webhooks_on_startup()
                    except Exception as e:
                        logger.warning(f"Webhook setup after auto-assign failed: {e}")

            except Exception as e:
                logger.error(f"Auto-assign campaigns failed: {e}")

    async def _check_replies(self):
        """Check for new replies via API polling (backup to webhooks)."""
        logger.info(f"Checking replies via API (run #{self._reply_count + 1})")
        sync_service = get_crm_sync_service()
        
        async with async_session_maker() as session:
            try:
                # Check Smartlead replies
                if sync_service.smartlead:
                    results = await sync_service.sync_smartlead_replies(session, self.company_id)
                    new_replies = results.get('new_replies', 0)
                    campaigns_checked = results.get('campaigns_checked', 0)
                    logger.info(f"Smartlead reply check: {new_replies} new, {campaigns_checked} campaigns checked")
            except Exception as e:
                logger.error(f"Smartlead reply check failed: {e}")
            
            try:
                # Check GetSales replies
                if sync_service.getsales:
                    results = await sync_service.sync_getsales_replies(session, self.company_id)
                    new_replies = results.get('new_replies', 0)
                    if new_replies > 0:
                        logger.info(f"GetSales reply check: {new_replies} new replies found")
            except Exception as e:
                logger.error(f"GetSales reply check failed: {e}")
    
    async def _run_report_loop(self):
        """Send Telegram report every 4 hours with reply summary."""
        await asyncio.sleep(300)  # Initial delay 5 min
        while self._running:
            try:
                await self._send_reply_report()
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
            await asyncio.sleep(self.report_interval)
    
    async def _send_reply_report(self):
        """Generate and send Telegram report of replies in last 24 hours."""
        from app.db import async_session_maker
        from app.models.reply import ProcessedReply
        from app.models.contact import Contact, ContactActivity
        from app.services.notification_service import send_telegram_notification
        from sqlalchemy import select, func, and_
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(hours=24)
        
        async with async_session_maker() as session:
            # Get Smartlead warm replies with lead names
            smartlead_warm_query = await session.execute(
                select(ProcessedReply).where(
                    and_(
                        ProcessedReply.received_at >= since,
                        ProcessedReply.category.in_(["interested", "meeting_request", "question"])
                    )
                ).order_by(ProcessedReply.campaign_name, ProcessedReply.received_at.desc())
            )
            smartlead_warm = smartlead_warm_query.scalars().all()
            
            # Get Smartlead negative count
            smartlead_negative_query = await session.execute(
                select(func.count(ProcessedReply.id)).where(
                    and_(
                        ProcessedReply.received_at >= since,
                        ProcessedReply.category.in_(["not_interested", "unsubscribe", "wrong_person"])
                    )
                )
            )
            negative_total = smartlead_negative_query.scalar() or 0
            
            # Get GetSales LinkedIn replies with contact info and flow names
            getsales_query = await session.execute(
                select(ContactActivity, Contact).join(
                    Contact, ContactActivity.contact_id == Contact.id
                ).where(
                    and_(
                        ContactActivity.activity_type == "linkedin_replied",
                        ContactActivity.activity_at >= since
                    )
                ).order_by(ContactActivity.activity_at.desc())
            )
            getsales_replies = getsales_query.all()
            
            # Organize email replies by campaign (unique contacts)
            email_by_campaign = {}
            seen_email_contacts = set()
            for reply in smartlead_warm:
                campaign = reply.campaign_name or "Unknown"
                contact_key = (campaign, reply.lead_email.lower() if reply.lead_email else "")
                if contact_key in seen_email_contacts:
                    continue
                seen_email_contacts.add(contact_key)
                if campaign not in email_by_campaign:
                    email_by_campaign[campaign] = []
                name = f"{reply.lead_first_name or ''} {reply.lead_last_name or ''}".strip() or reply.lead_email
                email_by_campaign[campaign].append(name)
            
            # Organize LinkedIn replies by flow (unique contacts)
            linkedin_by_flow = {}
            seen_linkedin_contacts = set()
            for activity, contact in getsales_replies:
                flow_name = get_getsales_flow_name(activity.extra_data, contact.campaigns)
                contact_key = (flow_name, contact.id)
                if contact_key in seen_linkedin_contacts:
                    continue
                seen_linkedin_contacts.add(contact_key)
                if flow_name not in linkedin_by_flow:
                    linkedin_by_flow[flow_name] = []
                name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email
                linkedin_by_flow[flow_name].append(name)
            
            # Count unique contacts (after deduplication)
            warm_email = len(seen_email_contacts)
            warm_linkedin = len(seen_linkedin_contacts)
            warm_total = warm_email + warm_linkedin
            
            # Build message
            lines = []
            lines.append("<b>📊 Replies Report</b> <i>(Last 24h)</i>")
            lines.append("")
            lines.append(f"<b>🔥 WARM LEADS ({warm_total})</b>")
            
            # Email section
            if email_by_campaign:
                lines.append("")
                lines.append(f"<b>📧 Email ({warm_email}):</b>")
                for campaign, leads in sorted(email_by_campaign.items(), key=lambda x: -len(x[1]))[:8]:
                    lines.append(f"<code>{campaign[:35]}</code> ({len(leads)})")
                    for lead in leads[:5]:
                        lines.append(f"  └ {lead[:25]}")
                    if len(leads) > 5:
                        lines.append(f"  └ <i>+{len(leads)-5} more...</i>")
            
            # LinkedIn section
            if linkedin_by_flow:
                lines.append("")
                lines.append(f"<b>💼 LinkedIn ({warm_linkedin}):</b>")
                for flow, leads in sorted(linkedin_by_flow.items(), key=lambda x: -len(x[1]))[:8]:
                    lines.append(f"<code>{flow[:35]}</code> ({len(leads)})")
                    for lead in leads[:5]:
                        lines.append(f"  └ {lead[:25]}")
                    if len(leads) > 5:
                        lines.append(f"  └ <i>+{len(leads)-5} more...</i>")
            
            lines.append("")
            lines.append(f"<b>❌ Not Interested:</b> {negative_total}")
            lines.append("")
            lines.append(f"<b>📈 Total: {warm_total + negative_total}</b>")
            
            message = "\n".join(lines)
            await send_telegram_notification(message)
            logger.info(f"Sent reply report: {warm_email} email warm, {warm_linkedin} LinkedIn warm, {negative_total} negative")

    async def _setup_webhooks(self):
        """Set up webhooks for any new campaigns."""
        logger.info("Checking for new campaigns to configure webhooks...")
        await setup_crm_webhooks_on_startup()
    
    async def run_now(self):
        """Trigger an immediate sync outside the schedule."""
        logger.info("Manual CRM sync triggered")
        await self._run_sync()
        self._last_sync = datetime.utcnow()
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "sync_interval_minutes": self.sync_interval // 60,
            "reply_check_interval_minutes": self.reply_check_interval // 60,
            "webhook_check_interval_hours": self.webhook_check_interval // 3600,
            "company_id": self.company_id,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "last_reply_check": self._last_reply_check.isoformat() if self._last_reply_check else None,
            "last_webhook_check": self._last_webhook_check.isoformat() if self._last_webhook_check else None,
            "last_prompt_refresh": self._last_prompt_refresh.isoformat() if self._last_prompt_refresh else None,
            "prompt_refresh_interval_hours": self.prompt_refresh_interval // 3600,
            "sync_count": self._sync_count,
            "reply_check_count": self._reply_count
        }


# Global scheduler instance
_crm_scheduler: Optional[CRMScheduler] = None


def get_crm_scheduler() -> CRMScheduler:
    """Get or create the CRM scheduler singleton."""
    global _crm_scheduler
    if _crm_scheduler is None:
        _crm_scheduler = CRMScheduler()
    return _crm_scheduler


async def start_crm_scheduler():
    """Start the CRM scheduler."""
    scheduler = get_crm_scheduler()
    await scheduler.start()
    
    # Backfill reply cache from DB
    try:
        stats = await backfill_reply_cache_from_db()
        logger.info(f"Reply cache backfill: {stats}")
    except Exception as e:
        logger.warning(f"Reply cache backfill failed (non-fatal): {e}")
    
    # Also set up webhooks on startup
    await setup_crm_webhooks_on_startup()


async def setup_crm_webhooks_on_startup():
    """Set up CRM webhooks in external systems."""
    from app.services.crm_sync_service import get_crm_sync_service
    
    logger.info("Setting up CRM webhooks for all campaigns...")
    
    webhook_base_url = "http://46.62.210.24:8000/api"
    
    sync_service = get_crm_sync_service()
    
    # Set up GetSales webhooks
    if sync_service.getsales:
        try:
            getsales_url = f"{webhook_base_url}/crm-sync/webhook/getsales"
            results = await sync_service.getsales.setup_crm_webhooks(getsales_url)
            logger.info(f"GetSales webhooks: {len(results.get('created', []))} created, {len(results.get('existing', []))} existing")
        except Exception as e:
            logger.warning(f"Failed to set up GetSales webhooks: {e}")
    
    # Set up Smartlead webhooks - using correct endpoint
    if sync_service.smartlead:
        try:
            smartlead_url = f"{webhook_base_url}/smartlead/webhook"
            results = await sync_service.smartlead.setup_crm_webhooks(smartlead_url)
            created = len(results.get('created', []))
            existing = len(results.get('existing', []))
            skipped = len(results.get('skipped', []))
            failed = len(results.get('failed', []))
            active_count = created + existing
            
            # Log detailed summary
            logger.info(f"Smartlead webhook setup complete:")
            logger.info(f"  - Active campaigns with webhooks: {active_count}")
            logger.info(f"  - New webhooks created: {created}")
            logger.info(f"  - Already configured: {existing}")
            logger.info(f"  - Inactive campaigns skipped: {skipped}")
            if failed > 0:
                logger.warning(f"  - Failed: {failed}")
                for f_item in results.get('failed', [])[:5]:
                    logger.warning(f"    {f_item.get('name')}: {f_item.get('error')}")
        except Exception as e:
            logger.warning(f"Failed to set up Smartlead webhooks: {e}")


async def stop_crm_scheduler():
    """Stop the CRM scheduler."""
    global _crm_scheduler
    if _crm_scheduler:
        await _crm_scheduler.stop()
        _crm_scheduler = None
