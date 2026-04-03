"""Telegram bot E2E tests — sends messages via Vic_poshv telethon account to @ImpecableBot.

Runs on Hetzner: docker exec telethon-cron python /app/tests/test_bot_flow.py

Tests the same flow as Claude Code MCP connection:
1. /start → welcome message
2. Login with token
3. Find companies query
4. Check pipeline status
5. List campaigns
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

# Test token
TEST_TOKEN = os.environ.get("MCP_TEST_TOKEN", "")

TESTS = [
    {
        "name": "1. /start → welcome message",
        "send": "/start",
        "expect_contains": ["Welcome", "LeadGen", "sign up", "find companies"],
        "expect_any": True,
        "wait": 5,
    },
    {
        "name": "2. Login with token",
        "send": f"My MCP token is: {TEST_TOKEN}",
        "expect_contains": ["logged in", "authenticated", "Test User", "qwe@qwe", "ready", "connected"],
        "expect_any": True,
        "wait": 15,
    },
    {
        "name": "3. Check integrations",
        "send": "what integrations do I have?",
        "expect_contains": ["don't have", "not connected", "no integrations", "set up", "connect"],
        "expect_any": True,
        "wait": 10,
    },
    {
        "name": "4. List projects",
        "send": "list my projects",
        "expect_contains": ["no project", "create", "don't have", "empty", "none"],
        "expect_any": True,
        "wait": 10,
    },
    {
        "name": "5. Create project",
        "send": "create a project called Test Miami targeting IT consulting in Miami",
        "expect_contains": ["created", "project", "Test Miami", "IT"],
        "expect_any": True,
        "wait": 15,
    },
]


async def run_tests():
    client = TelegramClient("tg/session", API_ID, API_HASH)
    await client.start(phone=PHONE)
    print(f"\n{'='*60}")
    print(f"TELEGRAM BOT E2E TESTS — @{BOT_USERNAME}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    for test in TESTS:
        name = test["name"]
        msg = test["send"]
        wait = test.get("wait", 8)
        expect = test.get("expect_contains", [])
        expect_any = test.get("expect_any", False)

        print(f"TEST: {name}")
        print(f"  SEND: {msg[:80]}")

        # Send message
        await client.send_message(BOT_USERNAME, msg)

        # Wait for response
        await asyncio.sleep(wait)

        # Get last message from bot
        messages = await client.get_messages(BOT_USERNAME, limit=3)
        bot_reply = ""
        for m in messages:
            if m.sender_id != (await client.get_me()).id:
                bot_reply = m.text or ""
                break

        if not bot_reply:
            print(f"  RESULT: NO REPLY")
            print(f"  STATUS: FAIL ✗\n")
            failed += 1
            continue

        print(f"  REPLY: {bot_reply[:120]}...")

        # Check expectations
        if expect_any:
            ok = any(e.lower() in bot_reply.lower() for e in expect)
        else:
            ok = all(e.lower() in bot_reply.lower() for e in expect)

        if ok:
            print(f"  STATUS: PASS ✓\n")
            passed += 1
        else:
            print(f"  EXPECTED: {expect}")
            print(f"  STATUS: FAIL ✗\n")
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(TESTS)} total")
    print(f"{'='*60}\n")

    await client.disconnect()
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
