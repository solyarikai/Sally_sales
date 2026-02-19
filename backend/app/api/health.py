"""Health check endpoints for monitoring and load balancers."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import os
import logging

from app.db import get_session
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
@router.get("/")
async def health_check():
    """Basic health check - returns 200 if service is running."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "leadgen-backend",
    }


@router.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    """
    Readiness check - verifies database connection is working.
    Used by Kubernetes/load balancers to determine if traffic should be routed.
    """
    checks = {
        "database": False,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    try:
        # Test database connection
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database_error"] = str(e)
    
    # Overall status
    is_healthy = all([checks["database"]])
    
    return {
        "status": "ready" if is_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/live")
async def liveness_check():
    """
    Liveness check - returns 200 if the process is running.
    Used by Kubernetes to determine if the container should be restarted.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/details")
async def detailed_health(session: AsyncSession = Depends(get_session)):
    """
    Detailed health check with system information.
    Should be protected in production environments.
    """
    import platform
    
    checks = {
        "database": {"status": "unknown"},
        "environment": {},
        "system": {},
    }
    
    # Database check with connection pool info
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        checks["database"]["status"] = "healthy"
    except Exception as e:
        checks["database"]["status"] = "unhealthy"
        checks["database"]["error"] = str(e)
    
    # Environment info — all integrations
    checks["environment"] = {
        "debug": settings.DEBUG,
        "openai": bool(settings.OPENAI_API_KEY),
        "apollo": bool(settings.APOLLO_API_KEY),
        "findymail": bool(settings.FINDYMAIL_API_KEY),
        "smartlead": bool(settings.SMARTLEAD_API_KEY),
        "yandex_search": bool(settings.YANDEX_SEARCH_API_KEY),
        "crona": bool(settings.CRONA_EMAIL and settings.CRONA_PASSWORD),
        "apify_proxy": bool(settings.APIFY_PROXY_PASSWORD),
        "google_sheets": bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        "getsales": bool(settings.GETSALES_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
        "instantly": bool(settings.INSTANTLY_API_KEY),
        "clay": bool(settings.CLAY_API_KEY),
        "telegram": bool(settings.TELEGRAM_BOT_TOKEN),
    }
    
    # System info
    checks["system"] = {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
    }
    
    # Overall status
    is_healthy = checks["database"]["status"] == "healthy"
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }
