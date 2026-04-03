import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.api import api_router
from app.db import init_db, close_db, async_session_maker
from app.api.templates import ensure_default_templates
from app.services.cache_service import init_cache, close_cache, cache_service
from app.core.config import settings
import logging

# Import all models to register them with Base before init_db()
from app.models import user  # noqa
from app.models import dataset  # noqa
from app.models import knowledge_base  # noqa
from app.models import prospect  # noqa
from app.models import reply  # noqa
from app.models import User, Company

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def ensure_default_user(session):
    """Create default user if none exists"""
    result = await session.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.info("Creating default user...")
        default_user = User(
            name="Default User",
            email="user@leadgen.local",
            is_active=True
        )
        session.add(default_user)
        await session.flush()
        logger.info(f"Default user created with ID: {default_user.id}")
        return default_user
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting LeadGen Automation API...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis cache
    if await init_cache():
        logger.info("Redis cache initialized")
    else:
        logger.warning("Redis cache not available - running without cache")
    
    # Create default user and templates, load integration keys
    async with async_session_maker() as session:
        await ensure_default_user(session)
        await ensure_default_templates(session)
        await session.commit()

    # Load integration API keys (SmartLead, Instantly, etc.) from DB into services
    async with async_session_maker() as session:
        from app.api.integrations import load_integration_keys
        await load_integration_keys(session)
        logger.info("Integration keys loaded from database")

    # Note: last_touched_at column on processed_replies is created by init_db's create_all.
    # For existing databases, run manually:
    #   ALTER TABLE processed_replies ADD COLUMN IF NOT EXISTS last_touched_at TIMESTAMP;
    #   UPDATE processed_replies SET last_touched_at = received_at WHERE last_touched_at IS NULL;
    
    # Setup automatic file synchronization
    from app.services.sync_service import setup_default_syncs
    try:
        await setup_default_syncs()
        logger.info("File synchronization enabled")
    except Exception as e:
        logger.warning(f"Failed to setup file sync: {e}")
    
    # Initialize campaign routing caches from DB (must run before scheduler)
    try:
        from app.services.crm_sync_service import refresh_getsales_flow_cache, refresh_project_prefixes
        await refresh_getsales_flow_cache()
        await refresh_project_prefixes()
        logger.info("Campaign routing caches initialized")
    except Exception as e:
        logger.warning(f"Campaign cache init failed (will retry on first sync): {e}")

    # Start CRM sync scheduler (optional - comment out to disable)
    # Note: webhook registration is handled by the scheduler's startup routine
    # (setup_crm_webhooks_on_startup) which covers ALL active campaigns.
    try:
        from app.services.crm_scheduler import start_crm_scheduler
        await start_crm_scheduler()
        logger.info("CRM sync scheduler started")
    except Exception as e:
        logger.warning(f"CRM scheduler start failed: {e}")

    # Start Telegram DM inbox in background (reconnect can be slow if proxies are down)
    async def _start_telegram_dm():
        try:
            from app.services.telegram_dm_service import telegram_dm_service
            await telegram_dm_service.reconnect_all()
            await telegram_dm_service.start_listening()
            logger.info("Telegram DM service started (with real-time listeners)")
        except Exception as e:
            logger.warning(f"Telegram DM service start failed: {e}")
    asyncio.create_task(_start_telegram_dm())

    # Start Sally bot (Telegram client chat monitor)
    sally_task = None
    try:
        from app.services.sally_bot_service import sally_bot_service
        if settings.TELEGRAM_SALLY_BOT_TOKEN:
            sally_task = asyncio.create_task(sally_bot_service.poll_loop())
            logger.info("Sally bot started")
    except Exception as e:
        logger.warning(f"Sally bot start failed: {e}")


    # Start Telegram Outreach workers (sending + reply detection + warm-up)
    try:
        from app.services.sending_worker import sending_worker
        from app.services.reply_detector import reply_detector
        from app.services.auto_responder import auto_responder
        from app.services.warmup_worker import warmup_worker
        sending_worker.start()
        reply_detector.start()
        auto_responder.start()
        warmup_worker.start()
        logger.info("Telegram Outreach workers started (sending + reply detection + auto-reply + warm-up)")
    except Exception as e:
        logger.warning(f"Telegram Outreach worker start failed: {e}")

    # Fetch latest TG Desktop version (for anti-ban fingerprint freshness)
    tdesktop_task = None
    try:
        from app.api.telegram_outreach import fetch_latest_tdesktop_version

        async def _tdesktop_version_loop():
            """Refresh latest TG Desktop version every 24h."""
            while True:
                await fetch_latest_tdesktop_version()
                await asyncio.sleep(86400)  # 24h

        tdesktop_task = asyncio.create_task(_tdesktop_version_loop())
        logger.info("TG Desktop version auto-updater started")
    except Exception as e:
        logger.warning(f"TG Desktop version fetch failed: {e}")

    yield

    if tdesktop_task:
        tdesktop_task.cancel()
    
    # Shutdown
    logger.info("Shutting down...")

    # Stop Sally bot
    try:
        from app.services.sally_bot_service import sally_bot_service
        sally_bot_service.stop()
        if sally_task:
            sally_task.cancel()
        logger.info("Sally bot stopped")
    except Exception as e:
        logger.warning(f"Sally bot stop failed: {e}")

    # Stop warmup worker
    try:
        from app.services.warmup_worker import warmup_worker
        warmup_worker.stop()
        logger.info("WarmupWorker stopped")
    except Exception as e:
        logger.warning(f"WarmupWorker stop failed: {e}")

    # Stop CRM scheduler
    try:
        from app.services.crm_scheduler import stop_crm_scheduler
        await stop_crm_scheduler()
        logger.info("CRM scheduler stopped")
    except Exception as e:
        logger.warning(f"CRM scheduler stop failed: {e}")
    
    # Stop file sync
    from app.services import sync_service
    sync_service.stop_watching()
    logger.info("File synchronization stopped")
    
    # Close cache
    await close_cache()
    logger.info("Cache closed")
    
    # Close database connections
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.APP_NAME,
    description="Lead Generation Automation Platform - Enrich your leads with AI",
    version="1.0.0",
    lifespan=lifespan,
)

