"""Real MCP Conversation Tests — LLM decides tools, MCP executes via SSE.

NOT scripted tool calls. Real conversations where GPT-4o-mini reads user prompts,
DECIDES which MCP tools to call (from the real tool list), and MCP executes them.

Deterministic: temperature=0, same prompts, same tool definitions → same decisions.
Uses dedicated test user qwe@qwe.qwe to not affect real users.

Install:
    pip install mcp httpx-sse openai playwright
    playwright install chromium

Usage:
    cd mcp && python3 tests/test_real_mcp.py
    cd mcp && python3 tests/test_real_mcp.py --user pn@getsally.io
    cd mcp && python3 tests/test_real_mcp.py --test 16_campaign_lifecycle
    cd mcp && python3 tests/test_real_mcp.py --no-screenshots
"""
import asyncio
import json
import os
import sys
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

import httpx

if os.path.exists(os.path.expanduser("~/magnum-opus-project")):
    print("ERROR: Run from LOCAL machine, not Hetzner.")
    sys.exit(1)

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
except ImportError:
    print("pip install mcp httpx-sse"); sys.exit(1)

try:
    from openai import AsyncOpenAI
except ImportError:
    print("pip install openai"); sys.exit(1)

MCP_URL = os.environ.get("MCP_URL", "http://46.62.210.24:8002")
MCP_SSE = f"{MCP_URL}/mcp/sse"
UI_URL = os.environ.get("UI_URL", "http://46.62.210.24:3000")
TESTS_DIR = Path(__file__).parent / "conversations"
TMP_DIR = Path(__file__).parent / "tmp"

# Load mcp/.env
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and v not in ("sk-...", ""):
                os.environ.setdefault(k, v)

openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


# ═══════════════════════════════════════════
# MCP → OpenAI tool format conversion
# ═══════════════════════════════════════════

def mcp_tools_to_openai(mcp_tools: list) -> list:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    result = []
    for t in mcp_tools:
        schema = t.inputSchema if hasattr(t, 'inputSchema') else (t.get("inputSchema") or {"type": "object", "properties": {}})
        result.append({
            "type": "function",
            "function": {
                "name": t.name if hasattr(t, 'name') else t["name"],
                "description": (t.description if hasattr(t, 'description') else t.get("description", ""))[:500],
                "parameters": schema,
            }
        })
    return result


# ═══════════════════════════════════════════
# CONVERSATION ENGINE
# ═══════════════════════════════════════════

class ConversationEngine:
    """Runs a real conversation: user prompt → GPT decides tools → MCP executes."""

    def __init__(self, mcp_session: ClientSession, openai_tools: list, user_email: str, mcp_token: str):
        self.mcp = mcp_session
        self.tools = openai_tools
        self.email = user_email
        self.token = mcp_token
        self.history: list[dict] = []
        self.tool_calls_log: list[dict] = []

        # System prompt — tells GPT it's testing MCP
        self.system = (
            f"You are an MCP client testing the LeadGen MCP server. "
            f"You are logged in as {user_email}. "
            f"Use the provided tools to fulfill user requests. "
            f"Call tools as needed — you decide which ones based on the user's message. "
            f"After tool calls, summarize what happened concisely. "
            f"If a tool returns an error, report it. "
            f"Always share any links or IDs returned by tools."
        )

    async def send(self, user_message: str) -> dict:
        """Send a user message, GPT decides tools, MCP executes. Returns full result."""
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": self.system}] + self.history[-20:]

        # GPT decides which tools to call (temperature=0 for determinism)
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=self.tools if self.tools else None,
            tool_choice="auto",
            temperature=0,
            max_tokens=1500,
        )

        choice = response.choices[0]
        msg = choice.message
        tools_called = []
        tool_results_for_gpt = []

        # Execute tool calls via real MCP SSE
        if msg.tool_calls:
            # Add assistant message with tool calls to history
            self.history.append({
                "role": "assistant",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                # Inject auth token for tools that need it
                if "token" in tool_args or tool_name == "login":
                    tool_args["token"] = self.token

                # Call via REAL MCP SSE
                try:
                    result = await self.mcp.call_tool(tool_name, arguments=tool_args)
                    content = result.content[0].text if result.content else "{}"
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        data = {"raw": content[:500]}
                except Exception as e:
                    data = {"error": str(e)}

                tools_called.append({"tool": tool_name, "args": tool_args, "result": data})
                self.tool_calls_log.append({"tool": tool_name, "args_summary": str(tool_args)[:100],
                                            "result_summary": str(data)[:200]})

                tool_results_for_gpt.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": json.dumps(data, default=str)[:3000],
                })

            # Add tool results to history
            self.history.extend(tool_results_for_gpt)

            # GPT formats final response
            format_resp = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": self.system}] + self.history[-20:],
                temperature=0,
                max_tokens=1000,
            )
            final_text = format_resp.choices[0].message.content or ""
        else:
            final_text = msg.content or ""

        self.history.append({"role": "assistant", "content": final_text})

        return {
            "user_message": user_message,
            "assistant_response": final_text,
            "tools_called": [t["tool"] for t in tools_called],
            "tool_details": tools_called,
            "full_response": final_text,
        }


