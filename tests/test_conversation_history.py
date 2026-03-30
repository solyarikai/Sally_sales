#!/usr/bin/env python3
"""
Test: Conversation History API vs SmartLead Source of Truth
==========================================================
Verifies that our /api/replies/{reply_id}/conversation endpoint returns
conversation data that matches (or exceeds) what SmartLead's native API
returns.

Test 1 -- Julia Makutu (known data, 8 SmartLead messages)
Test 2 -- Dynamic meeting_request replies from project 40

Usage:
    python3 tests/test_conversation_history.py
"""

import sys
import json
import requests
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOCAL_API = "http://localhost:8001/api"
SMARTLEAD_API = "https://server.smartlead.ai/api/v1"
SMARTLEAD_API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"

# Known test data: Julia Makutu
JULIA = {
    "reply_id": 32885,
    "campaign_id": "2662913",
    "lead_id": "2528677716",  # Global SmartLead lead ID (NOT leadMap)
    "expected_smartlead_messages": 8,
}

# Counters
_passed = 0
_failed = 0
_skipped = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _label(status: str) -> str:
    """Return a clear label for test status."""
    return {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]", "INFO": "[INFO]"}[status]


def record(status: str, message: str):
    global _passed, _failed, _skipped
    if status == "PASS":
        _passed += 1
    elif status == "FAIL":
        _failed += 1
    elif status == "SKIP":
        _skipped += 1
    print(f"  {_label(status)} {message}")


def fetch_json(url: str, params: Optional[dict] = None, label: str = ""):
    """GET a URL and return (json_data, error_string)."""
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        return resp.json(), None
    except requests.ConnectionError:
        return None, f"Connection refused -- is the server running? ({label or url})"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def validate_message(msg: dict, index: int) -> list:
    """Check that a single message dict has the required fields. Returns list of error strings."""
    errors = []
    if not msg.get("direction"):
        errors.append(f"msg[{index}] missing 'direction'")
    if not msg.get("body"):
        errors.append(f"msg[{index}] missing 'body'")
    if not msg.get("activity_at"):
        errors.append(f"msg[{index}] missing 'activity_at'")
    return errors


# ---------------------------------------------------------------------------
# Test 1: Julia Makutu -- known SmartLead data
# ---------------------------------------------------------------------------
def test_julia_makutu():
    print("\n" + "=" * 70)
    print("TEST 1: Julia Makutu (reply_id=32885, 8 SmartLead messages)")
    print("=" * 70)

    # --- Step A: Call our conversation API ---
    our_url = f"{LOCAL_API}/replies/{JULIA['reply_id']}/conversation"
    our_data, our_err = fetch_json(our_url, label="our conversation API")
    if our_err:
        record("FAIL", f"Our API failed: {our_err}")
        return
    our_messages = our_data.get("messages", [])
    our_count = len(our_messages)
    print(f"  {_label('INFO')} Our API returned {our_count} messages")

    # --- Step B: Call SmartLead API directly ---
    sl_url = (
        f"{SMARTLEAD_API}/campaigns/{JULIA['campaign_id']}"
        f"/leads/{JULIA['lead_id']}/message-history"
    )
    sl_data, sl_err = fetch_json(sl_url, params={"api_key": SMARTLEAD_API_KEY}, label="SmartLead message-history")
    if sl_err:
        record("FAIL", f"SmartLead API failed: {sl_err}")
        return
    # SmartLead returns a list or {"history": [...]}
    if isinstance(sl_data, list):
        sl_messages = sl_data
    elif isinstance(sl_data, dict):
        sl_messages = sl_data.get("history", sl_data.get("data", []))
    else:
        sl_messages = []
    sl_count = len(sl_messages)
    print(f"  {_label('INFO')} SmartLead API returned {sl_count} messages")

    # --- Check 1: SmartLead count matches expected ---
    if sl_count == JULIA["expected_smartlead_messages"]:
        record("PASS", f"SmartLead has exactly {JULIA['expected_smartlead_messages']} messages (verified)")
    elif sl_count >= JULIA["expected_smartlead_messages"]:
        record("PASS", f"SmartLead has {sl_count} messages (>= expected {JULIA['expected_smartlead_messages']})")
    else:
        record("FAIL", f"SmartLead has {sl_count} messages, expected {JULIA['expected_smartlead_messages']}")

    # --- Check 2: Our API returns >= SmartLead messages ---
    if our_count >= sl_count:
        record("PASS", f"Our API has {our_count} messages >= SmartLead's {sl_count}")
    else:
        record("FAIL", f"Our API has {our_count} messages < SmartLead's {sl_count} -- MISSING MESSAGES")

    # --- Check 3: Each of our messages has required fields ---
    field_errors = []
    for i, msg in enumerate(our_messages):
        field_errors.extend(validate_message(msg, i))
    if not field_errors:
        record("PASS", f"All {our_count} messages have direction, body, activity_at")
    else:
        for err in field_errors:
            record("FAIL", err)

    # --- Check 4: Direction distribution makes sense ---
    inbound = sum(1 for m in our_messages if m.get("direction") == "inbound")
    outbound = sum(1 for m in our_messages if m.get("direction") == "outbound")
    if inbound > 0 and outbound > 0:
        record("PASS", f"Direction mix OK: {outbound} outbound, {inbound} inbound")
    elif inbound == 0 and our_count > 1:
        record("FAIL", f"No inbound messages found in {our_count} messages -- suspicious")
    elif outbound == 0 and our_count > 1:
        record("FAIL", f"No outbound messages found in {our_count} messages -- suspicious")
    else:
        record("PASS", f"Direction counts: {outbound} outbound, {inbound} inbound")

    # --- Print message summary for debugging ---
    print(f"\n  --- Message timeline (our API) ---")
    for i, msg in enumerate(our_messages):
        direction = msg.get("direction", "?")
        body_preview = (msg.get("body") or "")[:80].replace("\n", " ")
        ts = msg.get("activity_at", "?")
        print(f"  [{i+1}] {direction:>8} | {ts} | {body_preview}...")


