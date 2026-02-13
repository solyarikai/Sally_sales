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
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    
    # Redis - for caching and rate limiting
    REDIS_URL: str = "redis://leadgen-redis:6379/0"
    CACHE_TTL_DEFAULT: int = 300  # 5 minutes
    CACHE_TTL_SHORT: int = 60     # 1 minute
    CACHE_TTL_LONG: int = 3600    # 1 hour
    
    # OpenAI - MUST be set via .env file
    OPENAI_API_KEY: Optional[str] = None
    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"

    # Google Gemini - for complex reasoning tasks (query generation, website analysis)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-pro"
    
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
    
    # Google Sheets Integration
    # Either set GOOGLE_SERVICE_ACCOUNT_JSON (JSON string) or GOOGLE_APPLICATION_CREDENTIALS (path to JSON file)
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    
    # Google Drive Integration
    # Shared Drive ID — REQUIRED. Personal drive usage is FORBIDDEN.
    SHARED_DRIVE_ID: str = "0AEvTjlJFlWnZUk9PVA"
    
    # Yandex Search API
    YANDEX_SEARCH_API_KEY: Optional[str] = None
    YANDEX_SEARCH_FOLDER_ID: Optional[str] = None
    YANDEX_SEARCH_API_URL: str = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
    YANDEX_OPERATIONS_URL: str = "https://operation.api.cloud.yandex.net/operations"

    # Search settings
    SEARCH_MAX_PAGES: int = 3
    SEARCH_WORKERS: int = 8
    SEARCH_REQUEST_TIMEOUT: int = 30

    # Search pipeline settings
    SEARCH_DOMAIN_RECHECK_DAYS: int = 365       # Skip domains processed within this many days
    SEARCH_TARGET_GOAL: int = 1000              # Auto-iterate until this many targets found
    SEARCH_BATCH_QUERIES: int = 200             # Queries per iteration batch
    SEARCH_MAX_ITERATIONS: int = 30             # Safety cap on iterations

    # Crona API (website scraping via headless browser)
    CRONA_API_URL: str = "https://api.crona.ai"
    CRONA_EMAIL: Optional[str] = None
    CRONA_PASSWORD: Optional[str] = None
    CRONA_CREDITS_PER_SCRAPE: int = 1  # 1 credit per scrape_website call

    # Apollo API (people enrichment)
    APOLLO_API_KEY: Optional[str] = None
    APOLLO_API_URL: str = "https://api.apollo.io/api/v1"

    # Clay API (company enrichment via webhooks)
    CLAY_API_KEY: Optional[str] = None

    # Apify proxy (for Google SERP scraping)
    APIFY_PROXY_HOST: str = "proxy.apify.com"
    APIFY_PROXY_PORT: int = 8000
    APIFY_PROXY_PASSWORD: Optional[str] = None

    # CORS - comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,http://46.62.210.24,http://46.62.210.24:80,http://46.62.210.24:8000"
    
    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
