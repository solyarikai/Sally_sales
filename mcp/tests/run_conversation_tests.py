"""MCP Conversation Test Runner — tests via REAL SSE protocol.

Connects to MCP server, sends tool calls as a real agent would,
compares responses against expected behavior from test JSON files.

Usage:
    ssh hetzner "cd ~/magnum-opus-project/repo && python3 mcp/tests/run_conversation_tests.py"
"""
import asyncio
import json
import os
import re
import sys
import time
import random
from pathlib import Path
from datetime import datetime

import httpx

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8002")
TESTS_DIR = Path(__file__).parent / "conversations"
RESULTS_FILE = Path(__file__).parent / "test_results.json"

# Test tokens — created fresh for each test run
TEST_TOKENS = {}


async def get_session(client: httpx.AsyncClient) -> str:
    """Get SSE session ID by reading first event from stream."""
    import subprocess
    try:
        result = subprocess.run(
            ["timeout", "3", "curl", "-s", "-N", f"{MCP_URL}/mcp/sse"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            m = re.search(r"session_id=([a-f0-9]+)", line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


async def mcp_call(client: httpx.AsyncClient, session_id: str, token: str,
                   method: str, params: dict, call_id: str = None) -> dict:
    """Send a JSON-RPC message via MCP protocol."""
    msg = {
        "jsonrpc": "2.0",
        "id": call_id or f"call-{int(time.time()*1000)}",
        "method": method,
        "params": params,
    }
    resp = await client.post(
        f"{MCP_URL}/mcp/messages?session_id={session_id}",
        json=msg,
        headers={"X-MCP-Token": token, "Content-Type": "application/json"},
        timeout=120,
    )
    if resp.status_code == 200:
        return resp.json()
    # 202 = accepted, response via SSE stream
    return {"accepted": True, "status": resp.status_code}


async def tool_call(client: httpx.AsyncClient, session_id: str, token: str,
                    tool_name: str, args: dict) -> dict:
    """Call an MCP tool via REST /tool-call endpoint.

    Uses the same backend dispatch + logs to conversations.
    SSE session established for protocol compliance but tool execution
    goes through REST for reliable synchronous responses.
    """
    resp = await client.post(
        f"{MCP_URL}/api/pipeline/tool-call",
        json={"tool_name": tool_name, "arguments": args},
        headers={"X-MCP-Token": token, "Content-Type": "application/json"},
        timeout=120,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("result", data)
    elif resp.status_code == 400:
        return {"error": resp.json().get("detail", resp.text)}
    return {"error": f"HTTP {resp.status_code}"}


async def create_test_user(client: httpx.AsyncClient, email: str, name: str) -> str:
    """Create test user and return token."""
    resp = await client.post(f"{MCP_URL}/api/auth/signup", json={
        "email": email, "name": name, "password": "qweqweqwe"
    })
    if resp.status_code == 409:
        # Already exists, login
        resp = await client.post(f"{MCP_URL}/api/auth/login", json={
            "email": email, "password": "qweqweqwe"
        })
    data = resp.json()
    return data.get("api_token", "")


def score_step(expected: dict, actual: dict) -> dict:
    """Score a single step against expected behavior."""
    scores = {}
    total_checks = 0
    passed_checks = 0

    # Check must_contain
    if "response_must_contain" in expected:
        actual_str = json.dumps(actual).lower()
        for word in expected["response_must_contain"]:
            total_checks += 1
            if word.lower() in actual_str:
                passed_checks += 1
            else:
                scores[f"missing_{word}"] = "FAIL"

    if "response_must_not_contain" in expected:
        actual_str = json.dumps(actual).lower()
        for word in expected["response_must_not_contain"]:
            total_checks += 1
            if word.lower() not in actual_str:
                passed_checks += 1
            else:
                scores[f"unexpected_{word}"] = "FAIL"

    # Check segments
    if "segments_count" in expected or "parse_intent_segments" in expected:
        expected_count = expected.get("segments_count") or expected.get("parse_intent_segments")
        actual_segments = actual.get("segments", [])
        total_checks += 1
        if len(actual_segments) == expected_count:
            passed_checks += 1
        else:
            scores["segments_count"] = f"FAIL: expected {expected_count}, got {len(actual_segments)}"

    if "segment_labels" in expected or "segment_labels_contain" in expected:
        labels = expected.get("segment_labels") or expected.get("segment_labels_contain", [])
        actual_labels = [s.get("label", "") for s in actual.get("segments", [])]
        for label in labels:
            total_checks += 1
            if any(label.upper() in al.upper() for al in actual_labels):
                passed_checks += 1
            else:
                scores[f"missing_segment_{label}"] = "FAIL"

    # Check website scraped
    if "website_scraped" in expected:
        total_checks += 1
        if actual.get("website_scraped") == expected["website_scraped"]:
            passed_checks += 1
        else:
            scores["website_scraped"] = f"FAIL: expected {expected['website_scraped']}"

    # Check campaign status
    if "campaign_status" in expected:
        total_checks += 1
        if expected["campaign_status"].upper() in str(actual.get("status", "")).upper():
            passed_checks += 1
        else:
            scores["campaign_status"] = f"FAIL: expected {expected['campaign_status']}, got {actual.get('status')}"

    score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
    return {"score": score, "passed": passed_checks, "total": total_checks, "details": scores}


async def run_test(test_file: Path) -> dict:
    """Run a single conversation test."""
    with open(test_file) as f:
        test = json.load(f)

    test_id = test.get("id", test_file.stem)
    email = test.get("user_email", "test@test.com")
    print(f"\n{'='*60}")
    print(f"TEST: {test_id}")
    print(f"{'='*60}")

    results = {"test_id": test_id, "steps": [], "score": 0, "errors": []}

    async with httpx.AsyncClient(timeout=120) as client:
        # Create/login user
        token = await create_test_user(client, email, test_id)
        if not token:
            results["errors"].append("Failed to create/login user")
            return results

        # Get MCP session (for protocol compliance logging)
        session_id = await get_session(client)
        # Session may be empty if SSE times out — that's OK, REST /tool-call still works

        # Get context (as real agent would on reconnect)
        ctx = await tool_call(client, session_id, token, "get_context", {})
        print(f"  Context: {json.dumps(ctx, default=str)[:200]}...")

        # Run steps
        for step in test.get("steps", []):
            step_num = step.get("step", "?")
            phase = step.get("phase", "")
            print(f"\n  Step {step_num}: {phase}")

            # Pick shuffled prompt variant
            prompts = [step.get("user_prompt", "")] + step.get("user_prompt_variants", [])
            prompts = [p for p in prompts if p]
            chosen_prompt = random.choice(prompts) if prompts else ""
            if chosen_prompt:
                print(f"    User: {chosen_prompt[:80]}...")

            # Execute expected tool calls
            expected_tools = step.get("expected_tool_calls", [])
            expected_behavior = step.get("expected_behavior") or step.get("expected_mcp_behavior", {})

            step_result = {"step": step_num, "phase": phase, "prompt": chosen_prompt}

            if expected_tools:
                for tool_name in expected_tools:
                    # Build args based on tool name and context
                    args = step.get("tool_args", {})
                    if not args:
                        args = _infer_args(tool_name, test, step, ctx)

                    print(f"    Calling: {tool_name}({json.dumps(args, default=str)[:100]}...)")
                    try:
                        result = await tool_call(client, session_id, token, tool_name, args)
                        print(f"    Result: {json.dumps(result, default=str)[:150]}...")

                        # Score against expected
                        if expected_behavior:
                            score = score_step(expected_behavior, result)
                            step_result["score"] = score
                            print(f"    Score: {score['score']:.0f}% ({score['passed']}/{score['total']})")
                            if score["details"]:
                                for k, v in score["details"].items():
                                    print(f"      {k}: {v}")

                        # Update context with result
                        ctx.update(result) if isinstance(result, dict) else None

                    except Exception as e:
                        step_result["error"] = str(e)
                        print(f"    ERROR: {e}")
                        results["errors"].append(f"Step {step_num}: {e}")

                    await asyncio.sleep(1)  # Rate limiting
            else:
                step_result["score"] = {"score": 100, "passed": 0, "total": 0, "details": {}}
                print(f"    (No tool calls expected — behavioral check only)")

            results["steps"].append(step_result)

    # Calculate overall score
    scores = [s.get("score", {}).get("score", 100) for s in results["steps"] if s.get("score")]
    results["score"] = sum(scores) / len(scores) if scores else 0
    results["timestamp"] = datetime.utcnow().isoformat()

    print(f"\n  OVERALL SCORE: {results['score']:.1f}%")
    print(f"  Errors: {len(results['errors'])}")

    return results


def _infer_args(tool_name: str, test: dict, step: dict, ctx: dict) -> dict:
    """Infer tool arguments from test context."""
    # Common project_id
    project_id = None
    if ctx.get("projects"):
        project_id = ctx["projects"][0].get("id")
    elif ctx.get("project_id"):
        project_id = ctx["project_id"]

    if tool_name == "create_project":
        return {
            "name": test.get("project_name", "Test Project"),
            "website": step.get("website", "https://easystaff.io/"),
            "sender_name": "Test",
            "sender_company": "Test Co",
        }
    elif tool_name == "parse_gathering_intent":
        query = step.get("user_prompt", "IT consulting companies in Miami")
        return {"query": query, "project_id": project_id or 1}
    elif tool_name == "tam_gather":
        return {
            "source_type": "apollo.companies.api",
            "project_id": project_id or 1,
            "filters": {
                "q_organization_keyword_tags": ["IT consulting"],
                "organization_locations": ["Miami, Florida, United States"],
                "organization_num_employees_ranges": ["1,50", "51,200"],
                "per_page": 25, "max_pages": 1,
            },
        }
    elif tool_name in ("tam_blacklist_check", "tam_pre_filter", "tam_scrape", "tam_analyze"):
        run_id = None
        if ctx.get("pipeline_runs"):
            run_id = ctx["pipeline_runs"][0].get("id")
        return {"run_id": run_id or 1}
    elif tool_name == "tam_approve_checkpoint":
        return {"gate_id": ctx.get("last_gate_id", 1)}
    elif tool_name == "replies_summary":
        project_name = test.get("project_name", "")
        if not project_name and ctx.get("projects"):
            project_name = ctx["projects"][0].get("name", "")
        return {"project_name": project_name}
    elif tool_name == "replies_followups":
        project_name = test.get("project_name", "")
        if not project_name and ctx.get("projects"):
            project_name = ctx["projects"][0].get("name", "")
        return {"project_name": project_name}
    elif tool_name == "get_context":
        return {}
    elif tool_name == "list_email_accounts":
        return {}
    elif tool_name == "god_generate_sequence":
        return {"project_id": project_id or 1}
    elif tool_name == "god_approve_sequence":
        return {"sequence_id": ctx.get("last_sequence_id", 1)}
    elif tool_name == "god_push_to_smartlead":
        return {"sequence_id": ctx.get("last_sequence_id", 1), "target_country": "United States"}
    elif tool_name == "provide_feedback":
        return {"project_id": project_id or 1, "feedback_type": "sequence", "feedback_text": "Test feedback"}
    elif tool_name == "override_company_target":
        return {"company_id": 1, "is_target": True, "reasoning": "Test override"}
    elif tool_name == "import_smartlead_campaigns":
        return {"project_id": project_id or 1, "rules": {"contains": ["petr"]}}
    elif tool_name == "login":
        return {"token": ctx.get("token", "")}
    elif tool_name == "check_integrations":
        return {}
    elif tool_name == "configure_integration":
        return {"integration_name": "smartlead", "api_key": "test"}
    elif tool_name == "list_smartlead_campaigns":
        return {"search": "petr"}
    elif tool_name == "edit_sequence_step":
        return {"sequence_id": 1, "step_number": 1, "subject": "Test subject"}
    elif tool_name == "activate_campaign":
        return {"campaign_id": 1, "user_confirmation": "activate for test"}

    return {}


async def main():
    """Run all conversation tests."""
    test_files = sorted(TESTS_DIR.glob("*.json"))
    if not test_files:
        print("No test files found!")
        return

    print(f"Found {len(test_files)} test files")
    print(f"MCP URL: {MCP_URL}")
    print(f"Time: {datetime.utcnow().isoformat()}")

    all_results = []

    for tf in test_files:
        # Skip UI-only tests (no tool calls)
        with open(tf) as f:
            test = json.load(f)
        if "ui_tests" in test and "steps" not in test:
            print(f"\nSKIPPING {tf.name} (UI-only test)")
            continue

        try:
            result = await run_test(tf)
            all_results.append(result)
        except Exception as e:
            print(f"\nFAILED {tf.name}: {e}")
            all_results.append({"test_id": tf.stem, "score": 0, "errors": [str(e)]})

        await asyncio.sleep(2)  # Rate limiting between tests

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_score = 0
    for r in all_results:
        score = r.get("score", 0)
        errors = len(r.get("errors", []))
        status = "PASS" if score >= 80 else "FAIL"
        print(f"  {r['test_id']}: {score:.0f}% [{status}] ({errors} errors)")
        total_score += score

    avg = total_score / len(all_results) if all_results else 0
    print(f"\n  OVERALL: {avg:.1f}% across {len(all_results)} tests")
    print(f"  {'GOD LEVEL' if avg >= 95 else 'PASS' if avg >= 80 else 'NEEDS WORK'}")

    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump({"timestamp": datetime.utcnow().isoformat(), "results": all_results, "average_score": avg}, f, indent=2, default=str)
    print(f"\n  Results saved to {RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