# ---------------------------------------------------------------------------
# Test 2: Dynamic meeting_request replies from project 40
# ---------------------------------------------------------------------------
def test_meeting_request_replies():
    print("\n" + "=" * 70)
    print("TEST 2: Meeting request replies (project_id=40, first 3)")
    print("=" * 70)

    # Fetch meeting request replies
    list_url = f"{LOCAL_API}/replies/"
    params = {
        "project_id": 40,
        "needs_reply": "true",
        "category": "meeting_request",
        "page": 1,
        "page_size": 3,
    }
    list_data, list_err = fetch_json(list_url, params=params, label="replies listing")
    if list_err:
        record("FAIL", f"Could not fetch reply list: {list_err}")
        return

    replies = list_data.get("items", list_data.get("replies", []))
    if not replies:
        record("SKIP", "No meeting_request replies found for project 40")
        return

    print(f"  {_label('INFO')} Found {len(replies)} meeting_request replies to test")

    for idx, reply in enumerate(replies):
        reply_id = reply.get("id")
        lead_email = reply.get("lead_email", "?")
        campaign_id = reply.get("campaign_id", "?")
        lead_name = (
            f"{reply.get('lead_first_name', '')} {reply.get('lead_last_name', '')}".strip()
            or lead_email
        )

        print(f"\n  --- Reply #{idx+1}: {lead_name} (id={reply_id}, campaign={campaign_id}) ---")

        # Step A: Fetch our conversation API
        conv_url = f"{LOCAL_API}/replies/{reply_id}/conversation"
        conv_data, conv_err = fetch_json(conv_url, label=f"conversation for reply {reply_id}")
        if conv_err:
            record("FAIL", f"Reply {reply_id}: Our conversation API failed: {conv_err}")
            continue

        our_messages = conv_data.get("messages", [])
        our_count = len(our_messages)
        print(f"  {_label('INFO')} Our API returned {our_count} messages for reply {reply_id}")

        # Check: should have more than 2 messages (at least initial outbound + their reply)
        if our_count > 2:
            record("PASS", f"Reply {reply_id}: {our_count} messages (> 2)")
        elif our_count == 2:
            record("PASS", f"Reply {reply_id}: {our_count} messages (minimum expected for a reply thread)")
        elif our_count == 1:
            record("FAIL", f"Reply {reply_id}: only {our_count} message -- likely missing outbound or inbound")
        else:
            record("FAIL", f"Reply {reply_id}: {our_count} messages -- empty conversation!")

        # Validate fields on each message
        field_errors = []
        for i, msg in enumerate(our_messages):
            field_errors.extend(validate_message(msg, i))
        if not field_errors:
            record("PASS", f"Reply {reply_id}: all messages have required fields")
        else:
            for err in field_errors:
                record("FAIL", f"Reply {reply_id}: {err}")

        # Step B: Try to cross-reference with SmartLead directly
        if lead_email and lead_email != "?" and campaign_id and campaign_id != "?":
            _cross_check_smartlead(reply_id, lead_email, campaign_id, our_count)
        else:
            record("SKIP", f"Reply {reply_id}: no email/campaign_id to cross-check SmartLead")

        # Print timeline
        if our_messages:
            for i, msg in enumerate(our_messages):
                direction = msg.get("direction", "?")
                body_preview = (msg.get("body") or "")[:80].replace("\n", " ")
                ts = msg.get("activity_at", "?")
                print(f"    [{i+1}] {direction:>8} | {ts} | {body_preview}...")


