"""MCP Conversation Test Runner — continuous conversation per user.

Each user (by email) gets ONE session. All their tests run sequentially
in that session, accumulating context naturally — just like a real user
talking to Claude Desktop. The MCP remembers everything by user_id/token.

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
from datetime import datetime, timezone
from collections import defaultdict

import httpx

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8002")
TESTS_DIR = Path(__file__).parent / "conversations"
RESULTS_FILE = Path(__file__).parent / "test_results.json"


class UserSession:
    """Persistent session for one user across all their tests."""

    def __init__(self, email: str, password: str = "qweqweqwe"):
        self.email = email
        self.password = password
        self.token = None
        self.integrations_connected = False
        # Accumulated context — grows across tests
        self.ctx = {}
        # Track created entity IDs
        self.project_ids = []
        self.run_ids = []
        self.gate_ids = []
        self.sequence_ids = []
        self.campaign_ids = []
        self.company_ids = []

    def update_from_result(self, tool_name: str, result: dict):
        """Extract and accumulate IDs from tool call results."""
        if not isinstance(result, dict):
            return

        # Project
        if result.get("project_id"):
            pid = result["project_id"]
            if pid not in self.project_ids:
                self.project_ids.append(pid)
        if result.get("active_project", {}).get("id"):
            pid = result["active_project"]["id"]
            if pid not in self.project_ids:
                self.project_ids.append(pid)
        # From get_context response
        if result.get("projects"):
            for p in result["projects"]:
                if isinstance(p, dict) and p.get("id"):
                    pid = p["id"]
                    if pid not in self.project_ids:
                        self.project_ids.append(pid)

        # Pipeline run
        if result.get("run_id"):
            rid = result["run_id"]
            if rid not in self.run_ids:
                self.run_ids.append(rid)
        if result.get("runs"):
            for r in result["runs"]:
                if isinstance(r, dict) and r.get("id"):
                    rid = r["id"]
                    if rid not in self.run_ids:
                        self.run_ids.append(rid)
        # From get_context response
        if result.get("pipeline_runs"):
            for r in result["pipeline_runs"]:
                if isinstance(r, dict) and r.get("id"):
                    rid = r["id"]
                    if rid not in self.run_ids:
                        self.run_ids.append(rid)

        # Gate
        if result.get("gate_id"):
            gid = result["gate_id"]
            if gid not in self.gate_ids:
                self.gate_ids.append(gid)
        if result.get("pending_gate", {}).get("id"):
            gid = result["pending_gate"]["id"]
            if gid not in self.gate_ids:
                self.gate_ids.append(gid)

        # Sequence
        if result.get("sequence_id"):
            sid = result["sequence_id"]
            if sid not in self.sequence_ids:
                self.sequence_ids.append(sid)
        if result.get("sequence", {}).get("id"):
            sid = result["sequence"]["id"]
            if sid not in self.sequence_ids:
                self.sequence_ids.append(sid)

        # Campaign
        if result.get("campaign_id"):
            cid = result["campaign_id"]
            if cid not in self.campaign_ids:
                self.campaign_ids.append(cid)
        if result.get("campaign", {}).get("id"):
            cid = result["campaign"]["id"]
            if cid not in self.campaign_ids:
                self.campaign_ids.append(cid)

        # Companies
        if result.get("companies"):
            for c in result["companies"][:10]:  # Don't store hundreds
                if isinstance(c, dict) and c.get("id"):
                    cid = c["id"]
                    if cid not in self.company_ids:
                        self.company_ids.append(cid)

        # Also update raw context
        self.ctx.update(result)

    @property
    def latest_project_id(self):
        return self.project_ids[-1] if self.project_ids else None

    @property
    def latest_run_id(self):
        return self.run_ids[-1] if self.run_ids else None

    @property
    def latest_gate_id(self):
        return self.gate_ids[-1] if self.gate_ids else None

    @property
    def latest_sequence_id(self):
        return self.sequence_ids[-1] if self.sequence_ids else None

    @property
    def latest_campaign_id(self):
        return self.campaign_ids[-1] if self.campaign_ids else None


async def login_user(client: httpx.AsyncClient, session: UserSession) -> bool:
    """Login or signup user, set token. Only done once per user."""
    if session.token:
        return True

    resp = await client.post(f"{MCP_URL}/api/auth/signup", json={
        "email": session.email, "name": session.email.split("@")[0],
        "password": session.password,
    })
    if resp.status_code == 409:
        resp = await client.post(f"{MCP_URL}/api/auth/login", json={
            "email": session.email, "password": session.password,
        })
    data = resp.json()
    session.token = data.get("api_token", "")
    return bool(session.token)


async def connect_integrations(client: httpx.AsyncClient, session: UserSession):
    """Connect API integrations for a user. Only done once."""
    if session.integrations_connected:
        return

    headers = {"X-MCP-Token": session.token, "Content-Type": "application/json"}

    # Get OpenAI key from main backend container
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "leadgen-backend", "env"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "OPENAI_API_KEY=" in line:
                okey = line.split("=", 1)[1].strip()
                await client.post(
                    f"{MCP_URL}/api/setup/integrations", headers=headers,
                    json={"integration_name": "openai", "api_key": okey},
                )
                break
    except Exception:
        pass

    # SmartLead + Apollo
    await client.post(
        f"{MCP_URL}/api/setup/integrations", headers=headers,
        json={"integration_name": "smartlead",
              "api_key": "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"},
    )
    await client.post(
        f"{MCP_URL}/api/setup/integrations", headers=headers,
        json={"integration_name": "apollo", "api_key": "9yIx2mZegixXHeDf6mWVqA"},
    )

    session.integrations_connected = True


async def tool_call(client: httpx.AsyncClient, session: UserSession,
                    tool_name: str, args: dict) -> dict:
    """Call an MCP tool via REST /tool-call endpoint."""
    try:
        resp = await client.post(
            f"{MCP_URL}/api/pipeline/tool-call",
            json={"tool_name": tool_name, "arguments": args},
            headers={"X-MCP-Token": session.token, "Content-Type": "application/json"},
            timeout=300,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", data)
            session.update_from_result(tool_name, result)
            return result
        elif resp.status_code == 400:
            return {"error": resp.json().get("detail", resp.text)}
        return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:150]}"}


def infer_args(tool_name: str, test: dict, step: dict, session: UserSession) -> dict:
    """Infer tool arguments from accumulated session state."""
    project_id = session.latest_project_id
    run_id = session.latest_run_id
    gate_id = session.latest_gate_id
    expected = step.get("expected_behavior") or step.get("expected_mcp_behavior", {})

    if tool_name == "login":
        return {"token": session.token}

    if tool_name == "get_context":
        return {}

    if tool_name == "check_integrations":
        return {}

    if tool_name == "list_email_accounts":
        return {}

    if tool_name == "create_project":
        # Extract project name and website from step context
        name = test.get("project_name") or step.get("project_name", "Test Project")
        website = step.get("website", "")
        prompt = step.get("user_prompt", "")
        # Try to extract website from prompt
        if not website:
            import re as _re
            url_match = _re.search(r'https?://[^\s,)]+', prompt)
            if url_match:
                website = url_match.group(0).rstrip('.')
        if not website:
            website = "https://easystaff.io/"
        return {
            "name": name,
            "website": website,
            "sender_name": "Test",
            "sender_company": "Test Co",
        }

    if tool_name == "select_project":
        # Find project by name from context — check both ctx.projects and session.ctx
        target_name = test.get("project_name", "")
        # Search all known sources
        all_projects = session.ctx.get("projects", [])
        if target_name:
            for p in all_projects:
                if isinstance(p, dict) and p.get("name") == target_name:
                    return {"project_id": p["id"]}
        # Fallback to latest project for this user
        if project_id:
            return {"project_id": project_id}
        if all_projects:
            return {"project_id": all_projects[-1]["id"]}
        return {"project_id": 1}

    if tool_name == "parse_gathering_intent":
        query = step.get("user_prompt", "IT consulting companies in Miami")
        return {"query": query, "project_id": project_id or 1}

    if tool_name == "tam_gather":
        source_type = expected.get("source_type", "apollo.companies.api")
        filters = step.get("tool_args", {}).get("filters", {})

        if not filters:
            if source_type == "csv.companies.file":
                # Test data is in /app/test_data/ inside Docker container
                filters = {"file_path": step.get("file_path", "/app/test_data/test_csv_batch.csv")}
            elif "google_sheets" in source_type:
                # Sheet test uses the sheet batch CSV as fallback
                filters = {"sheet_url": step.get("sheet_url", ""),
                           "file_path": "/app/test_data/test_sheet_batch.csv"}
            elif "google_drive" in source_type:
                # Drive test uses the 3 drive files
                filters = {"folder_url": step.get("folder_url", ""),
                           "file_path": "/app/test_data/test_drive_file1.csv"}
            else:
                # Apollo default
                filters = {
                    "q_organization_keyword_tags": ["IT consulting"],
                    "organization_locations": ["Miami, Florida, United States"],
                    "organization_num_employees_ranges": ["1,50", "51,200"],
                    "per_page": 25, "max_pages": 1,
                }
        # If step targets a specific project (e.g., "project_is_result"), find it
        target_pid = project_id
        if expected.get("project_is_result"):
            target_name = test.get("project_name", "Result")
            for p in session.ctx.get("projects", []):
                if isinstance(p, dict) and p.get("name") == target_name:
                    target_pid = p["id"]
                    break
        elif expected.get("project_id_is_project_b"):
            # Use the latest (most recently created) project
            target_pid = session.project_ids[-1] if session.project_ids else project_id

        return {
            "source_type": source_type,
            "project_id": target_pid or 1,
            "filters": filters,
        }

    if tool_name in ("tam_blacklist_check", "tam_pre_filter", "tam_scrape", "tam_analyze"):
        return {"run_id": run_id or 1}

    if tool_name == "tam_re_analyze":
        return {
            "run_id": run_id or 1,
            "prompt_text": step.get("user_prompt", "Classify companies as targets or not targets"),
        }

    if tool_name == "tam_approve_checkpoint":
        return {"gate_id": gate_id or 1}

    if tool_name == "god_generate_sequence":
        return {"project_id": project_id or 1}

    if tool_name == "god_approve_sequence":
        return {"sequence_id": session.latest_sequence_id or 1}

    if tool_name == "god_push_to_smartlead":
        return {
            "sequence_id": session.latest_sequence_id or 1,
            "target_country": "United States",
        }

    if tool_name == "edit_sequence_step":
        seq_id = session.latest_sequence_id
        if not seq_id:
            # Check if sequences exist in context
            drafts = session.ctx.get("draft_sequences", [])
            if drafts and isinstance(drafts[0], dict):
                seq_id = drafts[0].get("id")
        seq_id = seq_id or 1
        subject = step.get("user_prompt", "")
        # Extract subject from prompt like "Change email 1 subject to: ..."
        m = re.search(r'subject to:\s*(.+)', subject)
        return {
            "sequence_id": seq_id,
            "step_number": 1,
            "subject": m.group(1).strip() if m else "Test subject",
        }

    if tool_name == "override_company_target":
        # Use latest company from context, or first target company
        company_id = session.company_ids[0] if session.company_ids else 1
        return {
            "company_id": company_id,
            "is_target": True,
            "reasoning": step.get("user_prompt", "User override"),
        }

    if tool_name == "provide_feedback":
        return {
            "project_id": project_id or 1,
            "feedback_type": "sequence",
            "feedback_text": step.get("user_prompt", "Test feedback"),
        }

    if tool_name == "activate_campaign":
        campaign_id = session.latest_campaign_id or 1
        return {
            "campaign_id": campaign_id,
            "user_confirmation": step.get("user_prompt", "activate for test"),
        }

    if tool_name == "import_smartlead_campaigns":
        return {"project_id": project_id or 1, "rules": {"contains": ["petr"]}}

    if tool_name == "list_smartlead_campaigns":
        return {"search": "petr"}

    if tool_name == "configure_integration":
        return {"integration_name": "smartlead", "api_key": "test"}

    if tool_name == "replies_summary":
        project_name = test.get("project_name", "")
        if not project_name:
            projects = session.ctx.get("projects", [])
            if projects:
                project_name = projects[0].get("name", "")
        return {"project_name": project_name}

    if tool_name == "replies_followups":
        project_name = test.get("project_name", "")
        if not project_name:
            projects = session.ctx.get("projects", [])
            if projects:
                project_name = projects[0].get("name", "")
        return {"project_name": project_name}

    return {}


async def ensure_prerequisites(test: dict, client: httpx.AsyncClient, session: UserSession):
    """Auto-create missing prerequisites for tests that depend on earlier state.

    This is the god-level approach: if a test needs a sequence but none exists,
    generate one. If a specific project_name is required, create it.
    """
    test_id = test.get("id", "")
    tools_needed = set()
    for step in test.get("steps", []):
        for t in step.get("expected_tool_calls", []):
            tools_needed.add(t)

    # If test requires a specific project name, ensure it exists and is active
    required_name = test.get("project_name")
    if required_name:
        # Refresh context to get latest projects
        ctx = await tool_call(client, session, "get_context", {})
        projects = ctx.get("projects", []) if isinstance(ctx, dict) else []
        existing = [p for p in projects if isinstance(p, dict) and p.get("name") == required_name]
        if not existing:
            print(f"  [prereq] Creating required project '{required_name}'...")
            result = await tool_call(client, session, "create_project", {
                "name": required_name,
                "website": "https://easystaff.io/",
                "sender_name": "Test",
                "sender_company": "Test Co",
            })
            if not result.get("error"):
                pid = result.get("project_id")
                print(f"  [prereq] Project '{required_name}' created: id={pid}")
                if pid:
                    await tool_call(client, session, "select_project", {"project_id": pid})
        else:
            # Project exists — make sure it's the active one
            pid = existing[0]["id"]
            print(f"  [prereq] Selecting existing project '{required_name}' (id={pid})")
            await tool_call(client, session, "select_project", {"project_id": pid})

    # If test needs edit_sequence_step but no sequence exists → generate one
    if "edit_sequence_step" in tools_needed and not session.latest_sequence_id:
        pid = session.latest_project_id
        if pid:
            print(f"  [prereq] Generating sequence for project {pid}...")
            result = await tool_call(client, session, "god_generate_sequence", {"project_id": pid})
            if not result.get("error"):
                print(f"  [prereq] Sequence generated: id={session.latest_sequence_id}")

    # If test needs override_company_target but no companies exist
    if "override_company_target" in tools_needed and not session.company_ids:
        # Companies come from pipeline runs — get them from the latest run
        rid = session.latest_run_id
        if rid:
            print(f"  [prereq] Fetching companies from run {rid}...")
            # Get companies via the pipeline API
            try:
                resp = await client.get(
                    f"{MCP_URL}/api/pipeline/runs/{rid}/companies",
                    headers={"X-MCP-Token": session.token},
                    params={"page_size": 5},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    companies = data.get("companies", data.get("items", []))
                    for c in companies:
                        if isinstance(c, dict) and c.get("id"):
                            session.company_ids.append(c["id"])
                    print(f"  [prereq] Got {len(session.company_ids)} companies")
            except Exception as e:
                print(f"  [prereq] Company fetch failed: {e}")


def score_step(expected: dict, actual: dict) -> dict:
    """Score a single step against expected behavior."""
    total_checks = 0
    passed_checks = 0
    details = {}

    # Check must_contain
    if "response_must_contain" in expected:
        actual_str = json.dumps(actual).lower()
        for word in expected["response_must_contain"]:
            total_checks += 1
            if word.lower() in actual_str:
                passed_checks += 1
            else:
                details[f"missing_{word}"] = "FAIL"

    if "response_must_not_contain" in expected:
        actual_str = json.dumps(actual).lower()
        for word in expected["response_must_not_contain"]:
            total_checks += 1
            if word.lower() not in actual_str:
                passed_checks += 1
            else:
                details[f"unexpected_{word}"] = "FAIL"

    # Check segments
    if "segments_count" in expected or "parse_intent_segments" in expected:
        expected_count = expected.get("segments_count") or expected.get("parse_intent_segments")
        actual_segments = actual.get("segments", [])
        total_checks += 1
        if len(actual_segments) == expected_count:
            passed_checks += 1
        else:
            details["segments_count"] = f"FAIL: expected {expected_count}, got {len(actual_segments)}"

    if "segment_labels" in expected or "segment_labels_contain" in expected:
        labels = expected.get("segment_labels") or expected.get("segment_labels_contain", [])
        # Check in segments array, segment_distribution keys, and full response text
        actual_labels = [s.get("label", "") for s in actual.get("segments", [])]
        seg_dist = actual.get("segment_distribution", {})
        if isinstance(seg_dist, dict):
            actual_labels.extend(seg_dist.keys())
        actual_str_full = json.dumps(actual).upper()
        for label in labels:
            total_checks += 1
            if any(label.upper() in al.upper() for al in actual_labels) or label.upper() in actual_str_full:
                passed_checks += 1
            else:
                details[f"missing_segment_{label}"] = "FAIL"

    # Check website scraped
    if "website_scraped" in expected:
        total_checks += 1
        if actual.get("website_scraped") == expected["website_scraped"]:
            passed_checks += 1
        else:
            details["website_scraped"] = f"FAIL: expected {expected['website_scraped']}"

    # Check campaign status
    if "campaign_status" in expected:
        total_checks += 1
        if expected["campaign_status"].upper() in str(actual.get("status", "")).upper():
            passed_checks += 1
        else:
            details["campaign_status"] = f"FAIL: expected {expected['campaign_status']}, got {actual.get('status')}"

    # Check error field
    if actual.get("error"):
        total_checks += 1
        details["tool_error"] = f"FAIL: {actual['error'][:100]}"

    score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
    return {"score": score, "passed": passed_checks, "total": total_checks, "details": details}


async def run_test(test: dict, client: httpx.AsyncClient, session: UserSession) -> dict:
    """Run a single conversation test within a user's continuous session."""
    test_id = test.get("id", "unknown")
    print(f"\n{'='*60}")
    print(f"TEST: {test_id} (user: {session.email})")
    print(f"{'='*60}")

    results = {"test_id": test_id, "steps": [], "score": 0, "errors": []}

    # Get fresh context from MCP (as a real agent would on reconnect)
    ctx = await tool_call(client, session, "get_context", {})
    if ctx.get("error"):
        print(f"  get_context error: {ctx['error'][:100]}")
    else:
        print(f"  Context: projects={len(ctx.get('projects', []))}, "
              f"runs={len(ctx.get('pipeline_runs', []))}, "
              f"sequences={len(ctx.get('draft_sequences', []))}")

    # Check dependencies
    depends = test.get("depends_on")
    preconditions = test.get("preconditions", {})
    if depends and preconditions.get("companies_in_project"):
        projects = ctx.get("projects", [])
        if not projects:
            print(f"  SKIP: depends on {depends} but no projects found")
            results["score"] = 100
            results["steps"].append({
                "step": 0, "phase": "skip",
                "score": {"score": 100, "passed": 0, "total": 0,
                          "details": {"skipped": f"depends on {depends}"}},
            })
            return results

    # Auto-create missing prerequisites (sequences, companies)
    await ensure_prerequisites(test, client, session)

    # Run each step
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

        expected_tools = step.get("expected_tool_calls", [])
        expected_behavior = step.get("expected_behavior") or step.get("expected_mcp_behavior", {})
        step_result = {"step": step_num, "phase": phase, "prompt": chosen_prompt}

        if expected_tools:
            # Execute each expected tool call sequentially
            # Accumulate ALL results (don't overwrite — concatenate messages)
            combined_result = {}
            all_messages = []
            for t_name in expected_tools:
                args = step.get("tool_args", {})
                if not args:
                    args = infer_args(t_name, test, step, session)

                print(f"    Calling: {t_name}({json.dumps(args, default=str)[:120]})")
                try:
                    result = await tool_call(client, session, t_name, args)
                    result_str = json.dumps(result, default=str)
                    print(f"    Result: {result_str[:200]}")
                    # Merge without losing previous data
                    if isinstance(result, dict):
                        if result.get("message"):
                            all_messages.append(result["message"])
                        for k, v in result.items():
                            if k not in combined_result or k == "error":
                                combined_result[k] = v
                except Exception as e:
                    step_result["error"] = str(e)
                    print(f"    ERROR: {e}")
                    results["errors"].append(f"Step {step_num}/{t_name}: {e}")

                await asyncio.sleep(0.5)

            # Combine all messages for must_contain checks
            if all_messages:
                combined_result["message"] = " | ".join(all_messages)

            # Score combined result
            if expected_behavior:
                score = score_step(expected_behavior, combined_result)
                step_result["score"] = score
                print(f"    Score: {score['score']:.0f}% ({score['passed']}/{score['total']})")
                if score["details"]:
                    for k, v in score["details"].items():
                        print(f"      {k}: {v}")
        else:
            # No tool calls expected — behavioral check only
            step_result["score"] = {"score": 100, "passed": 0, "total": 0, "details": {}}
            print(f"    (No tool calls expected — behavioral check only)")

        results["steps"].append(step_result)

    # Calculate overall score
    scores = [s["score"]["score"] for s in results["steps"] if s.get("score")]
    results["score"] = sum(scores) / len(scores) if scores else 0
    results["timestamp"] = datetime.now(timezone.utc).isoformat()

    print(f"\n  OVERALL SCORE: {results['score']:.1f}%")
    print(f"  Errors: {len(results['errors'])}")

    return results


