"""Real Conversation Test Runner — launches claude --print agents with MCP SSE.

NOT tool-call scripts. Real Claude agents that DECIDE which tools to call
based on natural language prompts. 2 parallel agents, 1 per test user.

Usage:
    cd mcp && python3 tests/run_real_conversation_tests.py
    cd mcp && python3 tests/run_real_conversation_tests.py --user pn@getsally.io
"""
import asyncio
import json
import os
import sys
import subprocess
import random
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

TESTS_DIR = Path(__file__).parent / "conversations"
RESULTS_DIR = Path(__file__).parent / "real_test_results"
MCP_SERVER_NAME = "magnum-opus-test"
MCP_SSE_URL = "http://46.62.210.24:8002/mcp/sse"

# Safety
if os.path.exists(os.path.expanduser("~/magnum-opus-project")):
    print("ERROR: Do NOT run on Hetzner! Run from your local machine.")
    sys.exit(1)


def ensure_mcp_server():
    """Ensure MCP server is registered in Claude Code."""
    result = subprocess.run(
        ["claude", "mcp", "list"], capture_output=True, text=True, timeout=10
    )
    if MCP_SERVER_NAME in result.stdout:
        print(f"MCP server '{MCP_SERVER_NAME}' already registered")
        return True

    print(f"Registering MCP server '{MCP_SERVER_NAME}'...")
    result = subprocess.run(
        ["claude", "mcp", "add", "--transport", "sse", MCP_SERVER_NAME, MCP_SSE_URL],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"  Registered: {MCP_SSE_URL}")
        return True
    else:
        print(f"  Failed: {result.stderr}")
        return False


def build_conversation_prompt(tests: list, email: str) -> str:
    """Build a natural language prompt from conversation test JSON files.

    The prompt tells the agent WHO they are, WHAT to test, and HOW to report results.
    The agent then DECIDES which MCP tools to call — that's the real test.
    """
    lines = [
        f"You are testing the GTM MCP system as user {email}.",
        f"You have access to the MCP server '{MCP_SERVER_NAME}' with 50+ tools.",
        "",
        "RULES:",
        "- Call MCP tools to test each step below",
        "- Report the result of EVERY tool call (tool name, args summary, result summary)",
        "- If a step fails, report the error and continue to the next step",
        "- NEVER create real campaigns — DRAFT only",
        "- NEVER activate campaigns unless the test explicitly says to",
        "",
        "TEST STEPS:",
        "",
    ]

    step_num = 0
    for test in tests:
        test_id = test.get("id", "unknown")
        lines.append(f"--- TEST: {test_id} ---")
        lines.append(f"Description: {test.get('description', '')[:200]}")

        for step in test.get("steps", []):
            step_num += 1
            phase = step.get("phase", "")
            # Pick a random prompt variant for natural conversation
            prompts = [step.get("user_prompt", "")] + step.get("user_prompt_variants", [])
            prompts = [p for p in prompts if p]
            chosen = random.choice(prompts) if prompts else ""

            expected_tools = step.get("expected_tool_calls", [])
            expected = step.get("expected_behavior", {})

            lines.append(f"\nStep {step_num} ({phase}):")
            if chosen:
                lines.append(f'  User says: "{chosen}"')
            if expected_tools:
                lines.append(f"  Expected tools: {', '.join(expected_tools)}")
            if expected.get("response_must_contain"):
                lines.append(f"  Response must contain: {expected['response_must_contain']}")
            if expected.get("response_must_contain_any"):
                lines.append(f"  Response must contain any of: {expected['response_must_contain_any']}")
            if step.get("critical_requirement"):
                lines.append(f"  CRITICAL: {step['critical_requirement'][:200]}")

        lines.append("")

    lines.extend([
        "",
        "After completing ALL steps, provide a summary:",
        "1. Total steps attempted",
        "2. Steps passed (tool called successfully, response matched expectations)",
        "3. Steps failed (with error details)",
        "4. Overall assessment: PASS (>=80%) or FAIL",
        "",
        "Format each step result as:",
        "STEP N: [PASS/FAIL] tool_name → result_summary",
    ])

    return "\n".join(lines)


