#!/usr/bin/env python3
"""
Standalone script: fetch Instantly inbox placement analytics and send to Slack.
Scheduled via cron: 0 6 * * 2,5  (Tue & Fri 13:00 Da Nang = 06:00 UTC)
"""

import os
import sys
import httpx
import datetime

API_KEY = os.environ.get(
    "INSTANTLY_API_KEY",
    "OWRlZDdiNDctMjU0Ni00N2VhLTk5NjQtNWM3MWQ1N2I3OGI2OlJJQlZ1amJRcWdYVQ==",
)
SLACK_WEBHOOK = os.environ.get(
    "INSTANTLY_ONSOCIAL_SLACK_WEBHOOK",
    "https://hooks.slack.com/services/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",
)
TEST_ID = os.environ.get(
    "INSTANTLY_ONSOCIAL_TEST_ID", "019d61f5-fbab-721d-99f6-31b3b76592ad"
)
BASE_URL = "https://api.instantly.ai/api/v2"

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def fetch_analytics(test_id: str) -> list:
    items = []
    next_cursor = None
    while True:
        params = {"test_id": test_id, "limit": 100}
        if next_cursor:
            params["starting_after"] = next_cursor
        r = httpx.get(
            f"{BASE_URL}/inbox-placement-analytics",
            headers=headers,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("items", []))
        next_cursor = data.get("next_starting_after")
        if not next_cursor:
            break
    return items


def build_stats(items: list) -> list:
    by_email: dict = {}
    for rec in items:
        e = rec["sender_email"]
        if e not in by_email:
            by_email[e] = {"total": 0, "spam": 0}
        by_email[e]["total"] += 1
        if rec.get("is_spam"):
            by_email[e]["spam"] += 1
    return [
        {"email": e, "deliverability": round((1 - s["spam"] / s["total"]) * 100)}
        for e, s in by_email.items()
    ]


def send_to_slack(text: str) -> bool:
    r = httpx.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    return r.status_code == 200


def main():
    items = fetch_analytics(TEST_ID)

    if not items:
        print("No analytics data yet.")
        send_to_slack(
            f"*OnSocial - Inbox Placement Report*\n{datetime.datetime.now().strftime('%d.%m.%Y')}\n\nНет данных для анализа."
        )
        return

    stats = build_stats(items)
    total = len(stats)
    bad = sorted(
        [s for s in stats if s["deliverability"] < 80],
        key=lambda x: x["deliverability"],
    )
    good = [s for s in stats if s["deliverability"] >= 80]

    date = datetime.datetime.now().strftime("%d.%m.%Y")
    link = f"https://app.instantly.ai/app/inbox-placement-tests/{TEST_ID}"

    text = f"*OnSocial - Inbox Placement Report*\n{date}\n\n"

    if bad:
        text += f":warning: *Проблемные ящики ({len(bad)} из {total}):*\n"
        for s in bad:
            text += f"  {s['email']} - {s['deliverability']}%\n"
        text += "\n"

    text += f":white_check_mark: Здоровые ящики: {len(good)} из {total}\n"
    text += f"\n<{link}|Открыть в Instantly>"

    ok = send_to_slack(text)
    print(f"Report sent: {ok} | {len(bad)} bad / {len(good)} good / {total} total")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
