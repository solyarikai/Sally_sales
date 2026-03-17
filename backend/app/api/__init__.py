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
from .contacts import router as contacts_router
from .crm_sync import router as crm_sync_router
from .errors import router as errors_router
from .drive import router as drive_router
from .dashboard import router as dashboard_router
from .tasks import router as tasks_router
from .health import router as health_router
from .data_search import router as data_search_router
from .search import router as search_router
from .search_chat import router as search_chat_router
from .chat_stream import router as chat_stream_router
from .pipeline import router as pipeline_router
from .knowledge import router as project_knowledge_router
from .learning import router as learning_router
from .query_dashboard import router as query_dashboard_router
from .operator_tasks import router as operator_tasks_router
from .god_panel import router as god_panel_router
from .chat_intel import router as chat_intel_router
from .diaspora import router as diaspora_router
from .calendly_webhook import router as calendly_webhook_router
from .outreach_stats import router as outreach_stats_router
from .client_dashboard import router as client_dashboard_router
from .fireflies import router as fireflies_router
from .intelligence import router as intelligence_router
from .project_reports import router as project_reports_router

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

# CRM
api_router.include_router(contacts_router)
api_router.include_router(crm_sync_router)

# Google Drive
api_router.include_router(drive_router)

# Error logging
api_router.include_router(errors_router)

# Dashboard
api_router.include_router(dashboard_router)
api_router.include_router(query_dashboard_router)

# Tasks (from state/tasks.md)
api_router.include_router(tasks_router)

# Health checks (no prefix - /api/health)
api_router.include_router(health_router)

# Data Search (Explee-like natural language search)
api_router.include_router(data_search_router)

# Search Pipeline (Yandex + GPT analysis)
api_router.include_router(search_router)
api_router.include_router(search_chat_router)
api_router.include_router(chat_stream_router)

# Pipeline (outreach data processing)
api_router.include_router(pipeline_router)

# Project Knowledge (unified KB per project)
api_router.include_router(project_knowledge_router)

# Learning System (AI learning + feedback)
api_router.include_router(learning_router)

# Operator Tasks (3-tab daily operations)
api_router.include_router(operator_tasks_router)

# God Panel (campaign intelligence dashboard)
api_router.include_router(god_panel_router)

# Chat Intelligence (Telegram chat analysis)
api_router.include_router(chat_intel_router)

# Diaspora Contact Gathering
api_router.include_router(diaspora_router)

# Calendly Webhooks
api_router.include_router(calendly_webhook_router)

# Outreach Stats (Client Report)
api_router.include_router(outreach_stats_router)

# Client Dashboard (aggregated client report)
api_router.include_router(client_dashboard_router)

# Fireflies.ai Call Transcripts
api_router.include_router(fireflies_router)

# Reply Intelligence
api_router.include_router(intelligence_router)

# Project Reports (lead daily reports + plans + progress)
api_router.include_router(project_reports_router)

__all__ = ["api_router"]
