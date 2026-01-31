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
    
    # Create default user and templates
    async with async_session_maker() as session:
        await ensure_default_user(session)
        await ensure_default_templates(session)
        await session.commit()
    
    # Setup automatic file synchronization
    from app.services.sync_service import setup_default_syncs
    try:
        await setup_default_syncs()
        logger.info("File synchronization enabled")
    except Exception as e:
        logger.warning(f"Failed to setup file sync: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
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
    return {"status": "healthy", "app": settings.APP_NAME}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
