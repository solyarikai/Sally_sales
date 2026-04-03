"""
Redis Cache Service for LeadGen Automation

Provides caching layer for:
- API responses
- Database query results
- Rate limiting
- Session data
"""
import json
import hashlib
from typing import Any, Optional, Callable, TypeVar
from functools import wraps
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheService:
    """Async Redis cache service with automatic serialization"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Initialize Redis connection"""
        if self._redis is not None:
            return self._connected
        
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info("Redis cache connected")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._redis = None
            self._connected = False
            return False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"leadgen:{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._connected or not self._redis:
            return None
        
        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL"""
        if not self._connected or not self._redis:
            return False
        
        try:
            data = json.dumps(value, default=str)
            if ttl:
                await self._redis.setex(key, ttl, data)
            else:
                await self._redis.set(key, data)
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self._connected or not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self._connected or not self._redis:
            return 0
        
        try:
            keys = []
            async for key in self._redis.scan_iter(match=f"leadgen:{pattern}:*"):
                keys.append(key)
            
            if keys:
                await self._redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Cache delete pattern error: {e}")
            return 0
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or call factory and cache result"""
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        result = await factory() if callable(factory) else factory
        await self.set(key, result, ttl)
        return result
    
    # Rate limiting helpers
    async def rate_limit_check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check rate limit. Returns (allowed, remaining).
        Uses sliding window counter.
        """
        if not self._connected or not self._redis:
            return True, max_requests  # Allow if no Redis
        
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, window_seconds)
            
            remaining = max(0, max_requests - current)
            allowed = current <= max_requests
            return allowed, remaining
        except Exception as e:
            logger.warning(f"Rate limit check error: {e}")
            return True, max_requests
    
    # Company-scoped cache helpers
    def company_key(self, company_id: int, resource: str, *args) -> str:
        """Generate company-scoped cache key"""
        return self._make_key(f"company:{company_id}:{resource}", *args)
    
    async def invalidate_company(self, company_id: int) -> int:
        """Invalidate all cache for a company"""
        return await self.delete_pattern(f"company:{company_id}")


# Singleton instance
cache_service = CacheService()


# Decorator for caching function results
def cached(
    prefix: str,
    ttl: int = settings.CACHE_TTL_DEFAULT,
    company_scoped: bool = False
):
    """
    Decorator to cache function results.
    
    Usage:
        @cached("prospects_list", ttl=60, company_scoped=True)
        async def get_prospects(company_id: int, page: int):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not cache_service.is_connected:
                return await func(*args, **kwargs)
            
            # Build cache key
            if company_scoped and "company_id" in kwargs:
                key = cache_service.company_key(
                    kwargs["company_id"], prefix, *args, **kwargs
                )
            else:
                key = cache_service._make_key(prefix, *args, **kwargs)
            
            # Try cache first
            cached_result = await cache_service.get(key)
            if cached_result is not None:
                return cached_result
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache_service.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


# Startup/shutdown hooks for FastAPI
async def init_cache():
    """Initialize cache on startup"""
    await cache_service.connect()


async def close_cache():
    """Close cache on shutdown"""
    await cache_service.disconnect()


# Sync lock helpers
SYNC_LOCK_KEY = "leadgen:sync_lock"
SYNC_LOCK_TTL = 600  # 10 minutes

async def acquire_sync_lock() -> bool:
    """
    Try to acquire exclusive sync lock.
    Returns True if lock acquired, False if sync already in progress.
    """
    if not cache_service.is_connected or not cache_service._redis:
        logger.warning("Redis not connected, skipping lock (allowing sync)")
        return True
    
    try:
        acquired = await cache_service._redis.set(
            SYNC_LOCK_KEY, 
            "1", 
            nx=True,  # Only set if not exists
            ex=SYNC_LOCK_TTL
        )
        if acquired:
            logger.info("Sync lock acquired")
            return True
        else:
            logger.warning("Sync lock already held - another sync in progress")
            return False
    except Exception as e:
        logger.warning(f"Failed to acquire sync lock: {e}")
        return True  # Allow sync if lock fails

async def release_sync_lock() -> bool:
    """Release the sync lock."""
    if not cache_service.is_connected or not cache_service._redis:
        return True
    
    try:
        await cache_service._redis.delete(SYNC_LOCK_KEY)
        logger.info("Sync lock released")
        return True
    except Exception as e:
        logger.warning(f"Failed to release sync lock: {e}")
        return False


# Reply tracking cache
SMARTLEAD_REPLIES_KEY = "leadgen:replies:smartlead"
GETSALES_REPLIES_KEY = "leadgen:replies:getsales"
REPLIES_TTL = 86400 * 7  # 7 days


async def add_processed_reply(source: str, reply_id: str) -> bool:
    """Add reply ID to processed set."""
    if not cache_service.is_connected or not cache_service._redis:
        return False
    
    try:
        key = SMARTLEAD_REPLIES_KEY if source == "smartlead" else GETSALES_REPLIES_KEY
        await cache_service._redis.sadd(key, str(reply_id))
        await cache_service._redis.expire(key, REPLIES_TTL)
        return True
    except Exception as e:
        logger.warning(f"Failed to add processed reply: {e}")
        return False


