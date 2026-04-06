"""
Instantly MCP Server
Manage inbox placement tests and send spam reports.
"""

import os
import httpx
from fastmcp import FastMCP

API_KEY = os.environ.get("INSTANTLY_API_KEY", "")
BASE_URL = "https://api.instantly.ai/api/v2"
ONSOCIAL_TEST_ID = os.environ.get("INSTANTLY_ONSOCIAL_TEST_ID", "")
ONSOCIAL_SLACK_WEBHOOK = os.environ.get("INSTANTLY_ONSOCIAL_SLACK_WEBHOOK", "")

mcp = FastMCP("Instantly")


def headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def api_get(path: str, params: dict = None) -> dict:
    resp = httpx.get(f"{BASE_URL}{path}", headers=headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict = None) -> dict:
    resp = httpx.post(
        f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def api_patch(path: str, body: dict = None) -> dict:
    resp = httpx.patch(
        f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# INBOX PLACEMENT TESTS
# ---------------------------------------------------------------------------


@mcp.tool()
def get_test(test_id: str = None) -> str:
    """
    Get inbox placement test details including current mailboxes list.
    If test_id is not provided, uses the default OnSocial test.

    Args:
        test_id: Test UUID (optional, defaults to OnSocial test)
    """
    tid = test_id or ONSOCIAL_TEST_ID
    data = api_get(f"/inbox-placement-tests/{tid}")
    emails = data.get("emails", [])
    return (
        f"Test: {data['name']}\n"
        f"ID: {data['id']}\n"
        f"Status: {data.get('status')} (1=Active, 2=Paused, 3=Completed)\n"
        f"Mailboxes ({len(emails)}):\n" + "\n".join(f"  {e}" for e in emails)
    )


@mcp.tool()
def list_tests() -> str:
    """List all inbox placement tests."""
    data = api_get("/inbox-placement-tests")
    items = data.get("items", [])
    if not items:
        return "No tests found."
    lines = []
    for t in items:
        lines.append(
            f"{t['id']} | {t['name']} | status={t.get('status')} | emails={len(t.get('emails', []))}"
        )
    return "\n".join(lines)


@mcp.tool()
def add_mailboxes(new_emails: list[str], test_id: str = None) -> str:
    """
    Add mailboxes to an inbox placement test.
    Since Instantly API doesn't allow editing emails after creation,
    this creates a new test with the merged mailbox list and updates the default test ID.

    Args:
        new_emails: List of email addresses to add
        test_id: Source test UUID (optional, defaults to OnSocial test)
    """
    global ONSOCIAL_TEST_ID

    tid = test_id or ONSOCIAL_TEST_ID
    current = api_get(f"/inbox-placement-tests/{tid}")
    existing = current.get("emails", [])

    to_add = [e for e in new_emails if e not in existing]
    if not to_add:
        return (
            f"All {len(new_emails)} mailboxes already in the test. No changes needed."
        )

    merged = existing + to_add

    new_test = api_post(
        "/inbox-placement-tests",
        {
            "name": current["name"],
            "type": 1,
            "sending_method": current.get("sending_method", 1),
            "delivery_mode": current.get("delivery_mode", 1),
            "email_subject": current.get("email_subject", "Test"),
            "email_body": current.get("email_body", "Test"),
            "emails": merged,
            "run_immediately": False,
        },
    )

    new_id = new_test["id"]
    ONSOCIAL_TEST_ID = new_id

    return (
        f"Created new test with {len(merged)} mailboxes.\n"
        f"New test ID: {new_id}\n"
        f"Added: {len(to_add)} mailboxes\n"
        f"  " + "\n  ".join(to_add) + "\n\n"
        f"IMPORTANT: Update INSTANTLY_ONSOCIAL_TEST_ID in mcp.json to: {new_id}"
    )


@mcp.tool()
def replace_mailboxes(emails: list[str], test_name: str = "Onsocial") -> str:
    """
    Create a new inbox placement test with exactly the given mailbox list,
    replacing the current one.

    Args:
        emails: Full list of email addresses for the new test
        test_name: Name for the new test (default: Onsocial)
    """
    tid = ONSOCIAL_TEST_ID
    current = api_get(f"/inbox-placement-tests/{tid}")

    new_test = api_post(
        "/inbox-placement-tests",
        {
            "name": test_name,
            "type": 1,
            "sending_method": current.get("sending_method", 1),
            "delivery_mode": current.get("delivery_mode", 1),
            "email_subject": current.get("email_subject", "Test"),
            "email_body": current.get("email_body", "Test"),
            "emails": emails,
            "run_immediately": False,
        },
    )

    new_id = new_test["id"]
    return (
        f"Created new test '{test_name}' with {len(emails)} mailboxes.\n"
        f"New test ID: {new_id}\n\n"
        f"IMPORTANT: Update INSTANTLY_ONSOCIAL_TEST_ID in mcp.json to: {new_id}"
    )


# ---------------------------------------------------------------------------
# ANALYTICS & SPAM REPORT
# ---------------------------------------------------------------------------


@mcp.tool()
def get_analytics(test_id: str = None, limit: int = 100) -> str:
    """
    Get inbox placement analytics for a test, grouped by sender email.

    Args:
        test_id: Test UUID (optional, defaults to OnSocial test)
        limit: Max items per page (default 100)
    """
    tid = test_id or ONSOCIAL_TEST_ID
    items = []
    next_cursor = None

    while True:
        params = {"test_id": tid, "limit": limit}
        if next_cursor:
            params["starting_after"] = next_cursor
        data = api_get("/inbox-placement-analytics", params)
        items.extend(data.get("items", []))
        next_cursor = data.get("next_starting_after")
        if not next_cursor:
            break

    if not items:
        return "No analytics data yet. Run the test in Instantly UI first."

    by_email: dict = {}
    for r in items:
        e = r["sender_email"]
        if e not in by_email:
            by_email[e] = {"total": 0, "spam": 0}
        by_email[e]["total"] += 1
        if r.get("is_spam"):
            by_email[e]["spam"] += 1

    stats = sorted(
        [
            {"email": e, "deliverability": round((1 - s["spam"] / s["total"]) * 100)}
            for e, s in by_email.items()
        ],
        key=lambda x: x["deliverability"],
    )

    bad = [s for s in stats if s["deliverability"] < 80]
    good = [s for s in stats if s["deliverability"] >= 80]

    lines = [f"Analytics for test {tid} ({len(stats)} mailboxes):"]
    if bad:
        lines.append(f"\nProblematic (< 80%) — {len(bad)}:")
        for s in bad:
            lines.append(f"  {s['email']} — {s['deliverability']}%")
    lines.append(f"\nHealthy (>= 80%): {len(good)} of {len(stats)}")
    return "\n".join(lines)


@mcp.tool()
def send_spam_report(test_id: str = None, slack_webhook: str = None) -> str:
    """
    Fetch inbox placement analytics and send a formatted report to Slack.
    Uses the default OnSocial test and Slack webhook if not provided.

    Args:
        test_id: Test UUID (optional, defaults to OnSocial test)
        slack_webhook: Slack webhook URL (optional, defaults to OnSocial channel)
    """
    import datetime

    tid = test_id or ONSOCIAL_TEST_ID
    webhook = slack_webhook or ONSOCIAL_SLACK_WEBHOOK

    items = []
    next_cursor = None
    while True:
        params = {"test_id": tid, "limit": 100}
        if next_cursor:
            params["starting_after"] = next_cursor
        data = api_get("/inbox-placement-analytics", params)
        items.extend(data.get("items", []))
        next_cursor = data.get("next_starting_after")
        if not next_cursor:
            break

    by_email: dict = {}
    for r in items:
        e = r["sender_email"]
        if e not in by_email:
            by_email[e] = {"total": 0, "spam": 0}
        by_email[e]["total"] += 1
        if r.get("is_spam"):
            by_email[e]["spam"] += 1

    stats = [
        {"email": e, "deliverability": round((1 - s["spam"] / s["total"]) * 100)}
        for e, s in by_email.items()
    ]
    total = len(stats)
    bad = [s for s in stats if s["deliverability"] < 80]
    good = [s for s in stats if s["deliverability"] >= 80]

    date = datetime.datetime.now().strftime("%d.%m.%Y")
    link = f"https://app.instantly.ai/app/inbox-placement-tests/{tid}"

    text = f"*OnSocial - Inbox Placement Report*\n{date}\n\n"

    if bad:
        text += f":warning: *Проблемные ящики ({len(bad)} из {total}):*\n"
        for s in sorted(bad, key=lambda x: x["deliverability"]):
            text += f"  {s['email']} - {s['deliverability']}%\n"
        text += "\n"

    if good:
        text += f":white_check_mark: Здоровые ящики: {len(good)} из {total}\n"

    if total == 0:
        text += "Нет данных по ящикам\n"

    text += f"\n<{link}|Открыть в Instantly>"

    resp = httpx.post(webhook, json={"text": text}, timeout=10)
    if resp.status_code == 200:
        status = "bad" if bad else "OK"
        return f"Report sent to Slack. Status: {len(bad)} problematic / {len(good)} healthy ({total} total)."
    else:
        return f"Failed to send to Slack: {resp.status_code} {resp.text}"
