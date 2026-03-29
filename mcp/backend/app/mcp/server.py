"""MCP Server — uses official MCP Python SDK for proper protocol compliance."""
import json
import logging

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.requests import Request

from app.mcp.tools import TOOLS
from app.mcp.dispatcher import dispatch_tool

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp_server = Server("mcp-leadgen")

# SSE transport — path is relative to mount point (/mcp), so just /messages
sse_transport = SseServerTransport("/messages")

# Token store: session_id → auth token (extracted from HTTP headers on POST)
_session_tokens: dict[str, str] = {}

# Per-session token for concurrent session isolation
# Uses MCP SDK's request_context to identify which session a tool call belongs to.
# Each SSE connection = one session. Token stored per session_id.
_session_user_tokens: dict[int, str] = {}  # session_object_id → token


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    tools = []
    for t in TOOLS:
        tools.append(Tool(
            name=t["name"],
            description=(t.get("description") or "")[:1024],
            inputSchema=t.get("inputSchema", {"type": "object", "properties": {}}),
        ))
    return tools


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Token from arguments (explicit) or from session-local store (set by login tool)
    token = arguments.pop("_token", None)
    if not token:
        # Use MCP SDK's request_context to identify current session
        try:
            ctx = mcp_server.request_context
            session_key = id(ctx.session)
            token = _session_user_tokens.get(session_key, '')
        except (LookupError, AttributeError):
            pass
    if not token:
        # Fallback: HTTP header token stored per session_id
        for sid, t in _session_tokens.items():
            if t:
                token = t
                break
    try:
        result = await dispatch_tool(name, arguments, token, None)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def handle_sse(request: Request):
    """SSE endpoint — Starlette Request wrapper for MCP SDK."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0], streams[1], mcp_server.create_initialization_options()
        )


async def handle_messages(request: Request):
    """Message endpoint — Starlette Request wrapper for MCP SDK."""
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )
