from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings


# Configure engine with connection pooling
# Use NullPool for SQLite (doesn't support pooling)
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

if is_sqlite:
    engine_kwargs["poolclass"] = NullPool
else:
    # PostgreSQL pool settings
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_pre_ping": True,  # Verify connections before use
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create tables that don't exist yet. Safe to run repeatedly."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Table already exists errors are safe to ignore on startup
        import logging
        logging.getLogger(__name__).warning(f"init_db warning (safe to ignore): {e}")


async def close_db():
    """Close database connections on shutdown"""
    await engine.dispose()
