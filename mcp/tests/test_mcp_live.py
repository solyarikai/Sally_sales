"""Live MCP connection test — connects like a real user via SSE.

Run:
    cd mcp && python3 -u tests/test_mcp_live.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
except ImportError:
    print("pip install mcp httpx-sse")
    sys.exit(1)

MCP_URL = "http://46.62.210.24:8002/mcp/sse"
TMP = Path(__file__).parent / "tmp"
TMP.mkdir(exist_ok=True)


async def get_token():
    import httpx
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post("http://46.62.210.24:8002/api/auth/signup",
            json={"email": f"live_{datetime.now().strftime('%H%M%S')}@test.io",
                  "name": "LiveTest", "password": "testtest123"})
        d = r.json()
        return d.get("api_token", "")


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = []

    def l(msg):
        print(msg)
        log.append(msg)

    token = await get_token()
    if not token:
        l("ERROR: Could not create test user")
        return

    l(f"MCP LIVE TEST — {ts}")
    l(f"Token: {token[:20]}...")
    l("=" * 80)

    async with sse_client(MCP_URL) as (rs, ws):
        async with ClientSession(rs, ws) as mcp:
            await mcp.initialize()
            tools = await mcp.list_tools()
            l(f"Connected: {len(tools.tools)} tools")

            results = {}

            # 1. Login
            r = await mcp.call_tool("login", arguments={"token": token})
            d = json.loads(r.content[0].text)
            results["login"] = "PASS" if d.get("user_id") else "FAIL"
            l(f"1. Login: {results['login']} — {d.get('message','')}")

            # 2. Check integrations
            r = await mcp.call_tool("check_integrations", arguments={})
            d = json.loads(r.content[0].text)
            results["integrations"] = "PASS"
            l(f"2. Integrations: PASS — missing: {d.get('missing_required',[])}")

            # 3. Create project from website
            r = await mcp.call_tool("create_project", arguments={
                "name": "LiveTestProject", "website": "https://easystaff.io"
            })
            d = json.loads(r.content[0].text)
            pid = d.get("project_id")
            results["create_project"] = "PASS" if pid else "FAIL"
            l(f"3. Create project: {results['create_project']} — id={pid}, scraped={d.get('website_scraped')}")
            l(f"   next_question: {d.get('next_question','')[:100]}")

            # 4. Filter preview (tam_gather without confirm)
            r = await mcp.call_tool("tam_gather", arguments={
                "project_id": pid,
                "source_type": "apollo.companies.api",
                "query": "IT consulting companies in Miami",
                "filters": {
                    "organization_num_employees_ranges": ["11,50", "51,200"],
                    "per_page": 25, "max_pages": 1
                },
                "target_count": 100,
            })
            d = json.loads(r.content[0].text)
            has_preview = d.get("status") == "awaiting_filter_confirmation"
            has_cost = "cost_estimate" in d
            results["filter_preview"] = "PASS" if has_preview and has_cost else "FAIL"
            cost = d.get("cost_estimate", {})
            l(f"4. Filter preview: {results['filter_preview']}")
            l(f"   total_available: {d.get('total_available',0):,}")
            l(f"   cost: {cost.get('total_credits',0)} credits (${cost.get('total_cost_usd',0)})")
            l(f"   keywords: {d.get('filters_preview',{}).get('q_organization_keyword_tags',[])[:5]}")
            l(f"   has_next_action: {'next_action' in d}")

            # 5. Get context
            r = await mcp.call_tool("get_context", arguments={})
            d = json.loads(r.content[0].text)
            results["get_context"] = "PASS" if d.get("projects") else "FAIL"
            l(f"5. Get context: {results['get_context']} — projects={len(d.get('projects',[]))}")

            # 6. Replies (empty for new project)
            r = await mcp.call_tool("replies_summary", arguments={"project_name": "LiveTestProject"})
            d = json.loads(r.content[0].text)
            results["replies"] = "PASS" if "total_replies" in d or "project" in d else "FAIL"
            l(f"6. Replies: {results['replies']} — {d.get('total_replies', 0)} replies")

            # 7. List email accounts
            r = await mcp.call_tool("list_email_accounts", arguments={})
            d = json.loads(r.content[0].text)
            results["email_accounts"] = "PASS" if "accounts" in d else "FAIL"
            l(f"7. Email accounts: {results['email_accounts']} — {len(d.get('accounts',[]))} accounts")

            # Summary
            passes = sum(1 for v in results.values() if v == "PASS")
            total = len(results)
            l(f"\nRESULT: {passes}/{total} PASS")
            for name, status in results.items():
                icon = "✅" if status == "PASS" else "❌"
                l(f"  {icon} {name}")

    out = TMP / f"{ts}_mcp_live_test.log"
    out.write_text("\n".join(log))
    print(f"\nSaved: {out.name}")


if __name__ == "__main__":
    asyncio.run(main())