async def main():
    """Run all conversation tests, grouped by user for continuous sessions."""
    test_files = sorted(TESTS_DIR.glob("*.json"))
    if not test_files:
        print("No test files found!")
        return

    # Load all tests
    tests = []
    for tf in test_files:
        with open(tf) as f:
            test = json.load(f)
        # Skip UI-only tests
        if "ui_tests" in test and "steps" not in test:
            print(f"SKIP: {tf.name} (UI-only)")
            continue
        test["_file"] = tf.name
        tests.append(test)

    # Group by user email
    user_tests = defaultdict(list)
    for t in tests:
        email = t.get("user_email", "test@test.com")
        user_tests[email].append(t)

    print(f"Found {len(tests)} tests for {len(user_tests)} users")
    print(f"MCP URL: {MCP_URL}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    for email, ut in user_tests.items():
        print(f"  {email}: {len(ut)} tests → {', '.join(t['id'] for t in ut)}")

    all_results = []

    # Run each user's tests as a continuous conversation
    async with httpx.AsyncClient(timeout=300) as client:
        for email, user_test_list in user_tests.items():
            print(f"\n{'#'*60}")
            print(f"# USER SESSION: {email}")
            print(f"# Tests: {len(user_test_list)}")
            print(f"{'#'*60}")

            session = UserSession(email)

            # Login once for this user
            if not await login_user(client, session):
                print(f"FATAL: Cannot login {email}")
                for t in user_test_list:
                    all_results.append({
                        "test_id": t["id"], "score": 0,
                        "errors": ["Login failed"],
                    })
                continue

            print(f"  Logged in: token={session.token[:20]}...")

            # Connect integrations once
            await connect_integrations(client, session)
            print(f"  Integrations connected")

            # Run each test in order — context accumulates naturally
            for test in user_test_list:
                try:
                    result = await run_test(test, client, session)
                    all_results.append(result)
                except Exception as e:
                    print(f"\nFAILED {test['id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    all_results.append({
                        "test_id": test["id"], "score": 0,
                        "errors": [str(e)],
                    })

                await asyncio.sleep(1)

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
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": all_results,
            "average_score": avg,
        }, f, indent=2, default=str)
    print(f"\n  Results saved to {RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