# Request timing middleware — logs slow requests (>1s)
import time as _time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _StarletteRequest

class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: _StarletteRequest, call_next):
        start = _time.monotonic()
        response = await call_next(request)
        elapsed = _time.monotonic() - start
        path = request.url.path
        qs = str(request.url.query)
        if elapsed > 1.0 and "/health" not in path:
            logger.warning(f"[SLOW] {request.method} {path}?{qs} — {elapsed:.1f}s")
        elif "/health" not in path:
            logger.info(f"[REQ] {request.method} {path}?{qs} — {elapsed:.1f}s")
        return response

app.add_middleware(RequestTimingMiddleware)

# CORS middleware - origins from config
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint — used by Docker healthcheck.
    
    Returns 200 if DB is reachable (minimum requirement).
    Returns 503 if DB is down (triggers Docker restart).
    Also reports Redis, scheduler, and webhook health status.
    """
    from fastapi.responses import JSONResponse
    
    checks = {
        "db": False,
        "redis": cache_service.is_connected if cache_service else False,
        "scheduler": False,
        "webhook_healthy": True,
    }
    
    # Quick DB check
    try:
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            checks["db"] = True
    except Exception:
        pass
    
    # Scheduler status
    try:
        from app.services.crm_scheduler import get_crm_scheduler
        scheduler = get_crm_scheduler()
        checks["scheduler"] = scheduler._running if scheduler else False
        checks["webhook_healthy"] = scheduler._webhook_healthy if scheduler else True
    except Exception:
        pass
    
    healthy = checks["db"]  # DB is the minimum requirement
    status_code = 200 if healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "app": settings.APP_NAME,
            "checks": checks
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