async def run_agent(email: str, tests: list) -> dict:
    """Launch a claude --print agent with the conversation prompt."""
    prompt = build_conversation_prompt(tests, email)
    safe_email = email.replace("@", "_at_").replace(".", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save prompt for debugging
    RESULTS_DIR.mkdir(exist_ok=True)
    prompt_file = RESULTS_DIR / f"prompt_{safe_email}_{timestamp}.txt"
    prompt_file.write_text(prompt)

    print(f"\n{'='*60}")
    print(f"LAUNCHING AGENT: {email}")
    print(f"Tests: {len(tests)} conversations, {sum(len(t.get('steps',[])) for t in tests)} steps")
    print(f"Prompt: {len(prompt)} chars → {prompt_file.name}")
    print(f"{'='*60}")

    # Launch claude --print with the prompt
    output_file = RESULTS_DIR / f"output_{safe_email}_{timestamp}.txt"

    try:
        process = await asyncio.create_subprocess_exec(
            "claude", "--print", "--dangerously-skip-permissions",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode()),
            timeout=600  # 10 minutes max per agent
        )

        output = stdout.decode()
        errors = stderr.decode()

        # Save output
        output_file.write_text(output)
        if errors:
            (RESULTS_DIR / f"stderr_{safe_email}_{timestamp}.txt").write_text(errors)

        print(f"\n  Agent {email} completed ({len(output)} chars output)")
        print(f"  Output saved: {output_file.name}")

        # Parse results from output
        passed = output.lower().count("[pass]") + output.lower().count("pass")
        failed = output.lower().count("[fail]") + output.lower().count("fail")
        total = passed + failed

        return {
            "email": email,
            "tests_count": len(tests),
            "output_file": str(output_file),
            "output_length": len(output),
            "passed": passed,
            "failed": failed,
            "total_steps": total,
            "score": (passed / total * 100) if total > 0 else 0,
            "output_preview": output[:500],
            "timestamp": timestamp,
        }

    except asyncio.TimeoutError:
        print(f"\n  Agent {email} TIMED OUT after 10 minutes")
        return {
            "email": email, "tests_count": len(tests),
            "error": "Timeout after 600s", "score": 0,
        }
    except FileNotFoundError:
        print(f"\n  ERROR: 'claude' command not found. Install Claude Code CLI.")
        return {
            "email": email, "tests_count": len(tests),
            "error": "claude CLI not found", "score": 0,
        }
    except Exception as e:
        print(f"\n  Agent {email} ERROR: {e}")
        return {
            "email": email, "tests_count": len(tests),
            "error": str(e), "score": 0,
        }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Real MCP Conversation Test Runner")
    parser.add_argument("--user", help="Run tests for specific user only")
    args = parser.parse_args()

    # Check claude CLI exists
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        print(f"Claude Code: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: 'claude' CLI not found. Install from https://claude.ai/code")
        sys.exit(1)

    # Ensure MCP server registered
    if not ensure_mcp_server():
        print("WARNING: Could not register MCP server. Tests may fail.")

    # Load conversation tests
    tests = []
    for tf in sorted(TESTS_DIR.glob("*.json")):
        with open(tf) as f:
            try:
                test = json.load(f)
            except json.JSONDecodeError:
                continue
        if "steps" not in test or not test["steps"]:
            continue
        tests.append(test)

    # Group by user
    user_tests = defaultdict(list)
    for t in tests:
        email = t.get("user_email", "test@test.com")
        user_tests[email].append(t)

    if args.user:
        if args.user in user_tests:
            user_tests = {args.user: user_tests[args.user]}
        else:
            print(f"ERROR: User {args.user} not found. Available: {list(user_tests.keys())}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"REAL MCP CONVERSATION TESTS")
    print(f"Method: claude --print with MCP SSE connection")
    print(f"Server: {MCP_SSE_URL}")
    print(f"Users: {len(user_tests)}")
    for email, ut in user_tests.items():
        total_steps = sum(len(t.get("steps", [])) for t in ut)
        print(f"  {email}: {len(ut)} conversations, {total_steps} steps")
    print(f"{'='*60}")

    # Launch ALL users in PARALLEL
    tasks = [run_agent(email, ut) for email, ut in user_tests.items()]
    results = await asyncio.gather(*tasks)

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS — REAL CONVERSATION TESTS")
    print(f"{'='*60}")

    total_score = 0
    for r in results:
        score = r.get("score", 0)
        status = "PASS" if score >= 80 else "FAIL"
        error = r.get("error", "")
        print(f"  {r['email']}: {score:.0f}% [{status}]"
              + (f" — {error}" if error else f" — {r.get('passed',0)} passed, {r.get('failed',0)} failed"))
        total_score += score

    avg = total_score / len(results) if results else 0
    print(f"\n  OVERALL: {avg:.1f}%")
    print(f"  {'GOD LEVEL' if avg >= 95 else 'PASS' if avg >= 80 else 'NEEDS WORK'}")

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    results_file = RESULTS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": "claude --print with MCP SSE (real conversation)",
            "server": MCP_SSE_URL,
            "results": results,
            "average_score": avg,
        }, f, indent=2, default=str)
    print(f"\n  Results: {results_file}")
    print(f"  Agent outputs: {RESULTS_DIR}/output_*.txt")


if __name__ == "__main__":
    asyncio.run(main())
