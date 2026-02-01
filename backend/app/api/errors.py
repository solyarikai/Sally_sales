"""
Error logging endpoint for frontend error reporting.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

router = APIRouter(prefix="/errors", tags=["errors"])

# Configure logger for frontend errors
frontend_logger = logging.getLogger("frontend_errors")
frontend_logger.setLevel(logging.ERROR)

# Create file handler if not exists
if not frontend_logger.handlers:
    handler = logging.FileHandler("/tmp/frontend_errors.log")
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    frontend_logger.addHandler(handler)
    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - FRONTEND ERROR - %(message)s'
    ))
    frontend_logger.addHandler(console_handler)


class FrontendError(BaseModel):
    error: str
    stack: Optional[str] = None
    componentStack: Optional[str] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None
    timestamp: Optional[str] = None
    extra: Optional[dict] = None


@router.post("/log")
async def log_frontend_error(error: FrontendError):
    """
    Log frontend errors for debugging and monitoring.
    """
    timestamp = error.timestamp or datetime.utcnow().isoformat()
    
    # Format the log message
    log_message = f"""
=== Frontend Error ===
Time: {timestamp}
URL: {error.url or 'Unknown'}
User-Agent: {error.userAgent or 'Unknown'}

Error: {error.error}

Stack Trace:
{error.stack or 'No stack trace'}

Component Stack:
{error.componentStack or 'No component stack'}

Extra Data: {error.extra or {}}
======================
"""
    
    # Log to file and console
    frontend_logger.error(log_message)
    
    # In production, you might want to:
    # - Send to error tracking service (Sentry, etc.)
    # - Store in database for analysis
    # - Send alerts for critical errors
    
    return {"status": "logged", "timestamp": timestamp}


@router.get("/health")
async def error_logging_health():
    """Check if error logging is working."""
    return {"status": "ok", "logging_enabled": True}