def _cross_check_smartlead(reply_id: int, email: str, campaign_id: str, our_count: int):
    """Resolve SmartLead lead_id by email and compare message counts."""
    # Step 1: Resolve lead_id from email
    lookup_url = f"{SMARTLEAD_API}/leads/"
    lookup_data, lookup_err = fetch_json(
        lookup_url,
        params={"api_key": SMARTLEAD_API_KEY, "email": email},
        label=f"SmartLead lead lookup for {email}",
    )
    if lookup_err:
        record("SKIP", f"Reply {reply_id}: SmartLead lead lookup failed: {lookup_err}")
        return

    # SmartLead returns a dict with "id" or a list
    lead_id = None
    if isinstance(lookup_data, dict):
        lead_id = lookup_data.get("id")
    elif isinstance(lookup_data, list) and lookup_data:
        lead_id = lookup_data[0].get("id")

    if not lead_id:
        record("SKIP", f"Reply {reply_id}: could not resolve SmartLead lead_id for {email}")
        return

    print(f"  {_label('INFO')} Resolved SmartLead lead_id={lead_id} for {email}")

    # Step 2: Fetch SmartLead message history
    hist_url = f"{SMARTLEAD_API}/campaigns/{campaign_id}/leads/{lead_id}/message-history"
    hist_data, hist_err = fetch_json(
        hist_url,
        params={"api_key": SMARTLEAD_API_KEY},
        label=f"SmartLead history for lead {lead_id}",
    )
    if hist_err:
        record("SKIP", f"Reply {reply_id}: SmartLead history API failed: {hist_err}")
        return

    if isinstance(hist_data, list):
        sl_messages = hist_data
    elif isinstance(hist_data, dict):
        sl_messages = hist_data.get("history", hist_data.get("data", []))
    else:
        sl_messages = []

    sl_count = len(sl_messages)
    print(f"  {_label('INFO')} SmartLead has {sl_count} messages for this lead")

    if our_count >= sl_count:
        record("PASS", f"Reply {reply_id}: our {our_count} >= SmartLead {sl_count}")
    else:
        record("FAIL", f"Reply {reply_id}: our {our_count} < SmartLead {sl_count} -- MISSING MESSAGES")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global _passed, _failed, _skipped

    print("Conversation History API Test Suite")
    print(f"Local API: {LOCAL_API}")
    print(f"SmartLead API key: {SMARTLEAD_API_KEY[:12]}...")

    # Quick health check
    health_data, health_err = fetch_json(f"{LOCAL_API.replace('/api', '')}/health", label="health check")
    if health_err:
        # Try alternative health endpoint
        health_data, health_err = fetch_json(f"{LOCAL_API}/health", label="health check alt")
    if health_err:
        print(f"\n[FATAL] Cannot reach local API: {health_err}")
        print("Make sure the backend is running on port 8001.")
        sys.exit(1)
    print(f"Backend health: OK")

    test_julia_makutu()
    test_meeting_request_replies()

    # Summary
    total = _passed + _failed + _skipped
    print("\n" + "=" * 70)
    print(f"RESULTS: {_passed} passed, {_failed} failed, {_skipped} skipped (total {total})")
    print("=" * 70)

    if _failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