async def is_reply_processed(source: str, reply_id: str) -> bool:
    """Check if reply ID was already processed."""
    if not cache_service.is_connected or not cache_service._redis:
        return False
    
    try:
        key = SMARTLEAD_REPLIES_KEY if source == "smartlead" else GETSALES_REPLIES_KEY
        return await cache_service._redis.sismember(key, str(reply_id))
    except Exception as e:
        logger.warning(f"Failed to check processed reply: {e}")
        return False


async def bulk_check_replies(source: str, reply_ids: list) -> set:
    """
    Check multiple reply IDs at once. 
    Returns set of already processed IDs.
    """
    if not cache_service.is_connected or not cache_service._redis:
        return set()
    
    if not reply_ids:
        return set()
    
    try:
        key = SMARTLEAD_REPLIES_KEY if source == "smartlead" else GETSALES_REPLIES_KEY
        # Use pipeline for efficiency
        pipe = cache_service._redis.pipeline()
        for rid in reply_ids:
            pipe.sismember(key, str(rid))
        results = await pipe.execute()
        return {str(rid) for rid, exists in zip(reply_ids, results) if exists}
    except Exception as e:
        logger.warning(f"Failed to bulk check replies: {e}")
        return set()


async def bulk_add_replies(source: str, reply_ids: list) -> bool:
    """Add multiple reply IDs to processed set at once."""
    if not cache_service.is_connected or not cache_service._redis:
        return False
    
    if not reply_ids:
        return True
    
    try:
        key = SMARTLEAD_REPLIES_KEY if source == "smartlead" else GETSALES_REPLIES_KEY
        await cache_service._redis.sadd(key, *[str(rid) for rid in reply_ids])
        await cache_service._redis.expire(key, REPLIES_TTL)
        return True
    except Exception as e:
        logger.warning(f"Failed to bulk add replies: {e}")
        return False


async def try_claim_reply(source: str, reply_key: str, ttl: int = REPLIES_TTL) -> bool:
    """Atomic claim: returns True if this caller won the race (key was new).

    Uses SADD which is atomic — if the member already exists, returns 0.
    This replaces the check-then-set pattern that had a race window.
    """
    if not cache_service.is_connected or not cache_service._redis:
        return True  # If Redis is down, proceed (DB constraint is backup)

    try:
        key = SMARTLEAD_REPLIES_KEY if source == "smartlead" else GETSALES_REPLIES_KEY
        added = await cache_service._redis.sadd(key, str(reply_key))
        if added:
            await cache_service._redis.expire(key, ttl)
        return bool(added)
    except Exception as e:
        logger.warning(f"try_claim_reply failed: {e}")
        return True  # Proceed on Redis failure, DB constraint is backup


async def get_replies_cache_stats() -> dict:
    """Get stats about the reply cache."""
    if not cache_service.is_connected or not cache_service._redis:
        return {"connected": False}
    
    try:
        smartlead_count = await cache_service._redis.scard(SMARTLEAD_REPLIES_KEY)
        getsales_count = await cache_service._redis.scard(GETSALES_REPLIES_KEY)
        return {
            "connected": True,
            "smartlead_cached": smartlead_count,
            "getsales_cached": getsales_count
        }
    except Exception as e:
        logger.warning(f"Failed to get cache stats: {e}")
        return {"connected": True, "error": str(e)}


async def backfill_reply_cache_from_db() -> dict:
    """
    Backfill Redis reply cache from existing contact_activities.
    
    Called on startup to populate cache with already-processed reply IDs.
    Returns stats about how many IDs were loaded.
    """
    if not cache_service.is_connected or not cache_service._redis:
        logger.warning("Redis not connected, skipping reply cache backfill")
        return {"skipped": "no_redis"}
    
    try:
        from app.db import async_session_maker
        from app.models.contact import ContactActivity
        from sqlalchemy import select
        from datetime import datetime, timedelta
        
        # Only backfill replies from last 7 days (matches TTL)
        since = datetime.utcnow() - timedelta(days=7)
        
        async with async_session_maker() as session:
            # Get Smartlead reply IDs
            smartlead_query = await session.execute(
                select(ContactActivity.source_id).where(
                    ContactActivity.source == "smartlead",
                    ContactActivity.activity_type == "email_replied",
                    ContactActivity.activity_at >= since
                )
            )
            smartlead_ids = [row[0] for row in smartlead_query.all() if row[0]]
            
            # Get GetSales reply IDs
            getsales_query = await session.execute(
                select(ContactActivity.source_id).where(
                    ContactActivity.source == "getsales",
                    ContactActivity.activity_type == "linkedin_replied",
                    ContactActivity.activity_at >= since
                )
            )
            getsales_ids = [row[0] for row in getsales_query.all() if row[0]]
        
        # Bulk add to Redis
        stats = {
            "smartlead": len(smartlead_ids),
            "getsales": len(getsales_ids)
        }
        
        if smartlead_ids:
            await bulk_add_replies("smartlead", smartlead_ids)
        
        if getsales_ids:
            await bulk_add_replies("getsales", getsales_ids)
        
        logger.info(f"Reply cache backfill complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Reply cache backfill failed: {e}")
        return {"error": str(e)}
