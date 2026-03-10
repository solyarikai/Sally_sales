"""Load full Telegram chat history via user account (Telethon) into DB.

One-time script to backfill telegram_chat_messages from before the bot was added.
Requires phone auth on first run (session file reused after).
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from telethon import TelegramClient
from telethon.tl.types import PeerChannel, PeerChat
import asyncpg

API_ID = 34121326
API_HASH = "a4b0f44432891817c3158c4964cffdf9"
SESSION_NAME = os.path.join(os.path.dirname(__file__), "petr_session")

# Rizzult chat
CHAT_TITLE = "Rizzult <> Sally – lead gen"
CHAT_ID = -4885632583  # from DB

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://leadgen:leadgen_secret@localhost:5432/leadgen"
)


async def main():
    phone = os.environ.get("TG_PHONE") or sys.argv[1] if len(sys.argv) > 1 else None
    if not phone:
        print("Usage: TG_PHONE=+xxx python load_telegram_history.py")
        print("  or:  python load_telegram_history.py +xxx")
        return

    code_file = os.path.join(os.path.dirname(__file__), "tg_code.txt")

    password_file = os.path.join(os.path.dirname(__file__), "tg_password.txt")

    def _wait_for_file(filepath, label):
        print(f"\n>>> Waiting for {label}...")
        print(f">>> Write it to: {filepath}")
        while True:
            if os.path.exists(filepath):
                with open(filepath) as f:
                    val = f.read().strip()
                if val:
                    os.remove(filepath)
                    print(f">>> Got {label}")
                    return val
            import time
            time.sleep(2)

    def code_callback():
        return _wait_for_file(code_file, "login code")

    def password_callback():
        return _wait_for_file(password_file, "2FA password")

    print(f"Connecting to Telegram as {phone}...")
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=phone, code_callback=code_callback, password=password_callback)

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} {me.last_name or ''} (@{me.username})")

    # Find the chat
    print(f"\nSearching for chat: {CHAT_TITLE}")
    target = None
    async for dialog in client.iter_dialogs():
        if dialog.title == CHAT_TITLE:
            target = dialog
            break

    if not target:
        print(f"Chat '{CHAT_TITLE}' not found! Available chats:")
        async for d in client.iter_dialogs(limit=20):
            print(f"  - {d.title}")
        await client.disconnect()
        return

    print(f"Found: {target.title} (id={target.id})")

    # Connect to DB
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql://")
    print(f"\nConnecting to DB: {db_url.split('@')[1] if '@' in db_url else db_url}")
    pool = await asyncpg.create_pool(db_url)

    # Check existing messages
    existing = await pool.fetchval(
        "SELECT COUNT(*) FROM telegram_chat_messages WHERE chat_id = $1", CHAT_ID
    )
    print(f"Existing messages in DB: {existing}")

    # Get existing message_ids to avoid duplicates
    existing_ids = set()
    if existing > 0:
        rows = await pool.fetch(
            "SELECT message_id FROM telegram_chat_messages WHERE chat_id = $1", CHAT_ID
        )
        existing_ids = {r['message_id'] for r in rows}
        print(f"Will skip {len(existing_ids)} already-stored messages")

    # Fetch all messages
    print(f"\nFetching messages from '{target.title}'...")
    messages = []
    count = 0
    async for msg in client.iter_messages(target, limit=None):
        count += 1
        if count % 100 == 0:
            print(f"  fetched {count} messages...")

        if msg.id in existing_ids:
            continue

        # Determine message type
        msg_type = "text"
        if msg.photo:
            msg_type = "photo"
        elif msg.document:
            msg_type = "document"
        elif msg.video:
            msg_type = "video"
        elif msg.voice:
            msg_type = "voice"
        elif msg.sticker:
            msg_type = "sticker"

        sender_name = ""
        sender_username = None
        sender_id = None
        if msg.sender:
            sender_id = msg.sender_id
            first = getattr(msg.sender, 'first_name', '') or ''
            last = getattr(msg.sender, 'last_name', '') or ''
            sender_name = f"{first} {last}".strip()
            sender_username = getattr(msg.sender, 'username', None)
        elif msg.post:
            sender_name = "channel"

        text = msg.text or msg.message or ""

        # Build raw_data (simplified)
        raw = {
            "message_id": msg.id,
            "date": msg.date.isoformat() if msg.date else None,
            "text": text,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "reply_to": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
        }

        messages.append((
            CHAT_ID,
            msg.id,
            sender_id,
            sender_name,
            sender_username,
            text,
            msg.reply_to.reply_to_msg_id if msg.reply_to else None,
            msg.date.replace(tzinfo=None) if msg.date else datetime.utcnow(),
            msg_type,
            json.dumps(raw, default=str, ensure_ascii=False),
        ))

    print(f"\nTotal fetched: {count}, new to insert: {len(messages)}")

    if not messages:
        print("Nothing to insert.")
        await pool.close()
        await client.disconnect()
        return

    # Insert in batches
    batch_size = 100
    inserted = 0
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i+batch_size]
        await pool.executemany(
            """INSERT INTO telegram_chat_messages
               (chat_id, message_id, sender_id, sender_name, sender_username,
                text, reply_to_message_id, sent_at, message_type, raw_data)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::json)
               ON CONFLICT DO NOTHING""",
            batch
        )
        inserted += len(batch)
        print(f"  inserted {inserted}/{len(messages)}")

    # Update chat message count
    total = await pool.fetchval(
        "SELECT COUNT(*) FROM telegram_chat_messages WHERE chat_id = $1", CHAT_ID
    )
    await pool.execute(
        "UPDATE telegram_chats SET message_count = $1 WHERE chat_id = $2",
        total, CHAT_ID
    )
    print(f"\nDone! Total messages in DB for this chat: {total}")

    await pool.close()
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