# ═══════════════════════════════════════════
# SCORING
# ═══════════════════════════════════════════

def score_step(expected: dict, result: dict) -> dict:
    t = p = 0
    fails = {}

    # Check expected tool calls (hit rate)
    if "expected_tool_calls" in expected:
        exp_tools = expected["expected_tool_calls"]
        actual_tools = result.get("tools_called", [])
        for et in exp_tools:
            t += 1
            if et in actual_tools:
                p += 1
            else:
                fails[f"missing_tool:{et}"] = f"called: {actual_tools}"

    eb = expected.get("expected_behavior", {})

    if "response_must_contain" in eb:
        full = json.dumps(result).lower()
        for w in eb["response_must_contain"]:
            t += 1
            if w.lower() in full: p += 1
            else: fails[f"missing:{w}"] = True

    if "response_must_not_contain" in eb:
        full = json.dumps(result).lower()
        for w in eb["response_must_not_contain"]:
            t += 1
            if w.lower() not in full: p += 1
            else: fails[f"unexpected:{w}"] = True

    if "response_must_contain_any" in eb:
        t += 1
        full = json.dumps(result).lower()
        if any(w.lower() in full for w in eb["response_must_contain_any"]): p += 1
        else: fails["must_contain_any"] = eb["response_must_contain_any"][:3]

    # Check for errors in tool results
    for td in result.get("tool_details", []):
        if isinstance(td.get("result"), dict) and td["result"].get("error"):
            t += 1
            fails[f"tool_error:{td['tool']}"] = td["result"]["error"][:80]

    return {"score": (p / t * 100) if t > 0 else 100, "passed": p, "total": t, "fails": fails}


# ═══════════════════════════════════════════
# SCREENSHOTS
# ═══════════════════════════════════════════

async def screenshot(path: str, name: str, ts: str) -> Optional[str]:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            br = await pw.chromium.launch(headless=True)
            pg = await br.new_page(viewport={"width": 1440, "height": 900})
            await pg.goto(f"{UI_URL}{path}", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(2)
            fp = TMP_DIR / f"{ts}_{name}.png"
            await pg.screenshot(path=str(fp), full_page=True)
            await br.close()
            return str(fp)
    except:
        return None


# ═══════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════

async def get_token(email: str, password: str = "qweqweqwe") -> str:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{MCP_URL}/api/auth/signup",
                         json={"email": email, "name": email.split("@")[0], "password": password})
        if r.status_code == 409:
            r = await c.post(f"{MCP_URL}/api/auth/login",
                             json={"email": email, "password": password})
        return r.json().get("api_token", "")


# ═══════════════════════════════════════════
# RUN ONE USER'S TESTS
# ═══════════════════════════════════════════

