"""Test MCP flow via real SSE protocol. Measures performance."""
import httpx
import json
import time
import asyncio
import sys

MCP_BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""


async def wait_for_id(events_q, msg_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(events_q.get(), timeout=5)
            try:
                d = json.loads(raw)
                if d.get("id") == msg_id:
                    return d
            except json.JSONDecodeError:
                pass
        except asyncio.TimeoutError:
            pass
    return None


async def sse_reader(client, url, q):
    try:
        async with client.stream("GET", url) as sse:
            async for line in sse.aiter_lines():
                if line.startswith("data: "):
                    await q.put(line[6:])
    except Exception:
        pass


async def main():
    q = asyncio.Queue()
    async with httpx.AsyncClient(timeout=60) as client:
        task = asyncio.create_task(sse_reader(client, f"{MCP_BASE}/mcp/sse", q))
        session_path = await asyncio.wait_for(q.get(), timeout=5)
        url = f"{MCP_BASE}{session_path}"
        headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
        print(f"Session: {session_path}")

        # Initialize
        t0 = time.monotonic()
        await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "perf", "version": "1.0"}}})
        r = await wait_for_id(q, 1)
        t1 = time.monotonic()
        si = r["result"]["serverInfo"] if r else {}
        print(f"Init: {si.get('name')} v{si.get('version')} — {(t1-t0)*1000:.0f}ms")

        await client.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"})

        # Tools
        await client.post(url, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        r = await wait_for_id(q, 2)
        t2 = time.monotonic()
        tcount = len(r["result"]["tools"]) if r else 0
        print(f"Tools: {tcount} — {(t2-t1)*1000:.0f}ms")

        # list_smartlead_campaigns
        print("\n=== list_smartlead_campaigns (search: petr) ===")
        t3 = time.monotonic()
        await client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_smartlead_campaigns", "arguments": {"search": "petr"}}})
        r = await wait_for_id(q, 3)
        t4 = time.monotonic()
        if r:
            text = r.get("result", {}).get("content", [{}])[0].get("text", "{}")
            c = json.loads(text)
            camps = c.get("campaigns", [])
            total_leads = sum(x.get("leads", 0) for x in camps)
            print(f"  {c.get('total', len(camps))} campaigns, {total_leads} total leads")
            for x in camps[:10]:
                print(f"  {x.get('name','?')} — {x.get('leads',0)} leads — {x.get('status','?')}")
            if len(camps) > 10:
                print(f"  ... +{len(camps)-10} more")
        else:
            print("  ERROR: no response")
        print(f"  LATENCY: {(t4-t3)*1000:.0f}ms")

        # import_smartlead_campaigns
        print("\n=== import_smartlead_campaigns (contains: Petr) ===")
        t5 = time.monotonic()
        await client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "import_smartlead_campaigns", "arguments": {"project_id": 3, "rules": {"contains": ["Petr"]}}}})
        r = await wait_for_id(q, 4)
        t6 = time.monotonic()
        if r:
            text = r.get("result", {}).get("content", [{}])[0].get("text", "{}")
            c = json.loads(text)
            print(f"  Imported: {c.get('campaigns_imported', 0)} campaigns")
            print(f"  Blacklist: {c.get('contacts_in_blacklist', 0)} contacts")
        else:
            print("  ERROR: no response")
        print(f"  LATENCY: {(t6-t5)*1000:.0f}ms")

        print(f"\n=== TOTAL: {(t6-t0)*1000:.0f}ms ===")
        task.cancel()


asyncio.run(main())
