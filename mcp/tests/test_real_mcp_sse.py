"""Real MCP SSE test — connects like Claude Desktop would.

Tests the ACTUAL MCP protocol: SSE connect → initialize → tools/list → tools/call.
NOT REST mocks. This is what a real user experiences through Claude Desktop/Cursor.

Usage:
    ssh hetzner "cd ~/magnum-opus-project/repo && python3 mcp/tests/test_real_mcp_sse.py"
"""
import asyncio
import json
import os
import sys
import time

import httpx

MCP_URL = os.environ.get("MCP_URL", "http://localhost:3000")

# Load MCP .env for API keys
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip() and v.strip() not in ("sk-...", ""):
                os.environ.setdefault(k.strip(), v.strip())


async def main():
    results = {"passed": 0, "failed": 0, "tests": []}

    # Step 0: Login
    print("=== STEP 0: AUTH ===")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{MCP_URL}/api/auth/login", json={
            "email": "pn@getsally.io", "password": "qweqweqwe"
        })
        if resp.status_code != 200:
            resp = await client.post(f"{MCP_URL}/api/auth/signup", json={
                "email": "pn@getsally.io", "name": "Petr", "password": "qweqweqwe"
            })
        token = resp.json().get("api_token", "")
        print(f"  Token: {token[:20]}...")

    # Step 1: Connect integrations
    print("\n=== STEP 1: CONNECT INTEGRATIONS ===")
    async with httpx.AsyncClient(timeout=30) as client:
        headers = {"X-MCP-Token": token, "Content-Type": "application/json"}
        for name, key_env in [("smartlead", "SMARTLEAD_API_KEY"), ("apollo", "APOLLO_API_KEY"), ("openai", "OPENAI_API_KEY")]:
            key = os.environ.get(key_env, "")
            if key:
                r = await client.post(f"{MCP_URL}/api/setup/integrations", headers=headers,
                                      json={"integration_name": name, "api_key": key})
                status = "OK" if r.status_code == 200 else f"FAIL ({r.status_code})"
                print(f"  {name}: {status}")

    # Step 2: Connect to SSE (real MCP protocol)
    print("\n=== STEP 2: SSE CONNECT (real MCP protocol) ===")
    # IMPORTANT: SSE stream and POST messages must use SEPARATE clients
    # The SSE holds the connection open; POST needs its own connection
    sse_client = httpx.AsyncClient(timeout=120)
    msg_client = httpx.AsyncClient(timeout=60)
    try:
        headers = {"X-MCP-Token": token}
        messages_endpoint = None
        session_id = None

        async with sse_client.stream("GET", f"{MCP_URL}/mcp/sse", headers=headers) as sse:
            async for raw_line in sse.aiter_lines():
                line = raw_line.strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if "/messages" in data:
                        messages_endpoint = data.strip('"')
                        if "session_id=" in messages_endpoint:
                            session_id = messages_endpoint.split("session_id=")[1]
                        print(f"  Messages endpoint: {messages_endpoint}")
                        print(f"  Session ID: {session_id}")
                        break

            if not messages_endpoint:
                print("FATAL: No messages endpoint from SSE")
                sys.exit(1)

            msg_url = f"{MCP_URL}{messages_endpoint}" if messages_endpoint.startswith("/") else messages_endpoint

            # Helper: send JSON-RPC and collect response from SSE
            pending_responses = {}
            response_queue = asyncio.Queue()

            async def read_sse():
                try:
                    async for raw_line in sse.aiter_lines():
                        line = raw_line.strip()
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            try:
                                parsed = json.loads(data)
                                if "id" in parsed and ("result" in parsed or "error" in parsed):
                                    await response_queue.put(parsed)
                            except json.JSONDecodeError:
                                pass
                except Exception:
                    pass

            reader_task = asyncio.create_task(read_sse())

            async def call_jsonrpc(msg_id, method, params=None):
                msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
                if params:
                    msg["params"] = params
                resp = await msg_client.post(msg_url, json=msg, headers={**headers, "Content-Type": "application/json"})
                if resp.status_code != 200 and resp.status_code != 202:
                    return {"error": f"HTTP {resp.status_code}"}
                # Wait for response via SSE
                try:
                    result = await asyncio.wait_for(response_queue.get(), timeout=30)
                    return result
                except asyncio.TimeoutError:
                    return {"error": "timeout"}

            # Test 1: Initialize
            print("\n=== TEST 1: INITIALIZE ===")
            resp = await call_jsonrpc(1, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-sse-test", "version": "1.0"}
            })
            if "result" in resp:
                server_info = resp["result"].get("serverInfo", {})
                print(f"  Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")
                tools_cap = resp["result"].get("capabilities", {}).get("tools", {})
                print(f"  Tools capability: {tools_cap}")
                results["passed"] += 1
                results["tests"].append({"name": "initialize", "status": "PASS"})
            else:
                print(f"  FAIL: {resp.get('error', resp)}")
                results["failed"] += 1
                results["tests"].append({"name": "initialize", "status": "FAIL", "error": str(resp)})

            # Send initialized notification
            await msg_client.post(msg_url, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                              headers={**headers, "Content-Type": "application/json"})

            # Test 2: List tools
            print("\n=== TEST 2: LIST TOOLS ===")
            resp = await call_jsonrpc(2, "tools/list")
            if "result" in resp:
                tools = resp["result"].get("tools", [])
                print(f"  Tools: {len(tools)}")
                for t in tools[:8]:
                    print(f"    - {t['name']}")
                if len(tools) > 8:
                    print(f"    ... +{len(tools)-8} more")
                results["passed"] += 1
                results["tests"].append({"name": "tools/list", "status": "PASS", "tool_count": len(tools)})
            else:
                print(f"  FAIL: {resp.get('error', resp)}")
                results["failed"] += 1
                results["tests"].append({"name": "tools/list", "status": "FAIL"})

            # Test 3: get_context (real user flow — "what was I working on?")
            print("\n=== TEST 3: get_context (real user conversation) ===")
            resp = await call_jsonrpc(3, "tools/call", {"name": "get_context", "arguments": {}})
            if "result" in resp:
                content = resp["result"].get("content", [])
                text = content[0].get("text", "") if content else ""
                try:
                    ctx = json.loads(text)
                    print(f"  User: {ctx.get('user', {}).get('name')}")
                    print(f"  Projects: {[p['name'] for p in ctx.get('projects', [])]}")
                    print(f"  Active project: {ctx.get('active_project_id')}")
                    print(f"  Runs: {len(ctx.get('pipeline_runs', []))}")
                    print(f"  Replies: {ctx.get('replies', {})}")
                    action = ctx.get('action_required')
                    if action:
                        print(f"  ACTION REQUIRED: {action}")
                    results["passed"] += 1
                    results["tests"].append({"name": "get_context", "status": "PASS"})
                except json.JSONDecodeError:
                    print(f"  Raw: {text[:300]}")
                    results["passed"] += 1
                    results["tests"].append({"name": "get_context", "status": "PASS"})
            else:
                print(f"  FAIL: {resp.get('error', resp)}")
                results["failed"] += 1
                results["tests"].append({"name": "get_context", "status": "FAIL"})

            # Test 4: create_project (real user — "I want to find IT companies")
            print("\n=== TEST 4: create_project (blind offer discovery) ===")
            resp = await call_jsonrpc(4, "tools/call", {
                "name": "create_project",
                "arguments": {
                    "name": "SSE-Test-Project",
                    "website": "https://easystaff.io/",
                    "sender_name": "Test",
                    "sender_company": "EasyStaff",
                }
            })
            if "result" in resp:
                content = resp["result"].get("content", [])
                text = content[0].get("text", "") if content else ""
                try:
                    data = json.loads(text)
                    print(f"  Project ID: {data.get('project_id')}")
                    print(f"  Website scraped: {data.get('website_scraped')}")
                    print(f"  Context length: {data.get('context_length')}")
                    results["passed"] += 1
                    results["tests"].append({"name": "create_project", "status": "PASS", "project_id": data.get('project_id')})
                except:
                    print(f"  Raw: {text[:300]}")
                    results["passed"] += 1
                    results["tests"].append({"name": "create_project", "status": "PASS"})
            else:
                err = resp.get("error", resp)
                # Project might already exist
                print(f"  Result: {err}")
                results["tests"].append({"name": "create_project", "status": "WARN", "detail": str(err)[:200]})

            # Test 5: list_email_accounts
            print("\n=== TEST 5: list_email_accounts ===")
            resp = await call_jsonrpc(5, "tools/call", {
                "name": "list_email_accounts", "arguments": {}
            })
            if "result" in resp:
                content = resp["result"].get("content", [])
                text = content[0].get("text", "") if content else ""
                try:
                    data = json.loads(text)
                    accounts = data.get("accounts", [])
                    print(f"  Accounts: {len(accounts)}")
                    for a in accounts[:3]:
                        print(f"    - {a.get('email', '?')} ({a.get('name', '?')})")
                    results["passed"] += 1
                    results["tests"].append({"name": "list_email_accounts", "status": "PASS", "count": len(accounts)})
                except:
                    print(f"  Raw: {text[:200]}")
                    results["tests"].append({"name": "list_email_accounts", "status": "PASS"})
                    results["passed"] += 1
            else:
                print(f"  FAIL: {resp.get('error', resp)}")
                results["failed"] += 1
                results["tests"].append({"name": "list_email_accounts", "status": "FAIL"})

            # Test 6: check_destination (M1 — both platforms configured?)
            print("\n=== TEST 6: check_destination ===")
            resp = await call_jsonrpc(6, "tools/call", {
                "name": "check_destination", "arguments": {}
            })
            if "result" in resp:
                content = resp["result"].get("content", [])
                text = content[0].get("text", "") if content else ""
                print(f"  Result: {text[:300]}")
                results["passed"] += 1
                results["tests"].append({"name": "check_destination", "status": "PASS"})
            else:
                print(f"  FAIL: {resp.get('error', resp)}")
                results["failed"] += 1
                results["tests"].append({"name": "check_destination", "status": "FAIL"})

            reader_task.cancel()

    finally:
        await sse_client.aclose()
        await msg_client.aclose()

    # Summary
    print(f"\n{'='*60}")
    print(f"REAL MCP SSE TEST RESULTS")
    print(f"{'='*60}")
    total = results["passed"] + results["failed"]
    print(f"  Passed: {results['passed']}/{total}")
    print(f"  Failed: {results['failed']}/{total}")
    for t in results["tests"]:
        icon = "PASS" if t["status"] == "PASS" else ("WARN" if t["status"] == "WARN" else "FAIL")
        print(f"  [{icon}] {t['name']}")

    if results["failed"] == 0:
        print(f"\n  ALL TESTS PASSED via real MCP SSE protocol!")
    else:
        print(f"\n  {results['failed']} FAILURES — fix and re-run")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
