"""MCP LeadGen — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route

from app.config import settings
from app.db.database import close_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MCP LeadGen starting up...")
    yield
    logger.info("MCP LeadGen shutting down...")
    await close_db()


app = FastAPI(
    title="MCP LeadGen",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST API routes ──
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.setup import router as setup_router
from app.api.pipeline import router as pipeline_router

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")

# ── MCP SSE (official SDK) ──
# The MCP SDK's SseServerTransport needs raw ASGI handlers.
# We mount them directly using Starlette Mount which preserves ASGI signatures.
from app.mcp.server import sse_transport, mcp_server


async def _sse_handler(scope, receive, send):
    async with sse_transport.connect_sse(scope, receive, send) as streams:
        await mcp_server.run(
            streams[0], streams[1], mcp_server.create_initialization_options()
        )


# Mount as raw ASGI — bypasses Starlette's Request wrapping
app.mount("/mcp", app=Mount("", routes=[
    Route("/sse", _sse_handler),
    Route("/messages", sse_transport.handle_post_message, methods=["POST"]),
]))


@app.get("/")
async def root():
    return {"service": "mcp-leadgen", "version": "1.0.0", "docs": "/docs"}
