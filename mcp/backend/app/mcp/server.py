"""MCP Server — uses official MCP Python SDK for proper protocol compliance."""
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.requests import Request
from starlette.routing import Route

from app.mcp.tools import TOOLS
from app.mcp.dispatcher import dispatch_tool

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp_server = Server("mcp-leadgen")

# SSE transport
sse_transport = SseServerTransport("/mcp/messages")


# ── Register tool list handler ──
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all 30 MCP tools."""
    tools = []
    for t in TOOLS:
        tools.append(Tool(
            name=t["name"],
            description=(t.get("description") or "")[:1024],
            inputSchema=t.get("inputSchema", {"type": "object", "properties": {}}),
        ))
    return tools


# ── Register tool call handler ──
@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route tool calls to dispatcher."""
    # Extract auth token from arguments
    token = arguments.pop("_token", None)

    try:
        result = await dispatch_tool(name, arguments, token, None)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# ── Starlette routes for FastAPI integration ──

async def handle_sse(request: Request):
    """SSE endpoint — clients connect here."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0], streams[1], mcp_server.create_initialization_options()
        )


async def handle_messages(request: Request):
    """Message endpoint — receives JSON-RPC from clients."""
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


def get_mcp_routes():
    """Return Starlette routes for MCP endpoints."""
    return [
        Route("/mcp/sse", endpoint=handle_sse),
        Route("/mcp/messages", endpoint=handle_messages, methods=["POST"]),
    ]
