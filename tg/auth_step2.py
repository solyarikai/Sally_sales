"""Step 2: Complete auth with the code and send a test message."""
import asyncio
from telethon import TelegramClient

API_ID = 32597601
API_HASH = "2a95184dbf5981a91f1e492d0ce30a34"
PHONE = "+77014007948"
BOT_USERNAME = "infinitecodingbot"

async def main():
    client = TelegramClient("tg/session", API_ID, API_HASH)
    await client.connect()

    with open("tg/code_hash.txt") as f:
        phone_code_hash = f.read().strip()

    await client.sign_in(PHONE, "10308", phone_code_hash=phone_code_hash)
    print("Authenticated!")

    await client.send_message(BOT_USERNAME, "test message from cron setup")
    print("Message sent!")

    await client.disconnect()

asyncio.run(main())
