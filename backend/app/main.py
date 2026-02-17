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
    
    # Start CRM sync scheduler (optional - comment out to disable)
    # Note: webhook registration is handled by the scheduler's startup routine
    # (setup_crm_webhooks_on_startup) which covers ALL active campaigns.
    try:
        from app.services.crm_scheduler import start_crm_scheduler
        await start_crm_scheduler()
        logger.info("CRM sync scheduler started")
    except Exception as e:
        logger.warning(f"CRM scheduler start failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
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
