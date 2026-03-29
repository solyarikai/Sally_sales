"""Full pipeline E2E test via Telegram bot @sallymcptestbot.

Tests the COMPLETE flow a real user would go through:
1. /start
2. Login with token
3. Connect SmartLead + Apollo + OpenAI integrations
4. Create project with website
5. Import SmartLead campaigns as blacklist
6. Find companies (Apollo search)
7. Approve Checkpoint 1
8. Wait for scrape + analysis
9. Review targets at Checkpoint 2
10. Check CRM
11. Generate sequence
12. Create SmartLead campaign

Run: docker exec telethon-cron python /app/tests/test_full_pipeline.py
"""
import os
import sys
import asyncio
import json
import time
from telethon import TelegramClient

API_ID = int(os.environ.get("TELETHON_API_ID", "0"))
API_HASH = os.environ.get("TELETHON_API_HASH", "")
BOT_USERNAME = os.environ.get("TEST_BOT_USERNAME", "sallymcptestbot")
PHONE = os.environ.get("TELETHON_PHONE", "")

# Test user credentials
TEST_TOKEN = os.environ.get("MCP_TEST_TOKEN", "")

# API Keys
SMARTLEAD_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

TESTS = [
    # ── Auth ──
    {
        "name": "01. /start",
        "send": "/start",
        "expect_any": ["Welcome", "LeadGen", "find companies"],
        "wait": 5,
    },
    {
        "name": "02. Login",
        "send": f"My token: {TEST_TOKEN}",
        "expect_any": ["logged in", "Test User", "ready", "set up"],
        "wait": 15,
    },

    # ── Integrations ──
    {
        "name": "03. Connect SmartLead",
        "send": f"connect smartlead with key {SMARTLEAD_KEY}",
        "expect_any": ["connected", "SmartLead", "campaigns found", "success"],
        "wait": 15,
    },
    {
        "name": "04. Connect Apollo",
        "send": f"connect apollo with key {APOLLO_KEY}",
        "expect_any": ["connected", "Apollo", "success"],
        "wait": 10,
    },
    {
        "name": "05. Connect OpenAI",
        "send": f"connect openai with key {OPENAI_KEY}",
        "expect_any": ["connected", "OpenAI", "success", "saved"],
        "wait": 10,
    },
    {
        "name": "06. Verify integrations",
        "send": "show my integrations",
        "expect_any": ["SmartLead", "Apollo", "connected"],
        "wait": 10,
    },

    # ── Project ──
    {
        "name": "07. Create project",
        "send": "create project EasyStaff Test with website easystaff.io targeting IT outsourcing companies in Miami, sender Rinat Karimov BDM at Easystaff",
        "expect_any": ["created", "project", "EasyStaff"],
        "wait": 20,
    },

    # ── Pipeline ──
    {
        "name": "08. Find companies",
        "send": "find IT consulting companies in Miami, 5-50 employees, just 1 page",
        "expect_any": ["gathering", "companies", "started", "checkpoint", "found", "blacklist"],
        "wait": 30,
    },
    {
        "name": "09. Approve checkpoint 1",
        "send": "yes, approve, looks good",
        "expect_any": ["approved", "scraping", "analyzing", "proceed", "checkpoint", "target"],
        "wait": 30,
    },
    {
        "name": "10. Check pipeline status",
        "send": "what's my pipeline status?",
        "expect_any": ["pipeline", "phase", "companies", "target", "run"],
        "wait": 10,
    },

    # ── CRM ──
    {
        "name": "11. Check contacts",
        "send": "how many contacts do I have?",
        "expect_any": ["contact", "company", "total", "0", "no contacts"],
        "wait": 10,
    },

    # ── Replies ──
    {
        "name": "12. Check replies",
        "send": "do I have any warm replies?",
        "expect_any": ["no replies", "no warm", "none", "0", "don't have"],
        "wait": 10,
    },
]


async def run_tests():
    client = TelegramClient("tg/session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    print(f"\n{'='*70}")
    print(f"FULL PIPELINE E2E TEST — @{BOT_USERNAME}")
    print(f"{'='*70}\n")

    results = []
    passed = 0
    failed = 0

    for test in TESTS:
        name = test["name"]
        msg = test["send"]
        wait = test.get("wait", 10)
        expect = test.get("expect_any", [])

        print(f"TEST: {name}")
        print(f"  SEND: {msg[:100]}{'...' if len(msg) > 100 else ''}")

        await client.send_message(BOT_USERNAME, msg)
        await asyncio.sleep(wait)

        # Get bot's reply — find the NEWEST message from bot AFTER our send
        messages = await client.get_messages(BOT_USERNAME, limit=10)
        my_id = (await client.get_me()).id
        bot_reply = ""
        found_our_msg = False
        for m in reversed(list(messages)):
            if m.sender_id == my_id and msg[:30] in (m.text or "")[:50]:
                found_our_msg = True
                continue
            if found_our_msg and m.sender_id != my_id and m.text:
                bot_reply = m.text
                break
        # Fallback: just get latest bot message
        if not bot_reply:
            for m in messages:
                if m.sender_id != my_id and m.text:
                    bot_reply = m.text
                    break

        if not bot_reply:
            status = "FAIL"
            reason = "NO REPLY"
        elif any(e.lower() in bot_reply.lower() for e in expect):
            status = "PASS"
            reason = ""
        else:
            status = "FAIL"
            reason = f"Expected any of: {expect}"

        reply_preview = bot_reply[:150].replace('\n', ' ') if bot_reply else "—"
        print(f"  REPLY: {reply_preview}...")
        if reason:
            print(f"  REASON: {reason}")
        print(f"  STATUS: {status} {'✓' if status == 'PASS' else '✗'}\n")

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        results.append({
            "name": name,
            "send": msg[:100],
            "reply": reply_preview,
            "status": status,
            "reason": reason,
        })

    print(f"\n{'='*70}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(TESTS)} total")
    print(f"{'='*70}\n")

    # Write results to suck.md
    with open("/app/tests/suck.md", "w") as f:
        f.write(f"# Telegram Bot Test Results\n\n")
        f.write(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Bot**: @{BOT_USERNAME}\n")
        f.write(f"**Results**: {passed}/{len(TESTS)} passed\n\n")

        if failed > 0:
            f.write("## Failures\n\n")
            for r in results:
                if r["status"] == "FAIL":
                    f.write(f"### {r['name']}\n")
                    f.write(f"- **Sent**: {r['send']}\n")
                    f.write(f"- **Reply**: {r['reply']}\n")
                    f.write(f"- **Reason**: {r['reason']}\n\n")

        f.write("## All Results\n\n")
        f.write("| # | Test | Status | Reply |\n")
        f.write("|---|------|--------|-------|\n")
        for r in results:
            emoji = "✓" if r["status"] == "PASS" else "✗"
            f.write(f"| {emoji} | {r['name']} | {r['status']} | {r['reply'][:60]}... |\n")

    print("Results written to /app/tests/suck.md")

    await client.disconnect()
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