async def run_user(email: str, tests: list, do_ss: bool) -> list:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = await get_token(email)
    if not token:
        return [{"test_id": t["id"], "score": 0, "error": "login failed"} for t in tests]

    results = []

    print(f"\n{'#'*65}")
    print(f"# {email} — {len(tests)} conversations")
    print(f"{'#'*65}")

    async with sse_client(MCP_SSE) as (rs, ws):
        async with ClientSession(rs, ws) as mcp:
            await mcp.initialize()
            tools_result = await mcp.list_tools()
            openai_tools = mcp_tools_to_openai(tools_result.tools)
            print(f"  Connected — {len(openai_tools)} tools")

            # Login via MCP
            r = await mcp.call_tool("login", arguments={"token": token})

            # Create conversation engine
            engine = ConversationEngine(mcp, openai_tools, email, token)

            for test in tests:
                tid = test.get("id", "?")
                print(f"\n  ── {tid} ──")

                tres = {"test_id": tid, "steps": [], "conversations": [], "errors": []}

                for step in test.get("steps", []):
                    sn = step.get("step", "?")
                    phase = step.get("phase", "")

                    # Pick user prompt (shuffle variants for robustness)
                    prompts = [step.get("user_prompt", "")] + step.get("user_prompt_variants", [])
                    prompts = [p for p in prompts if p]
                    if not prompts:
                        tres["steps"].append({"step": sn, "phase": phase, "score": 100, "skipped": True})
                        continue

                    chosen = random.choice(prompts)
                    print(f"    {sn}. [{phase}] User: {chosen[:70]}...")

                    # REAL CONVERSATION: GPT reads prompt → decides tools → MCP executes
                    try:
                        result = await asyncio.wait_for(
                            engine.send(chosen),
                            timeout=120
                        )
                    except asyncio.TimeoutError:
                        result = {"error": "timeout", "tools_called": [], "tool_details": [],
                                  "assistant_response": "", "user_message": chosen}
                        tres["errors"].append(f"step {sn}: timeout")

                    tools_used = result.get("tools_called", [])
                    response = result.get("assistant_response", "")
                    print(f"       Tools: {tools_used}")
                    print(f"       Response: {response[:100]}...")

                    # Score
                    sc = score_step(step, result)
                    tres["steps"].append({"step": sn, "phase": phase, "prompt": chosen,
                                          "tools_called": tools_used, **sc})
                    tres["conversations"].append({
                        "step": sn, "user": chosen, "assistant": response[:300],
                        "tools": tools_used
                    })

                    if sc["fails"]:
                        for k, v in sc["fails"].items():
                            print(f"       FAIL: {k}")

                    await asyncio.sleep(0.3)

                # Test score
                scores = [s.get("score", 100) for s in tres["steps"]]
                tres["score"] = sum(scores) / len(scores) if scores else 0
                tres["timestamp"] = datetime.now(timezone.utc).isoformat()
                tres["total_tool_calls"] = len(engine.tool_calls_log)
                results.append(tres)

                st = "PASS" if tres["score"] >= 80 else "FAIL"
                print(f"  → {tid}: {tres['score']:.0f}% [{st}]")

                # Screenshots after each test
                if do_ss:
                    for pg_path, pg_name in [("/pipeline", "pipeline"), ("/crm", "crm"),
                                              ("/campaigns", "campaigns")]:
                        fp = await screenshot(pg_path, f"{tid}_{pg_name}", ts)
                        if fp: print(f"      screenshot: {Path(fp).name}")

    # Save results
    out = TMP_DIR / f"{ts}_{email.replace('@','_').replace('.','_')}.json"
    out.write_text(json.dumps(results, indent=2, default=str))

    # Save full conversation log
    conv_out = TMP_DIR / f"{ts}_{email.replace('@','_').replace('.','_')}_conversations.json"
    all_convs = []
    for r in results:
        all_convs.extend(r.get("conversations", []))
    conv_out.write_text(json.dumps(all_convs, indent=2, default=str))

    print(f"\n  Results → {out.name}")
    print(f"  Conversations → {conv_out.name}")
    return results


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="One user only")
    parser.add_argument("--test", help="One test ID only")
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args()

    TMP_DIR.mkdir(exist_ok=True)

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY env var (for GPT-4o-mini tool selection)")
        sys.exit(1)

    # Ensure test user exists
    print("Creating test user qwe@qwe.qwe...")
    await get_token("qwe@qwe.qwe", "qweqweqwe")

    # Load tests
    all_tests = []
    for f in sorted(TESTS_DIR.glob("*.json")):
        try: t = json.loads(f.read_text())
        except: continue
        if "steps" not in t or not t["steps"]: continue
        if args.test and args.test not in t.get("id", ""): continue
        all_tests.append(t)

    by_user = defaultdict(list)
    for t in all_tests:
        by_user[t.get("user_email", "qwe@qwe.qwe")].append(t)

    if args.user:
        by_user = {k: v for k, v in by_user.items() if k == args.user}

    do_ss = not args.no_screenshots

    print(f"\n{'='*65}")
    print(f"REAL MCP CONVERSATION TESTS")
    print(f"Engine: GPT-4o-mini (temp=0) → MCP SSE → Playwright screenshots")
    print(f"Server: {MCP_SSE}")
    print(f"{'='*65}")
    for email, ut in by_user.items():
        steps = sum(len(t.get("steps", [])) for t in ut)
        print(f"  {email}: {len(ut)} conversations, {steps} steps")

    # Run users SEQUENTIALLY to avoid SSE connection conflicts
    # (parallel SSE sessions can cause session token crossover — see audit29_03 Part 6D)
    user_results = []
    for email, ut in by_user.items():
        try:
            result = await run_user(email, ut, do_ss)
            user_results.append(result)
        except Exception as e:
            print(f"\n  FATAL: {email} failed: {e}")
            import traceback; traceback.print_exc()
            user_results.append([{"test_id": f"error_{email}", "score": 0, "error": str(e)}])

    all_results = []
    for ur in user_results:
        if isinstance(ur, Exception):
            all_results.append({"test_id": "error", "score": 0, "error": str(ur)})
        else:
            all_results.extend(ur)

    # Summary
    print(f"\n{'='*65}")
    print("SUMMARY")
    print(f"{'='*65}")
    total = 0
    for r in all_results:
        sc = r.get("score", 0)
        st = "PASS" if sc >= 80 else "FAIL"
        tc = r.get("total_tool_calls", 0)
        print(f"  {r['test_id']}: {sc:.0f}% [{st}] ({tc} tool calls)")
        total += sc

    avg = total / len(all_results) if all_results else 0
    print(f"\n  OVERALL: {avg:.1f}%  {'GOD' if avg >= 95 else 'PASS' if avg >= 80 else 'FAIL'}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = TMP_DIR / f"{ts}_summary.json"
    summary.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "GPT-4o-mini (temp=0) → real MCP SSE → Playwright",
        "server": MCP_SSE,
        "results": all_results,
        "average": avg,
    }, indent=2, default=str))
    print(f"  → {summary.name}")


if __name__ == "__main__":
    asyncio.run(main())
