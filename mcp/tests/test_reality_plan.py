"""REALITY TEST PLAN — full flow via real MCP SSE.

Tests the EXACT flow from REALITY_TEST_PLAN_20260330.md:
Phase 1: Onboarding (login, keys)
Phase 2: Project setup (website, campaigns)
Phase 3: Gathering (filter preview, confirm, email accounts)
Phase 4: Pipeline (blacklist, checkpoint, classify, exploration)
Phase 5: Campaign (sequence, approve, push)
Phase 6: Post-launch (replies, context)

Max 20 Apollo credits per run. Uses real SSE, real Apollo, real scraping.

Run:
    cd mcp && python3 -u tests/test_reality_plan.py
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

import httpx

MCP_URL = "http://46.62.210.24:8002/mcp/sse"
API_URL = "http://46.62.210.24:8002"
TMP = Path(__file__).parent / "tmp"

# Use httpx timeout to prevent SSE disconnects on slow tools
SSE_TIMEOUT = 120  # seconds


async def call(mcp, tool, args):
    """Call MCP tool, return parsed JSON."""
    try:
        r = await asyncio.wait_for(mcp.call_tool(tool, arguments=args), timeout=SSE_TIMEOUT)
        text = r.content[0].text if r.content else "{}"
        try:
            return json.loads(text)
        except:
            return {"raw": text[:500]}
    except asyncio.TimeoutError:
        return {"error": f"timeout after {SSE_TIMEOUT}s"}
    except Exception as e:
        return {"error": str(e)[:200]}


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = []
    results = {}

    def l(msg):
        print(msg)
        log.append(msg)

    # Create fresh test user
    async with httpx.AsyncClient(timeout=10) as c:
        email = f"reality_{ts}@test.io"
        r = await c.post(f"{API_URL}/api/auth/signup",
            json={"email": email, "name": "RealityTest", "password": "testtest123"})
        token = r.json().get("api_token", "")

    l(f"REALITY TEST PLAN — {ts}")
    l(f"User: {email}")
    l("=" * 80)

    async with sse_client(MCP_URL, timeout=SSE_TIMEOUT) as (rs, ws):
        async with ClientSession(rs, ws) as mcp:
            await mcp.initialize()
            tools = await mcp.list_tools()
            l(f"Connected: {len(tools.tools)} tools")

            # ═══ PHASE 1: Onboarding ═══
            l("\n--- PHASE 1: Onboarding ---")

            # 1.2 Login
            d = await call(mcp, "login", {"token": token})
            ok = bool(d.get("user_id"))
            results["1.2_login"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 1.2 Login: {d.get('message','')[:60]}")

            # 1.3 Keys check
            d = await call(mcp, "check_integrations", {})
            ok = "missing_required" in d
            results["1.3_keys"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 1.3 Keys: missing={d.get('missing_required',[])}")

            # ═══ PHASE 2: Project Setup ═══
            l("\n--- PHASE 2: Project Setup ---")

            # 2.1 Create project from website
            d = await call(mcp, "create_project", {"name": "EasyStaff", "website": "https://easystaff.io"})
            pid = d.get("project_id")
            ok = bool(pid) and d.get("website_scraped")
            results["2.1_project"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 2.1 Project: id={pid}, scraped={d.get('website_scraped')}")
            next_q = d.get("next_question", "")
            l(f"   next_question: {next_q[:80]}")
            has_campaign_q = "campaign" in next_q.lower()
            results["2.1_asks_campaigns"] = has_campaign_q
            l(f"{'PASS' if has_campaign_q else 'FAIL'} 2.1b Asks about campaigns: {has_campaign_q}")

            # 2.2 Import previous campaigns
            d = await call(mcp, "import_smartlead_campaigns", {"project_id": pid, "rules": {"contains": ["petr"]}})
            imported = d.get("campaigns_imported", 0)
            ok = imported > 0
            results["2.2_campaigns"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 2.2 Import campaigns: {imported} imported")

            # ═══ PHASE 3: Gathering ═══
            l("\n--- PHASE 3: Gathering ---")

            # 3.1 Filter preview (NO credits spent)
            d = await call(mcp, "tam_gather", {
                "project_id": pid,
                "source_type": "apollo.companies.api",
                "query": "IT consulting companies in Miami",
                "filters": {"organization_num_employees_ranges": ["11,50", "51,200"], "per_page": 25, "max_pages": 1},
            })
            preview = d.get("status") == "awaiting_filter_confirmation"
            has_cost = "cost_estimate" in d
            has_next = "next_action" in d
            total_available = d.get("total_available", 0)
            cost = d.get("cost_estimate", {})
            results["3.1_preview"] = preview and has_cost
            l(f"{'PASS' if preview and has_cost else 'FAIL'} 3.1 Filter preview: total={total_available:,}, cost={cost.get('total_credits',0)} credits (${cost.get('total_cost_usd',0):.2f})")
            l(f"   keywords: {d.get('filters_preview',{}).get('q_organization_keyword_tags',[])[:4]}...")
            l(f"   has_next_action: {has_next}")

            # 3.2 Confirm + gather (spends credits — limit to 1 page = 1 credit)
            filters = d.get("next_action", {}).get("args", {}).get("filters", {})
            if not filters:
                filters = d.get("filters_preview", {})
                filters["per_page"] = 25
                filters["max_pages"] = 1
            d = await call(mcp, "tam_gather", {
                "project_id": pid,
                "source_type": "apollo.companies.api",
                "filters": filters,
                "confirm_filters": True,
            })
            run_id = d.get("run_id")
            ok = bool(run_id)
            results["3.2_gather"] = ok
            new_companies = d.get("new_companies", 0)
            credits = d.get("credits_used", 0)
            l(f"{'PASS' if ok else 'FAIL'} 3.2 Gather: run_id={run_id}, companies={new_companies}, credits={credits}")

            # 3.3 Email accounts
            d = await call(mcp, "list_email_accounts", {})
            accounts = d.get("accounts", [])
            ok = len(accounts) > 0
            results["3.3_accounts"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 3.3 Email accounts: {len(accounts)} found")

            # ═══ PHASE 4: Pipeline ═══
            l("\n--- PHASE 4: Pipeline ---")

            if run_id:
                # 4.1 Blacklist check
                d = await call(mcp, "tam_blacklist_check", {"run_id": run_id})
                gate_id = d.get("gate_id")
                ok = bool(gate_id)
                results["4.1_blacklist"] = ok
                l(f"{'PASS' if ok else 'FAIL'} 4.1 Blacklist: gate_id={gate_id}")
                has_next = "next_action" in d
                l(f"   has_next_action: {has_next}")

                # 4.2 Approve checkpoint 1
                if gate_id:
                    d = await call(mcp, "tam_approve_checkpoint", {"gate_id": gate_id})
                    ok = d.get("approved")
                    results["4.2_approve"] = ok
                    l(f"{'PASS' if ok else 'FAIL'} 4.2 Approve CP1: approved={ok}")
                    has_next = "next_action" in d
                    l(f"   has_next_action: {has_next}")

                # 4.2b Run remaining phases
                for phase_tool in ["tam_pre_filter", "tam_scrape", "tam_analyze"]:
                    d = await call(mcp, phase_tool, {"run_id": run_id})
                    l(f"   {phase_tool}: {json.dumps(d, default=str)[:100]}")

                # 4.3 Pipeline status
                d = await call(mcp, "pipeline_status", {"run_id": run_id})
                ok = "run_id" in d
                results["4.3_status"] = ok
                phase = d.get("phase", d.get("current_phase", "?"))
                targets = d.get("targets_found", 0)
                l(f"{'PASS' if ok else 'FAIL'} 4.3 Status: phase={phase}, targets={targets}")

                # 4.4 Exploration (5 enrichment credits)
                d = await call(mcp, "tam_explore", {"run_id": run_id})
                ok = "optimized_filters" in d or "exploration_stats" in d
                results["4.4_explore"] = ok
                l(f"{'PASS' if ok else 'FAIL'} 4.4 Exploration: {json.dumps(d, default=str)[:150]}")
            else:
                l("SKIP Phase 4 — no run_id")

            # ═══ PHASE 5: Campaign ═══
            l("\n--- PHASE 5: Campaign ---")

            # 5.1 Generate sequence
            d = await call(mcp, "smartlead_generate_sequence", {"project_id": pid})
            seq_id = d.get("sequence_id")
            ok = bool(seq_id)
            results["5.1_sequence"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 5.1 Sequence: id={seq_id}, steps={d.get('steps',0)}")

            if seq_id:
                # 5.1b Approve sequence
                d = await call(mcp, "smartlead_approve_sequence", {"sequence_id": seq_id})
                ok = d.get("approved")
                results["5.1b_approve_seq"] = ok
                l(f"{'PASS' if ok else 'FAIL'} 5.1b Approve sequence: {ok}")

                # 5.2 Push to SmartLead (need email accounts)
                account_ids = [a["id"] for a in accounts[:2]] if accounts else [17062361]
                d = await call(mcp, "smartlead_push_campaign", {"sequence_id": seq_id, "email_account_ids": account_ids})
                campaign_id = d.get("campaign_id")
                ok = bool(campaign_id) or "DRAFT" in str(d)
                results["5.2_push"] = ok
                l(f"{'PASS' if ok else 'FAIL'} 5.2 Push: {json.dumps(d, default=str)[:150]}")

            # ═══ PHASE 6: Post-launch ═══
            l("\n--- PHASE 6: Post-launch ---")

            # 6.1 Replies
            d = await call(mcp, "replies_summary", {"project_name": "EasyStaff"})
            ok = "total_replies" in d or "project" in d
            results["6.1_replies"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 6.1 Replies: {d.get('total_replies', 0)}")

            # 6.3 Session continuity
            d = await call(mcp, "get_context", {})
            ok = bool(d.get("projects"))
            results["6.3_context"] = ok
            l(f"{'PASS' if ok else 'FAIL'} 6.3 Context: projects={len(d.get('projects',[]))}")

    # ═══ SUMMARY ═══
    l("\n" + "=" * 80)
    passes = sum(1 for v in results.values() if v)
    total = len(results)
    l(f"RESULT: {passes}/{total} PASS ({passes/total*100:.0f}%)")
    for name, ok in results.items():
        l(f"  {'✅' if ok else '❌'} {name}")

    # Save
    out = TMP / f"{ts}_reality_test.log"
    out.write_text("\n".join(log))
    results_file = TMP / f"{ts}_reality_test.json"
    results_file.write_text(json.dumps({"ts": ts, "results": results, "passes": passes, "total": total}, indent=2))
    l(f"\nSaved: {out.name}")


if __name__ == "__main__":
    asyncio.run(main())
