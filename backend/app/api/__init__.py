from fastapi import APIRouter
from .companies import router as companies_router
from .datasets import router as datasets_router
from .datasets import folder_router as folders_router
from .enrichment import router as enrichment_router
from .templates import router as templates_router
from .settings import router as settings_router
from .export import router as export_router
from .websocket import router as websocket_router
from .integrations import router as integrations_router
from .knowledge_base import router as knowledge_base_router
from .prospects import router as prospects_router
from .sync import router as sync_router
from .environments import router as environments_router
from .smartlead import router as smartlead_router
from .replies import router as replies_router
from .slack_interactions import router as slack_router

api_router = APIRouter(prefix="/api")

# Company management (must be first for /me endpoint)
api_router.include_router(companies_router)

# Data endpoints
api_router.include_router(datasets_router)
api_router.include_router(folders_router)
api_router.include_router(enrichment_router)
api_router.include_router(templates_router)
api_router.include_router(settings_router)
api_router.include_router(export_router)
api_router.include_router(websocket_router)
api_router.include_router(integrations_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(prospects_router)
api_router.include_router(sync_router)
api_router.include_router(environments_router)

# Reply Automation
api_router.include_router(smartlead_router)
api_router.include_router(replies_router)
api_router.include_router(slack_router)

__all__ = ["api_router"]
