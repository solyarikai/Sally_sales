import sys, asyncio
from telethon import TelegramClient

API_ID = 32597601
API_HASH = "2a95184dbf5981a91f1e492d0ce30a34"
BOT_USERNAME = "sallyinfinitecodingbot"
PHONE = "+77014007948"

async def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "ping"
    client = TelegramClient("tg/session", API_ID, API_HASH)

    if len(sys.argv) > 2 and sys.argv[2] == "--code":
        code = sys.argv[3]
        await client.start(phone=PHONE, code_callback=lambda: code)
    else:
        await client.start(phone=PHONE)

    await client.send_message(BOT_USERNAME, text)
    await client.disconnect()

asyncio.run(main())
