"""
CRM Sync Scheduler - Background job for periodic sync.

Runs CRM sync at configurable intervals.
"""
import asyncio
import logging
from datetime import datetime
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
        company_id: int = 1
    ):
        self.sync_interval = sync_interval_minutes * 60  # Convert to seconds
        self.company_id = company_id
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_sync: Optional[datetime] = None
        self._sync_count = 0
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("CRM scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"CRM scheduler started (interval: {self.sync_interval // 60} minutes)")
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
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
            
            # Wait for next interval
            await asyncio.sleep(self.sync_interval)
    
    async def _run_sync(self):
        """Run a single sync cycle."""
        logger.info(f"Starting scheduled CRM sync (run #{self._sync_count + 1})")
        
        sync_service = get_crm_sync_service()
        
        async with async_session_maker() as session:
            try:
                results = await sync_service.full_sync(session, self.company_id)
                
                # Log results
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
            "company_id": self.company_id,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "sync_count": self._sync_count
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
    """Set up CRM webhooks in external systems on startup."""
    from app.services.crm_sync_service import get_crm_sync_service
    
    logger.info("Setting up CRM webhooks...")
    
    # Default webhook base URL - update this to your actual backend URL
    webhook_base_url = "http://46.62.210.24:8000/api/crm-sync/webhook"
    
    sync_service = get_crm_sync_service()
    
    # Set up GetSales webhooks
    if sync_service.getsales:
        try:
            getsales_url = f"{webhook_base_url}/getsales"
            results = await sync_service.getsales.setup_crm_webhooks(getsales_url)
            logger.info(f"GetSales webhooks: {len(results.get('created', []))} created, {len(results.get('existing', []))} existing")
        except Exception as e:
            logger.warning(f"Failed to set up GetSales webhooks: {e}")
    
    # Set up Smartlead webhooks
    if sync_service.smartlead:
        try:
            smartlead_url = f"{webhook_base_url}/smartlead"
            results = await sync_service.smartlead.setup_crm_webhooks(smartlead_url)
            created = len(results.get('created', []))
            existing = len(results.get('existing', []))
            skipped = len(results.get('skipped', []))
            logger.info(f"Smartlead webhooks: {created} created, {existing} existing, {skipped} skipped (inactive campaigns)")
        except Exception as e:
            logger.warning(f"Failed to set up Smartlead webhooks: {e}")


async def stop_crm_scheduler():
    """Stop the CRM scheduler."""
    global _crm_scheduler
    if _crm_scheduler:
        await _crm_scheduler.stop()
        _crm_scheduler = None
