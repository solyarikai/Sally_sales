"""
CRM Sync Scheduler - Robust background job system.

Features:
- Full CRM sync every 30 minutes
- Adaptive reply polling: 3 min fast (startup/degraded), 10 min steady state
- Webhook registration every 60 min (5 min retry on failure)
- Webhook health monitoring
- Event recovery loop: reprocesses failed webhook events with exponential backoff
- Task watchdog: resurrects dead scheduler tasks within 60 seconds
- Per-project periodic reports every 4 hours
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.db import async_session_maker
from app.services.crm_sync_service import get_crm_sync_service, get_getsales_flow_name
from app.services.cache_service import backfill_reply_cache_from_db

logger = logging.getLogger(__name__)


async def _get_campaign_names_by_status(enabled: bool) -> set:
    """Query campaign names from projects by webhooks_enabled status."""
    from app.models.contact import Project
    async with async_session_maker() as session:
        result = await session.execute(
            select(Project.campaign_filters).where(
                Project.webhooks_enabled == enabled,
                Project.campaign_filters.isnot(None),
                Project.deleted_at.is_(None),
            )
        )
        names = set()
        for (filters,) in result.all():
            if isinstance(filters, list):
                names.update(filters)
        return names


# Shared webhook health state (updated by webhook handlers)
_last_webhook_received_at: Optional[datetime] = None


def mark_webhook_received():
    """Called by webhook handlers to signal that webhooks are working."""
    global _last_webhook_received_at
    _last_webhook_received_at = datetime.utcnow()


class CRMScheduler:
    """
    Robust background scheduler for CRM sync jobs.
    
    Self-healing: watchdog resurrects dead tasks, recovery loop retries failed events.
    """
    
    def __init__(
        self,
        sync_interval_minutes: int = 30,
        report_interval_hours: int = 4,
        prompt_refresh_interval_hours: int = 168,  # Weekly
        company_id: int = 1
    ):
        self.sync_interval = sync_interval_minutes * 60
        self.report_interval = report_interval_hours * 3600
        self.prompt_refresh_interval = prompt_refresh_interval_hours * 3600
        self.company_id = company_id
        self._running = False
        
        # Task references
        self._task: Optional[asyncio.Task] = None
        self._reply_task: Optional[asyncio.Task] = None
        self._webhook_task: Optional[asyncio.Task] = None
        self._report_task: Optional[asyncio.Task] = None
        self._prompt_refresh_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._conversation_sync_task: Optional[asyncio.Task] = None
        self._telegram_poll_task: Optional[asyncio.Task] = None
        self._sheet_sync_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        
        # Per-task tracking: last_run, interval_seconds, next_run
        self._task_timing: dict[str, dict] = {
            "reply_check": {"last_run": None, "interval": 180, "label": "Reply polling"},
            "sync": {"last_run": None, "interval": sync_interval_minutes * 60, "label": "Full CRM sync"},
            "webhook_setup": {"last_run": None, "interval": 3600, "label": "Webhook registration"},
            "conversation_sync": {"last_run": None, "interval": 180, "label": "Conversation sync"},
            "sheet_sync": {"last_run": None, "interval": 300, "label": "Sheet sync"},
            "event_recovery": {"last_run": None, "interval": 300, "label": "Event recovery"},
            "prompt_refresh": {"last_run": None, "interval": prompt_refresh_interval_hours * 3600, "label": "Prompt refresh"},
            "report": {"last_run": None, "interval": report_interval_hours * 3600, "label": "Reports"},
            "needs_reply_cleanup": {"last_run": None, "interval": 21600, "label": "Needs-reply cleanup"},
        }
        self._last_sync: Optional[datetime] = None
        self._last_reply_check: Optional[datetime] = None
        self._last_webhook_check: Optional[datetime] = None
        self._last_prompt_refresh: Optional[datetime] = None
        self._sync_count = 0
        self._reply_count = 0
        self._webhook_healthy = True
        
        # Campaign list cache (avoid fetching all 1700 campaigns every 3 min)
        self._campaign_cache: Optional[list] = None
        self._campaign_cache_at: Optional[datetime] = None
        self._CAMPAIGN_CACHE_TTL = 1800  # 30 min
    
    def _mark_task_run(self, task_name: str, interval: int = None):
        """Record that a task just completed. Optionally update its interval."""
        now = datetime.utcnow()
        if task_name in self._task_timing:
            self._task_timing[task_name]["last_run"] = now
            if interval is not None:
                self._task_timing[task_name]["interval"] = interval

    async def _get_campaigns_cached(self) -> list:
        """Get SmartLead campaigns with 30-min cache. One API call instead of per-cycle."""
        now = datetime.utcnow()
        if (self._campaign_cache is not None
                and self._campaign_cache_at
                and (now - self._campaign_cache_at).total_seconds() < self._CAMPAIGN_CACHE_TTL):
            return self._campaign_cache
        
        sync_service = get_crm_sync_service()
        if not sync_service.smartlead:
            return []
        campaigns = await sync_service.smartlead.get_campaigns()
        self._campaign_cache = campaigns
        self._campaign_cache_at = now
        logger.info(f"Campaign cache refreshed: {len(campaigns)} campaigns")
        return campaigns

    async def start(self):
        """Start all scheduler tasks + watchdog."""
        if self._running:
            logger.warning("CRM scheduler already running")
            return
        
        self._running = True
        self._start_all_tasks()
        self._watchdog_task = asyncio.create_task(self._run_watchdog())
        logger.info("CRM scheduler started (sync: 30min, replies: adaptive 3-10min, webhooks: 1h, reports: 4h, recovery: 5min)")
    
    async def stop(self):
        """Stop all scheduler tasks."""
        self._running = False
        all_tasks = [
            self._task, self._reply_task, self._webhook_task,
            self._report_task, self._prompt_refresh_task,
            self._recovery_task, self._conversation_sync_task,
            self._telegram_poll_task, self._sheet_sync_task,
            self._cleanup_task, self._watchdog_task
        ]
        for task in all_tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("CRM scheduler stopped")
    
    def _start_all_tasks(self):
        """Start or restart all scheduler tasks. Called by watchdog to resurrect dead tasks."""
        task_configs = [
            ("_task", self._run_loop, "CRM sync"),
            ("_reply_task", self._run_reply_loop, "Reply check"),
            ("_webhook_task", self._run_webhook_loop, "Webhook setup"),
            ("_report_task", self._run_report_loop, "Report"),
            ("_prompt_refresh_task", self._run_prompt_refresh_loop, "Prompt refresh"),
            ("_recovery_task", self._run_event_recovery_loop, "Event recovery"),
            ("_conversation_sync_task", self._run_conversation_sync_loop, "Conversation sync"),
            ("_telegram_poll_task", self._run_telegram_poll_loop, "Telegram poll"),
            ("_sheet_sync_task", self._run_sheet_sync_loop, "Sheet sync"),
            ("_cleanup_task", self._run_needs_reply_cleanup_loop, "Needs-reply cleanup"),
        ]
        for attr, coro_fn, name in task_configs:
            existing = getattr(self, attr, None)
            if existing is None or existing.done():
                if existing and existing.done():
                    # Task died — log the exception
                    try:
                        exc = existing.exception()
                    except (asyncio.CancelledError, asyncio.InvalidStateError):
                        exc = None
                    logger.error(f"[WATCHDOG] Task '{name}' died! Exception: {exc}. Restarting...")
                setattr(self, attr, asyncio.create_task(coro_fn()))
    
    async def _run_watchdog(self):
        """Monitor all tasks, resurrect any that died. Runs every 60 seconds."""
        while self._running:
            await asyncio.sleep(60)
            if self._running:
                self._start_all_tasks()
                
                # Check webhook health
                global _last_webhook_received_at
                if _last_webhook_received_at:
                    minutes_since = (datetime.utcnow() - _last_webhook_received_at).total_seconds() / 60
                    if minutes_since > 15:
                        if self._webhook_healthy:
                            logger.warning(f"[WATCHDOG] No webhooks received in {minutes_since:.0f}min — switching to fast polling")
                            self._webhook_healthy = False
                    else:
                        self._webhook_healthy = True
    
    # ===== Main CRM Sync Loop (30 min) =====
    
    async def _run_loop(self):
        """Full CRM sync loop."""
        while self._running:
            try:
                await self._run_sync()
                self._sync_count += 1
                self._last_sync = datetime.utcnow()
                self._mark_task_run("sync")
            except Exception as e:
                logger.error(f"CRM sync error: {e}")
            await asyncio.sleep(self.sync_interval)
    
    async def _run_sync(self):
        """Run a single sync cycle — scoped to enabled project campaigns."""
        logger.info(f"Starting scheduled CRM sync (run #{self._sync_count + 1})")
        sync_service = get_crm_sync_service()

        try:
            enabled_campaigns = await _get_campaign_names_by_status(True)
            logger.info(f"CRM sync scoped to {len(enabled_campaigns)} campaigns from enabled projects")
        except Exception as e:
            logger.warning(f"Failed to load enabled campaigns, running unscoped: {e}")
            enabled_campaigns = None
        
        async with async_session_maker() as session:
            try:
                results = await sync_service.full_sync(
                    session, self.company_id,
                    only_campaigns=enabled_campaigns,
                )
                
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
    
    # ===== Adaptive Reply Polling (3 min fast / 10 min steady) =====
    
    async def _run_reply_loop(self):
        """Adaptive reply polling — fast after startup, slow when webhooks are healthy."""
        await asyncio.sleep(30)
        fast_polls = 3
        poll_count = 0
        _auto_assign_counter = 0

        while self._running:
            _auto_assign_counter += 1
            if _auto_assign_counter % 6 == 1:
                try:
                    await self._auto_assign_new_campaigns()
                except Exception as e:
                    logger.error(f"Auto-assign campaigns error: {e}")
            try:
                await self._check_replies()
                self._reply_count += 1
                self._last_reply_check = datetime.utcnow()
                poll_count += 1
            except Exception as e:
                logger.error(f"Reply check error: {e}")
            
            # Adaptive interval
            if poll_count <= fast_polls:
                interval = 180  # 3 min: startup catch-up
            elif not self._webhook_healthy:
                interval = 180  # 3 min: webhooks seem broken, poll fast
            else:
                interval = 600  # 10 min: steady state, webhooks are working
            
            self._mark_task_run("reply_check", interval=interval)
            await asyncio.sleep(interval)
    
    async def _auto_assign_new_campaigns(self):
        """Auto-discover campaigns from SmartLead + GetSales, register in Campaign table, assign to projects."""
        from app.models.contact import Project
        from app.models.campaign import Campaign
        from app.services.crm_sync_service import match_campaign_to_project, refresh_getsales_flow_cache, refresh_project_prefixes
        from sqlalchemy import select, and_

        # ── Phase 1: Fetch campaigns from both platforms ──
        sl_campaigns = []
        gs_automations = []

        try:
            sl_campaigns = await self._get_campaigns_cached()
        except Exception as e:
            logger.warning(f"Failed to fetch SmartLead campaigns: {e}")

        try:
            from app.services.crm_sync_service import GetSalesClient
            import os
            gs_key = os.getenv("GETSALES_API_KEY")
            if gs_key:
                gs_client = GetSalesClient(gs_key)
                gs_automations = await gs_client.get_flows()
        except Exception as e:
            logger.warning(f"Failed to fetch GetSales automations: {e}")

        if not sl_campaigns and not gs_automations:
            return

        async with async_session_maker() as session:
            try:
                # ── Phase 2: Register/update all campaigns in Campaign table ──
                registered = 0

                # SmartLead campaigns
                for c in sl_campaigns:
                    c_name = c.get("name", "")
                    c_id = str(c.get("id", ""))
                    if not c_name or not c_id:
                        continue
                    c_tags = [t.get("name", "") for t in c.get("tags", []) if isinstance(t, dict)]
                    c_leads = c.get("total_lead_count", c.get("lead_count", 0)) or 0
                    existing = await session.execute(
                        select(Campaign).where(
                            and_(Campaign.platform == "smartlead", Campaign.external_id == c_id)
                        )
                    )
                    camp = existing.scalar()
                    if camp:
                        if camp.name != c_name:
                            camp.name = c_name
                        if c_tags:
                            camp.config = {**(camp.config or {}), "tags": c_tags}
                        if c_leads and camp.leads_count != c_leads:
                            camp.leads_count = c_leads
                    else:
                        matched_pid = match_campaign_to_project(c_name, c_tags)
                        camp = Campaign(
                            company_id=1, project_id=matched_pid,
                            platform="smartlead", channel="email",
                            external_id=c_id, name=c_name,
                            status=c.get("status", "active"),
                            leads_count=c_leads,
                            resolution_method="auto_discovery" if matched_pid else None,
                            resolution_detail=f"Auto-discovered from SmartLead" if matched_pid else None,
                            config={"tags": c_tags} if c_tags else None,
                        )
                        session.add(camp)
                        registered += 1

                # GetSales automations
                for a in gs_automations:
                    a_name = a.get("name", "")
                    a_uuid = a.get("uuid", "")
                    if not a_name or not a_uuid:
                        continue
                    existing = await session.execute(
                        select(Campaign).where(
                            and_(Campaign.platform == "getsales", Campaign.external_id == a_uuid)
                        )
                    )
                    camp = existing.scalar()
                    if camp:
                        if camp.name != a_name:
                            camp.name = a_name
                    else:
                        matched_pid = match_campaign_to_project(a_name)
                        camp = Campaign(
                            company_id=1, project_id=matched_pid,
                            platform="getsales", channel="linkedin",
                            external_id=a_uuid, name=a_name,
                            status=a.get("status", "active"),
                            resolution_method="auto_discovery" if matched_pid else None,
                            resolution_detail=f"Auto-discovered from GetSales" if matched_pid else None,
                        )
                        session.add(camp)
                        registered += 1

                if registered:
                    await session.flush()
                    logger.info(f"Registered {registered} new campaigns in Campaign table")

                # ── Phase 3: Assign unassigned campaigns to projects ──
                result = await session.execute(
                    select(Project).where(Project.deleted_at.is_(None))
                )
                projects = result.scalars().all()
                project_by_id = {p.id: p for p in projects}

                # Collect already-assigned campaign names across all projects
                assigned_names = set()
                for p in projects:
                    for name in (p.campaign_filters or []):
                        assigned_names.add(name.lower())

                # Find campaigns in Campaign table with project_id but not in campaign_filters
                assigned_in_table = await session.execute(
                    select(Campaign).where(Campaign.project_id.isnot(None))
                )
                for camp in assigned_in_table.scalars():
                    if camp.name.lower() not in assigned_names and camp.project_id in project_by_id:
                        project = project_by_id[camp.project_id]
                        filters = list(project.campaign_filters or [])
                        filters.append(camp.name)
                        project.campaign_filters = filters
                        assigned_names.add(camp.name.lower())

                # Try to assign unassigned campaigns via ownership rules
                unassigned_result = await session.execute(
                    select(Campaign).where(Campaign.project_id.is_(None))
                )
                assigned_count = 0
                for camp in unassigned_result.scalars():
                    c_tags = (camp.config or {}).get("tags", []) if camp.config else []
                    matched_pid = match_campaign_to_project(camp.name, c_tags)
                    if matched_pid and matched_pid in project_by_id:
                        camp.project_id = matched_pid
                        camp.resolution_method = "auto_discovery"
                        camp.resolution_detail = f"Auto-matched to project {project_by_id[matched_pid].name}"
                        # Append to campaign_filters
                        project = project_by_id[matched_pid]
                        if camp.name.lower() not in assigned_names:
                            filters = list(project.campaign_filters or [])
                            filters.append(camp.name)
                            project.campaign_filters = filters
                            assigned_names.add(camp.name.lower())
                        assigned_count += 1
                        # Audit log
                        from app.models.campaign_audit_log import CampaignAuditLog
                        session.add(CampaignAuditLog(
                            project_id=matched_pid, action="add", campaign_name=camp.name,
                            source="auto_discovery",
                            details=f"Auto-discovered and assigned by scheduler",
                        ))
                        logger.info(f"Auto-assigned '{camp.name}' to project '{project.name}'")

                if assigned_count > 0 or registered > 0:
                    await session.commit()
                    if assigned_count:
                        logger.info(f"Auto-assigned {assigned_count} campaigns to projects")
                    # Refresh caches after DB changes
                    try:
                        await refresh_getsales_flow_cache()
                        await refresh_project_prefixes()
                    except Exception as e:
                        logger.warning(f"Cache refresh after auto-assign failed: {e}")
                    # Trigger webhook setup for new campaigns
                    try:
                        await setup_crm_webhooks_on_startup()
                    except Exception as e:
                        logger.warning(f"Webhook setup after auto-assign failed: {e}")

            except Exception as e:
                await session.rollback()
                logger.error(f"Auto-assign campaigns failed: {e}", exc_info=True)
    
    async def _check_replies(self):
        """Check for new replies — scoped to enabled project campaigns only."""
        import time as _time
        logger.info(f"Checking replies via API (run #{self._reply_count + 1})")
        sync_service = get_crm_sync_service()

        try:
            enabled_campaigns = await _get_campaign_names_by_status(True)
        except Exception as e:
            logger.warning(f"Failed to load enabled campaigns, falling back to all: {e}")
            enabled_campaigns = None

        async with async_session_maker() as session:
            try:
                if sync_service.smartlead:
                    t0 = _time.monotonic()
                    results = await sync_service.sync_smartlead_replies(
                        session, self.company_id,
                        only_campaigns=enabled_campaigns,
                    )
                    sl_ms = int((_time.monotonic() - t0) * 1000)
                    new_replies = results.get('new_replies', 0)
                    campaigns_checked = results.get('campaigns_checked', 0)
                    logger.info(f"SmartLead poll: {sl_ms}ms, {new_replies} new, {campaigns_checked} campaigns")
            except Exception as e:
                logger.error(f"Smartlead reply check failed: {e}")

            try:
                if sync_service.getsales:
                    t0 = _time.monotonic()
                    results = await sync_service.sync_getsales_replies(session, self.company_id)
                    gs_ms = int((_time.monotonic() - t0) * 1000)
                    new_replies = results.get('new_replies', 0)
                    logger.info(f"GetSales poll: {gs_ms}ms, {new_replies} new")
            except Exception as e:
                logger.error(f"GetSales reply check failed: {e}")
    
    # ===== Webhook Registration (5 min, 1 min on failure) =====
    
    async def _run_webhook_loop(self):
        """Webhook registration — hourly safety net.

        Webhooks are also set up on startup and after auto-assign.
        The hourly loop only catches campaigns that appeared between
        auto-assign runs (rare). Previously ran every 5 min, which
        was 288 unnecessary SmartLead API round-trips per day.
        """
        await asyncio.sleep(10)
        interval = 3600

        while self._running:
            try:
                await setup_crm_webhooks_on_startup()
                self._last_webhook_check = datetime.utcnow()
                self._mark_task_run("webhook_setup", interval=interval)
            except Exception as e:
                logger.error(f"Webhook setup error: {e}")
                interval = 300
                self._mark_task_run("webhook_setup", interval=interval)
            await asyncio.sleep(interval)
            interval = 3600

    # ===== Event Recovery Loop (every 5 min) =====
    
    async def _run_event_recovery_loop(self):
        """Recover failed/unprocessed webhook events. Runs every 5 minutes."""
        await asyncio.sleep(120)  # Wait 2 min for initial batch to settle
        while self._running:
            try:
                await self._recover_events()
                self._mark_task_run("event_recovery")
            except Exception as e:
                logger.error(f"Event recovery error: {e}")
            await asyncio.sleep(300)
    
    async def _recover_events(self):
        """Find and reprocess failed webhook events with exponential backoff."""
        from app.models.reply import WebhookEventModel
        from app.services.reply_processor import process_reply_webhook
        from sqlalchemy import select, or_
        
        cutoff = datetime.utcnow() - timedelta(hours=24)
        now = datetime.utcnow()
        
        async with async_session_maker() as session:
            # Find unprocessed reply events ready for retry
            events_query = await session.execute(
                select(WebhookEventModel).where(
                    WebhookEventModel.processed == False,
                    WebhookEventModel.created_at >= cutoff,
                    WebhookEventModel.event_type.in_(["EMAIL_REPLY", "lead.replied", "email.replied", "reply"]),
                    or_(
                        WebhookEventModel.retry_count.is_(None),
                        WebhookEventModel.retry_count < 5
                    ),
                    or_(
                        WebhookEventModel.next_retry_at.is_(None),
                        WebhookEventModel.next_retry_at <= now
                    )
                ).order_by(WebhookEventModel.created_at.asc()).limit(20)
            )
            events_to_retry = events_query.scalars().all()
            
            if not events_to_retry:
                return
            
            logger.info(f"[RECOVERY] Found {len(events_to_retry)} events to retry")
            
            for event in events_to_retry:
                try:
                    payload = json.loads(event.payload)
                    
                    # Process with a fresh session
                    async with async_session_maker() as proc_session:
                        result = await process_reply_webhook(payload, proc_session)
                        await proc_session.commit()
                    
                    event.processed = True
                    event.processed_at = datetime.utcnow()
                    event.error = None
                    logger.info(f"[RECOVERY] Successfully reprocessed event {event.id}")
                    
                except Exception as e:
                    retry_count = (event.retry_count or 0) + 1
                    event.error = str(e)[:500]
                    event.retry_count = retry_count
                    # Exponential backoff: 5min, 15min, 45min, 2h, 6h (capped)
                    backoff_minutes = min(5 * (3 ** (retry_count - 1)), 360)
                    event.next_retry_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
                    logger.warning(f"[RECOVERY] Event {event.id} failed (retry {retry_count}, next in {backoff_minutes}min): {e}")
            
            await session.commit()
    
    # ===== Conversation History Sync (every 3 min) =====

    async def _run_conversation_sync_loop(self):
        """Sync Smartlead message histories to detect operator replies.

        Checks pending replies for outbound messages in Smartlead's thread API.
        Marks replied-to conversations as 'replied_externally' and creates
        missing outbound ContactActivity records.
        Runs every 3 minutes, processing up to 100 leads per run.
        """
        await asyncio.sleep(60)  # Wait 1 min after startup for other syncs to settle
        interval = 180  # 3 minutes

        while self._running:
            try:
                from app.services.crm_sync_service import sync_conversation_histories

                async with async_session_maker() as session:
                    stats = await sync_conversation_histories(session, limit=100)
                    if stats.get("checked", 0) > 0:
                        logger.info(
                            f"Conversation sync: checked={stats['checked']} "
                            f"replied_externally={stats['replied_externally']} "
                            f"still_pending={stats['still_pending']} "
                            f"activities_created={stats['activities_created']} "
                            f"errors={stats['errors']}"
                        )
                self._mark_task_run("conversation_sync")
            except Exception as e:
                logger.error(f"Conversation sync error: {e}")
            await asyncio.sleep(interval)

    # ===== Daily Needs-Reply Cleanup (once per day) =====

    async def _run_needs_reply_cleanup_loop(self):
        """Deep cleanup: load pending reply threads, auto-resolve where operator replied.

        Runs every 6 hours, processing 200 replies per batch. Processes the full
        backlog over multiple cycles, then maintains cleanliness.
        """
        await asyncio.sleep(300)  # Wait 5 min after startup

        interval = 21600  # 6 hours

        while self._running:
            try:
                from app.services.crm_sync_service import deep_cleanup_needs_reply

                async with async_session_maker() as session:
                    stats = await deep_cleanup_needs_reply(session)
                    logger.info(
                        f"[CLEANUP] Daily cleanup: checked={stats['checked']} "
                        f"resolved={stats['resolved']} errors={stats['errors']}"
                    )
                self._mark_task_run("needs_reply_cleanup")
            except Exception as e:
                logger.error(f"Needs-reply cleanup error: {e}")
            await asyncio.sleep(interval)

    # ===== Telegram Bot Polling (long-poll every 30s) =====

    async def _run_telegram_poll_loop(self):
        """Poll Telegram getUpdates for /start and /status commands.

        Since we don't have HTTPS for webhook, we use long-polling instead.
        Processes updates through the same logic as the webhook endpoint.
        """
        import os
        import httpx

        bot_token = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram polling disabled")
            return

        # First, delete any existing webhook so getUpdates works
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook")
        except Exception:
            pass

        offset = 0
        logger.info("Telegram poll loop started")

        while self._running:
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{bot_token}/getUpdates",
                        params={"offset": offset, "timeout": 30, "allowed_updates": '["message"]'},
                    )
                    data = resp.json()

                if not data.get("ok"):
                    logger.warning(f"Telegram getUpdates error: {data}")
                    await asyncio.sleep(5)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    try:
                        await self._handle_telegram_update(update)
                    except Exception as e:
                        logger.error(f"Telegram update handling error: {e}")

            except httpx.ReadTimeout:
                # Normal — long poll timed out with no updates
                pass
            except Exception as e:
                logger.error(f"Telegram poll error: {e}")
                await asyncio.sleep(5)

    async def _handle_telegram_update(self, update: dict):
        """Process a single Telegram update (message).

        Supports deep links: /start project_22 -> auto-links chat to project 22.
        Plain /start -> registers username for manual linking.
        /status -> shows linked projects.
        """
        from app.models.reply import TelegramRegistration
        from app.models.contact import Project
        from app.services.notification_service import send_telegram_notification
        from sqlalchemy import select, and_

        message = update.get("message", {})
        if not message:
            return

        chat = message.get("chat", {})
        from_user = message.get("from", {})
        text = (message.get("text") or "").strip()
        chat_id = str(chat.get("id", ""))
        username = (from_user.get("username") or "").lower().strip()
        first_name = from_user.get("first_name", "")

        if not chat_id or not text.startswith("/"):
            return

        async with async_session_maker() as session:
            if text.startswith("/start"):
                # Parse deep link payload: /start project_22
                parts = text.split(maxsplit=1)
                payload = parts[1].strip() if len(parts) > 1 else ""

                # Deep link: /start project_<id>
                if payload.startswith("project_"):
                    try:
                        project_id = int(payload.replace("project_", ""))
                    except ValueError:
                        await send_telegram_notification(
                            "Invalid project link.", chat_id=chat_id,
                        )
                        return

                    result = await session.execute(
                        select(Project).where(
                            and_(Project.id == project_id, Project.deleted_at.is_(None))
                        )
                    )
                    project = result.scalar_one_or_none()

                    if not project:
                        await send_telegram_notification(
                            "Project not found.", chat_id=chat_id,
                        )
                        return

                    # Upsert into telegram_subscriptions
                    from app.models.reply import TelegramSubscription
                    existing_sub = await session.execute(
                        select(TelegramSubscription).where(
                            and_(
                                TelegramSubscription.project_id == project_id,
                                TelegramSubscription.chat_id == chat_id,
                            )
                        )
                    )
                    sub = existing_sub.scalar_one_or_none()
                    if sub:
                        sub.first_name = first_name
                        if username:
                            sub.username = username
                    else:
                        session.add(TelegramSubscription(
                            project_id=project_id,
                            chat_id=chat_id,
                            username=username or None,
                            first_name=first_name or None,
                        ))

                    # Keep legacy field in sync for backward compat
                    project.telegram_chat_id = chat_id
                    project.telegram_first_name = first_name
                    if username:
                        project.telegram_username = username
                    await session.commit()

                    await send_telegram_notification(
                        f"Connected to <b>{project.name}</b>!\n\n"
                        f"You'll receive reply notifications for this project.",
                        chat_id=chat_id,
                    )
                    logger.info(
                        f"Telegram subscription: project {project_id} ({project.name}) "
                        f"-> chat_id={chat_id} ({first_name})"
                    )
                    return

                # Plain /start (no deep link) — register username for backward compat
                if username:
                    existing = await session.execute(
                        select(TelegramRegistration).where(
                            TelegramRegistration.telegram_username == username
                        )
                    )
                    reg = existing.scalar_one_or_none()
                    if reg:
                        reg.telegram_chat_id = chat_id
                        reg.telegram_first_name = first_name
                        from datetime import datetime as dt
                        reg.updated_at = dt.utcnow()
                    else:
                        reg = TelegramRegistration(
                            telegram_username=username,
                            telegram_chat_id=chat_id,
                            telegram_first_name=first_name,
                        )
                        session.add(reg)
                    await session.commit()

                await send_telegram_notification(
                    f"Hi {first_name}! To connect to a project, "
                    f"use the <b>Connect Telegram</b> button in the app.",
                    chat_id=chat_id,
                )

            elif text.startswith("/status"):
                from app.models.reply import TelegramSubscription
                subs_result = await session.execute(
                    select(TelegramSubscription, Project.name).join(
                        Project, TelegramSubscription.project_id == Project.id
                    ).where(
                        and_(
                            TelegramSubscription.chat_id == chat_id,
                            Project.deleted_at.is_(None),
                        )
                    )
                )
                subs = subs_result.all()

                if subs:
                    project_list = "\n".join(f"  - {name}" for _, name in subs)
                    await send_telegram_notification(
                        f"Receiving reply notifications for:\n{project_list}",
                        chat_id=chat_id,
                    )
                else:
                    await send_telegram_notification(
                        "No projects linked. Use the <b>Connect Telegram</b> button in the app.",
                        chat_id=chat_id,
                    )

    # ===== Google Sheet Sync (every 5 min) =====

    async def _run_sheet_sync_loop(self):
        """Sync project data to/from Google Sheets.

        Every 5 min: push replies + leads.
        Every 3rd cycle (15 min): poll qualification from sheet.
        Controlled by per-project `sheet_sync_config.enabled` toggle.
        Global kill switch: SHEET_SYNC_DISABLED=1 env var.
        """
        if os.getenv("SHEET_SYNC_DISABLED", "").strip() in ("1", "true", "yes"):
            logger.info("[SheetSync] Globally disabled via SHEET_SYNC_DISABLED env var")
            return

        await asyncio.sleep(90)
        cycle = 0

        while self._running:
            cycle += 1
            try:
                await self._run_sheet_sync(poll_qualification=(cycle % 3 == 0))
                self._mark_task_run("sheet_sync")
            except Exception as e:
                logger.error(f"Sheet sync error: {e}")
            await asyncio.sleep(300)

    async def _run_sheet_sync(self, poll_qualification: bool = False):
        """Run sheet sync for all projects with enabled sheet_sync_config."""
        from app.models.contact import Project
        from app.services.sheet_sync_service import sheet_sync_service

        async with async_session_maker() as session:
            result = await session.execute(
                select(Project).where(
                    Project.deleted_at.is_(None),
                    Project.sheet_sync_config.isnot(None),
                )
            )
            projects = result.scalars().all()

        for project in projects:
            config = project.sheet_sync_config
            if not isinstance(config, dict) or not config.get("enabled"):
                continue

            project_id = project.id
            try:
                # Push replies
                reply_stats = await sheet_sync_service.sync_replies_to_sheet(project_id)
                if reply_stats.get("rows_appended"):
                    logger.info(f"[SheetSync] Project {project_id}: {reply_stats['rows_appended']} replies appended")

                # Push/update leads
                lead_stats = await sheet_sync_service.push_leads_to_sheet(project_id)
                if lead_stats.get("new_rows") or lead_stats.get("updated_rows"):
                    logger.info(
                        f"[SheetSync] Project {project_id}: "
                        f"{lead_stats['new_rows']} new leads, "
                        f"{lead_stats['updated_rows']} updated"
                    )

                # Poll qualification (every 3rd cycle)
                if poll_qualification:
                    qual_stats = await sheet_sync_service.poll_qualification_from_sheet(project_id)
                    if qual_stats.get("contacts_updated"):
                        logger.info(
                            f"[SheetSync] Project {project_id}: "
                            f"{qual_stats['contacts_updated']} contacts updated from sheet, "
                            f"{qual_stats['qualifications_changed']} qualifications, "
                            f"{qual_stats['statuses_advanced']} statuses advanced"
                        )

                # Clear previous error on success
                async with async_session_maker() as ok_session:
                    proj = await ok_session.get(Project, project_id)
                    if proj and proj.sheet_sync_config and proj.sheet_sync_config.get("last_error"):
                        new_config = dict(proj.sheet_sync_config)
                        new_config.pop("last_error", None)
                        new_config.pop("last_error_at", None)
                        proj.sheet_sync_config = new_config
                        await ok_session.commit()

            except Exception as e:
                import traceback
                logger.error(f"[SheetSync] Project {project_id} failed: {e}\n{traceback.format_exc()}")
                # Store error in config
                try:
                    async with async_session_maker() as err_session:
                        proj = await err_session.get(Project, project_id)
                        if proj and proj.sheet_sync_config:
                            new_config = dict(proj.sheet_sync_config)
                            new_config["last_error"] = str(e)[:500]
                            new_config["last_error_at"] = datetime.utcnow().isoformat()
                            proj.sheet_sync_config = new_config
                            await err_session.commit()
                except Exception:
                    pass

    # ===== Reports (every 4 hours, per-project) =====
    
    async def _run_report_loop(self):
        """Send Telegram report every 4 hours with reply summary."""
        await asyncio.sleep(300)  # Initial delay 5 min
        while self._running:
            try:
                await self._send_reply_report()
                self._mark_task_run("report")
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
            await asyncio.sleep(self.report_interval)
    
    async def _send_reply_report(self):
        """Generate and send per-project + admin Telegram reports."""
        from app.models.reply import ProcessedReply
        from app.models.contact import Contact, ContactActivity, Project
        from app.services.notification_service import send_telegram_notification, TELEGRAM_CHAT_ID
        from sqlalchemy import select, func, and_
        
        since = datetime.utcnow() - timedelta(hours=24)
        
        async with async_session_maker() as session:
            # Get all replies data
            smartlead_warm_query = await session.execute(
                select(ProcessedReply).where(
                    and_(
                        ProcessedReply.received_at >= since,
                        ProcessedReply.category.in_(["interested", "meeting_request", "question"])
                    )
                ).order_by(ProcessedReply.campaign_name, ProcessedReply.received_at.desc())
            )
            smartlead_warm = smartlead_warm_query.scalars().all()
            
            smartlead_negative_query = await session.execute(
                select(func.count(ProcessedReply.id)).where(
                    and_(
                        ProcessedReply.received_at >= since,
                        ProcessedReply.category.in_(["not_interested", "unsubscribe", "wrong_person"])
                    )
                )
            )
            negative_total = smartlead_negative_query.scalar() or 0
            
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
            
            # 24h summary goes ONLY to admin (@impecableme).
            # Operators get real-time per-reply notifications — they don't need
            # periodic digests that duplicate what they already see instantly.
            message = self._build_report_message(
                smartlead_warm, negative_total, getsales_replies, title="All Projects"
            )
            await send_telegram_notification(message, chat_id=TELEGRAM_CHAT_ID)
            
            warm_email = len(smartlead_warm)
            warm_linkedin = len(getsales_replies)
            logger.info(f"Sent reply reports: {warm_email} email warm, {warm_linkedin} LinkedIn, {negative_total} negative")
    
    def _build_report_message(self, smartlead_warm, negative_total, getsales_replies, title="All Projects"):
        """Build a Telegram report message from reply data."""
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
        
        linkedin_by_flow = {}
        seen_linkedin_contacts = set()
        for activity, contact in getsales_replies:
            flow_name = get_getsales_flow_name(activity.extra_data, contact.get_platform("getsales").get("campaigns", []))
            contact_key = (flow_name, contact.id)
            if contact_key in seen_linkedin_contacts:
                continue
            seen_linkedin_contacts.add(contact_key)
            if flow_name not in linkedin_by_flow:
                linkedin_by_flow[flow_name] = []
            name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email
            linkedin_by_flow[flow_name].append(name)
        
        warm_email = len(seen_email_contacts)
        warm_linkedin = len(seen_linkedin_contacts)
        warm_total = warm_email + warm_linkedin
        
        lines = []
        lines.append(f"<b>📊 Replies Report</b> <i>(Last 24h — {title})</i>")
        lines.append("")
        lines.append(f"<b>🔥 WARM LEADS ({warm_total})</b>")
        
        if email_by_campaign:
            lines.append("")
            lines.append(f"<b>📧 Email ({warm_email}):</b>")
            for campaign, leads in sorted(email_by_campaign.items(), key=lambda x: -len(x[1]))[:8]:
                lines.append(f"<code>{campaign[:35]}</code> ({len(leads)})")
                for lead in leads[:5]:
                    lines.append(f"  └ {lead[:25]}")
                if len(leads) > 5:
                    lines.append(f"  └ <i>+{len(leads)-5} more...</i>")
        
        if linkedin_by_flow:
            lines.append("")
            lines.append(f"<b>💼 LinkedIn ({warm_linkedin}):</b>")
            for flow, leads in sorted(linkedin_by_flow.items(), key=lambda x: -len(x[1]))[:8]:
                lines.append(f"<code>{flow[:35]}</code> ({len(leads)})")
                for lead in leads[:5]:
                    lines.append(f"  └ {lead[:25]}")
                if len(leads) > 5:
                    lines.append(f"  └ <i>+{len(leads)-5} more...</i>")
        
        if negative_total:
            lines.append("")
            lines.append(f"<b>❌ Not Interested:</b> {negative_total}")
        
        lines.append("")
        lines.append(f"<b>📈 Total: {warm_total + negative_total}</b>")
        
        return "\n".join(lines)
    
    # ===== Prompt Refresh (weekly) =====
    
    async def _run_prompt_refresh_loop(self):
        """Prompt refresh loop — runs weekly to regenerate project reply prompts."""
        await asyncio.sleep(3600)  # Initial delay (1 hour)
        while self._running:
            try:
                await self._refresh_project_prompts()
                self._last_prompt_refresh = datetime.utcnow()
                self._mark_task_run("prompt_refresh")
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
                        Project.webhooks_enabled == True,
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
                await session.rollback()
                logger.error(f"Prompt refresh failed: {e}")
                raise
    
    # ===== Status & Manual Triggers =====
    
    async def run_now(self):
        """Trigger an immediate sync outside the schedule."""
        logger.info("Manual CRM sync triggered")
        await self._run_sync()
        self._last_sync = datetime.utcnow()
    
    def get_status(self) -> dict:
        """Get scheduler status including health info."""
        # Check which tasks are alive
        task_health = {}
        for attr, name in [
            ("_task", "sync"), ("_reply_task", "reply_check"),
            ("_webhook_task", "webhook_setup"), ("_report_task", "report"),
            ("_recovery_task", "event_recovery"), ("_prompt_refresh_task", "prompt_refresh"),
            ("_sheet_sync_task", "sheet_sync"),
        ]:
            task = getattr(self, attr, None)
            if task is None:
                task_health[name] = "not_started"
            elif task.done():
                task_health[name] = "dead"
            else:
                task_health[name] = "running"
        
        # Build task_timing with next_run estimates (all UTC with Z suffix)
        task_timing_out = {}
        for key, t in self._task_timing.items():
            last = t["last_run"]
            interval = t["interval"]
            task_timing_out[key] = {
                "label": t["label"],
                "last_run": last.isoformat() + "Z" if last else None,
                "interval_seconds": interval,
                "next_run": (last + timedelta(seconds=interval)).isoformat() + "Z" if last else None,
            }

        return {
            "running": self._running,
            "webhook_healthy": self._webhook_healthy,
            "task_health": task_health,
            "task_timing": task_timing_out,
            "sync_interval_minutes": self.sync_interval // 60,
            "company_id": self.company_id,
            "last_sync": self._last_sync.isoformat() + "Z" if self._last_sync else None,
            "last_reply_check": self._last_reply_check.isoformat() + "Z" if self._last_reply_check else None,
            "last_webhook_check": self._last_webhook_check.isoformat() + "Z" if self._last_webhook_check else None,
            "last_prompt_refresh": self._last_prompt_refresh.isoformat() + "Z" if self._last_prompt_refresh else None,
            "last_webhook_received": _last_webhook_received_at.isoformat() + "Z" if _last_webhook_received_at else None,
            "sync_count": self._sync_count,
            "reply_check_count": self._reply_count
        }


# ===== Global scheduler instance =====

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
    


# Prevents concurrent webhook registration runs.
_webhook_setup_lock = asyncio.Lock()


async def setup_crm_webhooks_on_startup():
    """Set up CRM webhooks in external systems.

    Single entry point for ALL webhook registration. Protected by an
    asyncio.Lock so concurrent callers (startup background task, periodic
    5-min loop, post-auto-assign trigger) never race each other.
    """
    if _webhook_setup_lock.locked():
        logger.info("Webhook setup already running, skipping")
        return

    async with _webhook_setup_lock:
        await _do_webhook_setup()


async def _do_webhook_setup():
    """Internal: actual webhook registration logic."""
    from app.services.crm_sync_service import get_crm_sync_service

    logger.info("Setting up CRM webhooks for all campaigns (background)...")

    webhook_base_url = f"{settings.WEBHOOK_BASE_URL}/api"
    token_suffix = f"?token={settings.WEBHOOK_SECRET}" if settings.WEBHOOK_SECRET else ""

    sync_service = get_crm_sync_service()

    try:
        skip_campaigns = await _get_campaign_names_by_status(False)
        if skip_campaigns:
            logger.info(f"Skipping webhooks for {len(skip_campaigns)} campaigns (disabled projects)")
    except Exception as e:
        logger.warning(f"Failed to load disabled campaigns: {e}")
        skip_campaigns = set()

    if sync_service.getsales:
        try:
            getsales_url = f"{webhook_base_url}/crm-sync/webhook/getsales{token_suffix}"
            results = await sync_service.getsales.setup_crm_webhooks(getsales_url)
            logger.info(f"GetSales webhooks: {len(results.get('created', []))} created, {len(results.get('existing', []))} existing")
        except Exception as e:
            logger.warning(f"Failed to set up GetSales webhooks: {e}")

    if sync_service.smartlead:
        try:
            smartlead_url = f"{webhook_base_url}/smartlead/webhook{token_suffix}"
            results = await sync_service.smartlead.setup_crm_webhooks(smartlead_url, skip_campaigns=skip_campaigns)
            created = len(results.get('created', []))
            existing = len(results.get('existing', []))
            skipped = len(results.get('skipped', []))
            failed = len(results.get('failed', []))
            active_count = created + existing

            logger.info(f"Smartlead webhook setup: {active_count} active, {created} new, {existing} existing, {skipped} skipped")
            if failed > 0:
                logger.warning(f"  Failed: {failed}")
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
