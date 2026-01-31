from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "LeadGen Automation"
    DEBUG: bool = False
    
    # Database - PostgreSQL (use SQLite for fallback: sqlite+aiosqlite:///./leadgen.db)
    DATABASE_URL: str = "postgresql+asyncpg://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen"
    
    # Database pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    
    # Redis - for caching and rate limiting
    REDIS_URL: str = "redis://leadgen-redis:6379/0"
    CACHE_TTL_DEFAULT: int = 300  # 5 minutes
    CACHE_TTL_SHORT: int = 60     # 1 minute
    CACHE_TTL_LONG: int = 3600    # 1 hour
    
    # OpenAI - MUST be set via .env file
    OPENAI_API_KEY: Optional[str] = None
    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Available OpenAI models for enrichment (latest models)
    AVAILABLE_MODELS: List[str] = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
        "o3-mini",
    ]
    
    # Processing - optimized for large datasets (1000-10000 rows)
    BATCH_SIZE: int = 25
    MAX_CONCURRENT_REQUESTS: int = 15
    
    # File upload limits
    MAX_UPLOAD_SIZE_MB: int = 100
    STREAMING_CHUNK_SIZE: int = 8192  # 8KB chunks for streaming
    
    # Integrations
    INSTANTLY_API_KEY: Optional[str] = None
    INSTANTLY_BASE_URL: str = "https://api.instantly.ai/api/v2"
    
    # CORS - comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
    
    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
