"""
Telegram Bot → MCP LeadGen bridge.
GPT-4o-mini translates user messages into MCP tool calls.

Usage:
  TELEGRAM_BOT_TOKEN=... OPENAI_API_KEY=... MCP_URL=http://mcp-backend:8000 python bot.py
"""
import os
import json
import asyncio
import logging
from typing import Any

import httpx
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ──
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
MCP_URL = os.environ.get("MCP_URL", "http://mcp-backend:8000")
REDIS_URL = os.environ.get("REDIS_URL", "redis://mcp-redis:6379/1")
UI_BASE = os.environ.get("UI_BASE", "http://46.62.210.24:3000")
MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
openai = AsyncOpenAI(api_key=OPENAI_KEY)
redis_client: redis.Redis = None


# ── MCP Tool Definitions (loaded once from server) ──
_mcp_tools: list[dict] = []
_openai_tools: list[dict] = []


async def load_mcp_tools():
    """Fetch tool list from MCP server REST endpoint and convert to OpenAI format."""
    global _mcp_tools, _openai_tools
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{MCP_URL}/api/tools")
        data = resp.json()
        _mcp_tools = data.get("tools", [])

    _openai_tools = []
    for tool in _mcp_tools:
        _openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"][:500],
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        })
    logger.info(f"Loaded {len(_openai_tools)} MCP tools for OpenAI")


# ── Session State ──

async def get_session(tg_user_id: int) -> dict:
    raw = await redis_client.get(f"tg_session:{tg_user_id}")
    if raw:
        return json.loads(raw)
    return {
        "mcp_token": None,
        "active_project_id": None,
        "active_project_name": None,
        "active_run_id": None,
        "current_phase": None,
        "pending_gate_id": None,
        "history": [],
    }


async def save_session(tg_user_id: int, session: dict):
    # Keep history manageable
    session["history"] = session["history"][-20:]
    await redis_client.set(f"tg_session:{tg_user_id}", json.dumps(session), ex=86400 * 7)


# ── MCP Client ──

async def call_mcp_tool(tool_name: str, arguments: dict, mcp_token: str = None) -> dict:
    """Call an MCP tool via REST API."""
    headers = {"Content-Type": "application/json"}
    if mcp_token:
        headers["X-MCP-Token"] = mcp_token

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{MCP_URL}/api/tools/call",
            headers=headers,
            json={"name": tool_name, "arguments": arguments},
        )
        data = resp.json()
        if data.get("error"):
            return {"error": data["error"]}
        return data.get("result", {})


# ── AI Router ──

def build_system_prompt(session: dict) -> str:
    parts = [
        "You are a lead generation assistant on Telegram. Use the provided tools to help users.",
        "Keep responses concise — Telegram messages should be short and clear.",
        "Always share links when available.",
        f"UI: {UI_BASE}",
    ]

    if session.get("mcp_token"):
        parts.append(f"\nUser is authenticated.")
    else:
        parts.append(f"\nUser has NO account yet. Tell them: sign up at {UI_BASE}/setup to get your API token, then paste it here. Call 'login' tool with the token.")

    if session.get("active_project_name"):
        parts.append(f"Active project: {session['active_project_name']} (ID: {session['active_project_id']})")

    if session.get("active_run_id"):
        parts.append(f"Pipeline run: #{session['active_run_id']}, phase: {session.get('current_phase', 'unknown')}")
        parts.append(f"Pipeline link: {UI_BASE}/pipeline/{session['active_run_id']}")

    if session.get("pending_gate_id"):
        parts.append(f"PENDING APPROVAL: Gate #{session['pending_gate_id']}. If user says 'approve'/'yes', call tam_approve_checkpoint.")

    parts.append("\nRules: ask before gathering (keywords, location, size, pages). Never skip checkpoints. Campaigns are DRAFT only.")

    return "\n".join(parts)


