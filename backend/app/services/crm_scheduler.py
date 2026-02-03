"""
CRM Sync Scheduler - Background job for periodic sync.

Runs CRM sync at configurable intervals with:
- Full sync every 30 minutes
- Reply check via API every 15 minutes (backup to webhooks)
- Webhook setup check every 6 hours (for new campaigns)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db import async_session_maker
from app.services.crm_sync_service import get_crm_sync_service

logger = logging.getLogger(__name__)


class CRMScheduler:
    """
    Background scheduler for CRM sync jobs.
    
    Runs periodic sync from Smartlead and GetSales.
    """
    
    def __init__(
        self,
        sync_interval_minutes: int = 30,
        reply_check_interval_minutes: int = 15,
        webhook_check_interval_hours: int = 6,
        company_id: int = 1
    ):
        self.sync_interval = sync_interval_minutes * 60
        self.reply_check_interval = reply_check_interval_minutes * 60
        self.webhook_check_interval = webhook_check_interval_hours * 3600
        self.company_id = company_id
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reply_task: Optional[asyncio.Task] = None
        self._webhook_task: Optional[asyncio.Task] = None
        self._last_sync: Optional[datetime] = None
        self._last_reply_check: Optional[datetime] = None
        self._last_webhook_check: Optional[datetime] = None
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
        logger.info(f"CRM scheduler started (sync: {self.sync_interval // 60}min, replies: {self.reply_check_interval // 60}min, webhooks: {self.webhook_check_interval // 3600}h)")
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for task in [self._task, self._reply_task, self._webhook_task]:
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
        """Reply check loop - runs every 15 minutes to catch replies via API."""
        await asyncio.sleep(60)  # Initial delay
        while self._running:
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
    
    async def _check_replies(self):
        """Check for new replies via API polling (backup to webhooks)."""
        logger.info(f"Checking replies via API (run #{self._reply_count + 1})")
        sync_service = get_crm_sync_service()
        
        async with async_session_maker() as session:
            try:
                if sync_service.smartlead:
                    results = await sync_service.sync_smartlead_replies(session, self.company_id)
                    new_replies = results.get('new_replies', 0)
                    if new_replies > 0:
                        logger.info(f"Smartlead reply check: {new_replies} new replies found")
            except Exception as e:
                logger.error(f"Reply check failed: {e}")
    
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
