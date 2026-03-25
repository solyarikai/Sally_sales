"""MCP SSE Server — implements Model Context Protocol over Server-Sent Events."""
import json
import logging
import uuid
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.mcp.tools import TOOLS
from app.mcp.dispatcher import dispatch_tool

logger = logging.getLogger(__name__)

# Active SSE sessions
_sessions: dict[str, dict] = {}


async def handle_sse(request: Request):
    """SSE endpoint — client connects here for MCP protocol."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"user": None, "initialized": False}

    async def event_generator():
        # Send session endpoint info
        yield {
            "event": "endpoint",
            "data": f"/mcp/messages?session_id={session_id}",
        }

        # Keep connection alive
        import asyncio
        try:
            while True:
                if request.is_disconnected:
                    break
                await asyncio.sleep(15)
                yield {"event": "ping", "data": ""}
        except asyncio.CancelledError:
            pass
        finally:
            _sessions.pop(session_id, None)

    return EventSourceResponse(event_generator())


async def handle_message(request: Request):
    """Handle incoming MCP JSON-RPC messages."""
    session_id = request.query_params.get("session_id")
    if not session_id:
        return JSONResponse({"error": "Missing session_id"}, status_code=400)
    # Auto-create session if it doesn't exist (handles reconnection)
    if session_id not in _sessions:
        _sessions[session_id] = {"user": None, "initialized": False}

    body = await request.json()
    method = body.get("method", "")
    msg_id = body.get("id")
    params = body.get("params", {})

    logger.info(f"MCP message: method={method}, id={msg_id}")

    if method == "initialize":
        _sessions[session_id]["initialized"] = True
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "mcp-leadgen",
                    "version": "1.0.0",
                },
            },
        })

    elif method == "notifications/initialized":
        return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Extract auth token from params or session
        token = arguments.pop("_token", None)
        if not token:
            # Try Authorization header
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        try:
            result = await dispatch_tool(tool_name, arguments, token, request)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                    "isError": False,
                },
            })
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                    "isError": True,
                },
            })

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        })