async def process_message(user_message: str, session: dict) -> tuple[str, dict]:
    """Send user message to GPT-4o-mini with tools. Returns (response_text, updated_session)."""

    messages = [
        {"role": "system", "content": build_system_prompt(session)},
    ]

    # Add recent history for context
    for h in session.get("history", [])[-10:]:
        messages.append(h)

    messages.append({"role": "user", "content": user_message})

    # Call OpenAI with function calling
    response = await openai.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=_openai_tools if _openai_tools else None,
        tool_choice="auto",
        max_tokens=1000,
    )

    choice = response.choices[0]
    assistant_msg = choice.message

    # If GPT wants to call a tool
    if assistant_msg.tool_calls:
        tool_results = []
        for tc in assistant_msg.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            logger.info(f"Tool call: {tool_name}({json.dumps(tool_args)[:200]})")

            # Call MCP
            result = await call_mcp_tool(tool_name, tool_args, session.get("mcp_token"))

            # Update session state from result
            if tool_name == "setup_account" and result.get("api_token"):
                session["mcp_token"] = result["api_token"]

            if tool_name == "select_project" and result.get("active_project"):
                session["active_project_id"] = result["active_project"]["id"]
                session["active_project_name"] = result["active_project"]["name"]

            if tool_name == "tam_gather" and result.get("run_id"):
                session["active_run_id"] = result["run_id"]

            if tool_name in ("tam_blacklist_check", "tam_analyze", "tam_prepare_verification"):
                if result.get("gate_id"):
                    session["pending_gate_id"] = result["gate_id"]

            if tool_name == "tam_approve_checkpoint":
                session["pending_gate_id"] = None

            if tool_name == "pipeline_status":
                session["current_phase"] = result.get("phase")

            tool_results.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "content": json.dumps(result, default=str)[:3000],
            })

        # Send results back to GPT for formatting
        messages.append({"role": "assistant", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in assistant_msg.tool_calls
        ]})
        messages.extend(tool_results)

        format_response = await openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1000,
        )
        final_text = format_response.choices[0].message.content or "Done."
    else:
        final_text = assistant_msg.content or "I'm not sure what to do. Try asking me to find companies or check pipeline status."

    # Save to history
    session["history"].append({"role": "user", "content": user_message})
    session["history"].append({"role": "assistant", "content": final_text[:500]})

    return final_text, session


# ── Telegram Handlers ──

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Welcome to LeadGen MCP Bot!\n\n"
        "I help you find companies, build prospect lists, and create outreach campaigns.\n\n"
        f"To get started, sign up at {UI_BASE}/setup and paste your mcp_ token here.\n\n"
        "Then try:\n"
        "• \"Find IT consulting companies in US, 50-200 employees\"\n"
        "• \"What's my pipeline status?\"\n"
        "• \"Create a campaign sequence\"\n\n"
        f"Web UI: {UI_BASE}"
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    session = await get_session(message.from_user.id)
    parts = [
        f"Account: {'✓ connected' if session.get('mcp_token') else '✗ not set up'}",
        f"Project: {session.get('active_project_name', 'none')}",
        f"Pipeline: {'Run #' + str(session.get('active_run_id')) if session.get('active_run_id') else 'none'}",
        f"Phase: {session.get('current_phase', 'N/A')}",
    ]
    if session.get("pending_gate_id"):
        parts.append(f"⚠️ Pending approval: Gate #{session['pending_gate_id']}")
    await message.answer("\n".join(parts))


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    await redis_client.delete(f"tg_session:{message.from_user.id}")
    await message.answer("Session reset. Start fresh with /start")


@dp.message(F.text)
async def handle_text(message: types.Message):
    session = await get_session(message.from_user.id)

    try:
        response_text, updated_session = await process_message(message.text, session)
        await save_session(message.from_user.id, updated_session)

        # Telegram has 4096 char limit
        for i in range(0, len(response_text), 4000):
            await message.answer(response_text[i:i + 4000])

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await message.answer(f"Error: {str(e)[:200]}")


# ── Main ──

async def main():
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    # Load MCP tools on startup
    try:
        await load_mcp_tools()
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}. Will retry on first message.")

    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
