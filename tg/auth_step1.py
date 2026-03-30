"""Step 1: Request Telegram to send the auth code."""
import asyncio
from telethon import TelegramClient

API_ID = 32597601
API_HASH = "2a95184dbf5981a91f1e492d0ce30a34"
PHONE = "+77014007948"

async def main():
    client = TelegramClient("tg/session", API_ID, API_HASH)
    await client.connect()
    result = await client.send_code_request(PHONE)
    print(f"Code sent! phone_code_hash: {result.phone_code_hash}")
    # Save hash for step 2
    with open("tg/code_hash.txt", "w") as f:
        f.write(result.phone_code_hash)
    await client.disconnect()

asyncio.run(main())
