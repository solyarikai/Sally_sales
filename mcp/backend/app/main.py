"""MCP LeadGen — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.middleware.base import BaseHTTPMiddleware

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
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request body size limit (10 MB)
MAX_BODY_SIZE = 10 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)


# Simple in-memory rate limiter for auth endpoints
import time as _time
from collections import defaultdict

_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10  # max requests per window per IP


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/auth/"):
            ip = request.client.host if request.client else "unknown"
            now = _time.time()
            _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < RATE_LIMIT_WINDOW]
            if len(_rate_limits[ip]) >= RATE_LIMIT_MAX:
                return JSONResponse(status_code=429, content={"detail": "Too many requests"})
            _rate_limits[ip].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# ── REST API routes ──
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.setup import router as setup_router
from app.api.pipeline import router as pipeline_router

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")


# ── Direct tool call REST endpoint (for Telegram bot, no SSE needed) ──

from fastapi import Header
from pydantic import BaseModel
from typing import Optional


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.get("/api/tools")
async def list_tools_rest():
    """List all MCP tools via REST (no SSE session needed). Used by Telegram bot."""
    from app.mcp.tools import TOOLS
    return {"tools": TOOLS}


@app.post("/api/tools/call")
async def call_tool_rest(
    req: ToolCallRequest,
    x_mcp_token: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Call an MCP tool via REST (no SSE session needed). Used by Telegram bot."""
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif x_mcp_token:
        token = x_mcp_token

    from app.mcp.dispatcher import dispatch_tool
    from app.db import async_session_maker
    async with async_session_maker() as session:
        try:
            result = await dispatch_tool(req.name, req.arguments, token, session)
            await session.commit()
            return {"result": result}
        except ValueError as e:
            await session.rollback()
            return {"error": str(e)}
        except Exception as e:
            await session.rollback()
            logger.error(f"Tool call {req.name} failed: {e}")
            return {"error": "Internal error processing tool call"}

# Contacts API — compatible with main app's ContactsPage
from app.api.contacts import router as contacts_router
app.include_router(contacts_router, prefix="/api")

# Replies API — stubs for TasksPage compatibility
from app.api.replies import router as replies_router
app.include_router(replies_router, prefix="/api")

# Account API — credits, usage, API keys
from app.api.account import router as account_router
app.include_router(account_router, prefix="/api")

# ── MCP SSE (official SDK) ──
from app.mcp.server import sse_transport, mcp_server


class MCPApp:
    """Raw ASGI app that routes /mcp/sse and /mcp/messages without Starlette wrapping.

    Intercepts all JSON-RPC messages for full conversation logging.
    """

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        logger.info(f"MCPApp: path={path}, type={scope.get('type')}")

        if scope["type"] in ("http", "websocket"):
            if "/sse" in path:
                # SSE connection — intercept server→client messages for logging
                async with sse_transport.connect_sse(scope, receive, send) as streams:
                    read_stream, write_stream = streams
                    await mcp_server.run(
                        read_stream, write_stream, mcp_server.create_initialization_options()
                    )
            elif "/messages" in path:
                # Extract auth token from HTTP headers and store for tool calls
                from app.mcp.server import _session_tokens
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()
                mcp_token = headers.get(b"x-mcp-token", b"").decode()
                token = ""
                session_id = ""
                if auth.startswith("Bearer "):
                    token = auth[7:]
                elif mcp_token:
                    token = mcp_token
                if token:
                    qs = scope.get("query_string", b"").decode()
                    for part in qs.split("&"):
                        if part.startswith("session_id="):
                            session_id = part.split("=", 1)[1]
                            _session_tokens[session_id] = token
                            break
                    _session_tokens["_latest"] = token

                # Intercept request body for conversation logging
                body_chunks = []
                async def logging_receive():
                    msg = await receive()
                    if msg.get("type") in ("http.request", "http.disconnect"):
                        body = msg.get("body", b"")
                        if body:
                            body_chunks.append(body)
                    return msg

                try:
                    await sse_transport.handle_post_message(scope, logging_receive, send)
                finally:
                    # Log after response is sent (async, non-blocking)
                    if body_chunks:
                        import asyncio
                        full_body = b"".join(body_chunks)
                        asyncio.create_task(
                            _log_conversation_message(full_body, token, session_id)
                        )
            else:
                await send({"type": "http.response.start", "status": 404, "headers": []})
                await send({"type": "http.response.body", "body": b"Not found"})
        elif scope["type"] == "lifespan":
            # Handle lifespan events
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return


async def _log_conversation_message(body: bytes, token: str, session_id: str):
    """Log a JSON-RPC message from the MCP client to the database."""
    import json as _json
    try:
        raw = _json.loads(body)
    except Exception:
        return  # Not JSON, skip

    method = raw.get("method", "")
    msg_type = "request" if "method" in raw else ("response" if "result" in raw or "error" in raw else "notification")

    # Build human-readable summary
    summary = ""
    if method == "tools/call":
        params = raw.get("params", {})
        tool_name = params.get("name", "?")
        args = params.get("arguments", {})
        args_preview = str(args)[:200]
        summary = f"Tool call: {tool_name}({args_preview})"
    elif method == "tools/list":
        summary = "List tools"
    elif method == "initialize":
        summary = f"Initialize: {raw.get('params', {}).get('clientInfo', {})}"
    elif method:
        summary = f"{method}: {str(raw.get('params', {}))[:200]}"
    else:
        summary = f"Response/notification: {str(raw)[:200]}"

    # Resolve user from token
    user_id = None
    if token:
        try:
            from app.db import async_session_maker
            from app.auth.middleware import verify_token
            async with async_session_maker() as session:
                user = await verify_token(session, token)
                if user:
                    user_id = user.id

                from app.models.usage import MCPConversationLog
                log = MCPConversationLog(
                    user_id=user_id,
                    session_id=session_id or None,
                    direction="client_to_server",
                    method=method or None,
                    message_type=msg_type,
                    raw_json=raw,
                    content_summary=summary[:1000],
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.debug(f"Conversation log failed: {e}")


app.mount("/mcp", MCPApp())


@app.get("/")
async def root():
    return {"service": "mcp-leadgen", "version": "1.0.0", "docs": "/docs"}
