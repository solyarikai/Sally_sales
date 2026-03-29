"""Telegram bot E2E tests — sends messages via Vic_poshv telethon account to @ImpecableBot.

Runs on Hetzner: docker exec telethon-cron python /app/tests/test_bot_flow.py

Tests the same flow as Claude Code MCP connection:
1. /start → welcome message
2. Login with token
3. Find companies query
4. Check pipeline status
5. List campaigns
"""
import sys
import asyncio
import json
import time
from telethon import TelegramClient

API_ID = 32597601
API_HASH = "2a95184dbf5981a91f1e492d0ce30a34"
BOT_USERNAME = "ImpecableBot"
PHONE = "+77014007948"

# Test token (pn@getsally.io account)
TEST_TOKEN = "mcp_d64cf6445d0905eea586aa4d9de4bc4e9a4119e460183a17b4552d158dedde5e"

TESTS = [
    {
        "name": "1. /start → welcome message",
        "send": "/start",
        "expect_contains": ["Welcome", "LeadGen", "sign up"],
        "wait": 5,
    },
    {
        "name": "2. Login with token",
        "send": f"login with token {TEST_TOKEN}",
        "expect_contains": ["logged in", "authenticated", "connected", "Petr", "pn@getsally"],
        "expect_any": True,
        "wait": 10,
    },
    {
        "name": "3. Check integrations",
        "send": "what integrations are connected?",
        "expect_contains": ["SmartLead", "Apollo", "connected"],
        "expect_any": True,
        "wait": 10,
    },
    {
        "name": "4. Pipeline status",
        "send": "what's my pipeline status?",
        "expect_contains": ["pipeline", "run", "phase", "target"],
        "expect_any": True,
        "wait": 10,
    },
    {
        "name": "5. List campaigns",
        "send": "list my smartlead campaigns with petr in name",
        "expect_contains": ["campaign", "Petr", "petr"],
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
