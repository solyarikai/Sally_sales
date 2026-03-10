"""Sally Bot Service — silent Telegram client chat monitor.

Polls for new messages, stores them, and periodically analyzes with Gemini.
In groups: silent (stores only). In DMs: friendly GPT-powered replies.
"""
import logging
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import async_session_maker
from app.models.telegram_chat import TelegramChat, TelegramChatMessage

logger = logging.getLogger(__name__)

GREETING = (
    "Hey! I'm Sally AI BDM — Petr just added me to maximize the result for Rizzult project — "
    "result… Rizzult… get it? "
    "I'll be back with brilliant thoughts!"
)

# Track DM reply count per chat — share links on 1st reply, then every 10th
_dm_reply_count: dict[int, int] = defaultdict(int)

SALES_LINKS = (
    "\n\nCheck out what we do: getsally.io | Follow updates: @rinatkhat"
)


async def _generate_dm_reply(user_name: str, user_message: str, chat_id: int) -> str:
    """Generate a friendly DM reply using GPT-4o-mini."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 18:
        time_of_day = "afternoon"
    elif 18 <= hour < 22:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    system_prompt = f"""You are Sally AI BDM, a friendly bot for the Sally B2B lead generation team.
Someone is messaging you directly. Respond with warmth and personality — like a chill,
helpful bro. Keep it concise (1-3 sentences max).

It's currently {time_of_day} (UTC). Use appropriate greeting if natural.

If they ask what you do — you're an AI assistant for the Sally team, helping with
B2B lead generation, project tracking, and outreach operations.

Do NOT include any links or mentions of websites/channels — that's handled separately.

Never be robotic. Be genuine, casual, human."""

    reply = None

    # Try OpenAI first
    if settings.OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"User '{user_name}' says: {user_message}"},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.9,
                    },
                )
                data = resp.json()
                if "choices" in data:
                    reply = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}")

    # Fallback to Gemini
    if not reply and settings.GEMINI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser '{user_name}' says: {user_message}"}]}],
                        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.9},
                    },
                )
                data = resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    if not reply:
        reply = f"Hey {user_name}! Have a great {time_of_day}! I'm Sally AI BDM — working behind the scenes for the Sally lead gen team."

    # Hardcode links: first reply always, then every 10th — don't trust GPT for this
    _dm_reply_count[chat_id] += 1
    count = _dm_reply_count[chat_id]
    if count == 1 or count % 10 == 0:
        reply += SALES_LINKS

    return reply


class SallyBotService:
    def __init__(self):
        self.token = settings.TELEGRAM_SALLY_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self._offset = 0
        self._running = False
        self._bot_id = None

    async def _api(self, method: str, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post(f"{self.base_url}/{method}", json=kwargs)
            return resp.json()

    async def _get_bot_id(self) -> int:
        if not self._bot_id:
            info = await self._api("getMe")
            self._bot_id = info.get("result", {}).get("id")
        return self._bot_id

    async def send_message(self, chat_id: int, text: str, parse_mode: str = None) -> dict:
        params = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        return await self._api("sendMessage", **params)

    async def _handle_update(self, update: dict):
        """Process a single Telegram update."""
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            logger.debug(f"Sally update skipped (no message): {list(update.keys())}")
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "")
        sender = msg.get("from", {})
        text = msg.get("text") or msg.get("caption") or ""
        logger.info(f"Sally update: chat={chat_id} type={chat_type} from={sender.get('first_name')} text={text[:50] if text else '(empty)'}")

        # Bot added to a group — send greeting
        new_members = msg.get("new_chat_members", [])
        if new_members:
            bot_id = await self._get_bot_id()
            for member in new_members:
                if member.get("id") == bot_id:
                    logger.info(f"Sally bot added to chat {chat_id}: {chat.get('title')}")
                    await self.send_message(chat_id, GREETING)
                    await self._ensure_chat(chat_id, chat.get("title"), chat_type)
                    return

        # DM (private chat) — respond with GPT
        if chat_type == "private":
            user_name = sender.get("first_name", "friend")
            reply = await _generate_dm_reply(user_name, text, chat_id)
            await self.send_message(chat_id, reply)
            return

        # Group messages — silent store only
        if chat_type not in ("group", "supergroup"):
            return

        msg_type = "text"
        for t in ["photo", "document", "video", "voice", "sticker", "animation"]:
            if t in msg:
                msg_type = t
                break

        async with async_session_maker() as session:
            await self._ensure_chat(chat_id, chat.get("title"), chat_type, session)

            chat_msg = TelegramChatMessage(
                chat_id=chat_id,
                message_id=msg.get("message_id"),
                sender_id=sender.get("id"),
                sender_name=f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip(),
                sender_username=sender.get("username"),
                text=text,
                reply_to_message_id=msg.get("reply_to_message", {}).get("message_id") if msg.get("reply_to_message") else None,
                sent_at=datetime.fromtimestamp(msg.get("date", 0), tz=timezone.utc),
                message_type=msg_type,
                raw_data=msg,
            )
            session.add(chat_msg)

            result = await session.execute(
                select(TelegramChat).where(TelegramChat.chat_id == chat_id)
            )
            tc = result.scalar_one_or_none()
            if tc:
                tc.message_count = (tc.message_count or 0) + 1
                tc.last_message_at = chat_msg.sent_at

            await session.commit()
            logger.info(f"Sally stored msg #{chat_msg.message_id} from {chat_msg.sender_name} in chat {chat_id}")

    async def _ensure_chat(self, chat_id: int, title: str, chat_type: str, session: AsyncSession = None):
        """Create TelegramChat record if it doesn't exist."""
        should_close = False
        if session is None:
            session = async_session_maker()
            should_close = True

        try:
            result = await session.execute(
                select(TelegramChat).where(TelegramChat.chat_id == chat_id)
            )
            if not result.scalar_one_or_none():
                session.add(TelegramChat(
                    chat_id=chat_id,
                    chat_title=title,
                    chat_type=chat_type,
                ))
                await session.commit()
        finally:
            if should_close:
                await session.close()

    async def poll_loop(self):
        """Long-polling loop for receiving updates."""
        if not self.token:
            logger.warning("TELEGRAM_SALLY_BOT_TOKEN not set, Sally bot disabled")
            return

        self._running = True
        self._bot_id = (await self._api("getMe")).get("result", {}).get("id")
        logger.info(f"Sally bot polling started (bot_id={self._bot_id})")

        while self._running:
            try:
                data = await self._api(
                    "getUpdates",
                    offset=self._offset,
                    timeout=30,
                    allowed_updates=["message", "edited_message", "my_chat_member"],
                )
                if not data.get("ok"):
                    logger.error(f"Sally poll failed: {data}")
                updates = data.get("result", [])
                if updates:
                    logger.info(f"Sally poll: got {len(updates)} updates")
                for update in updates:
                    self._offset = update["update_id"] + 1
                    try:
                        await self._handle_update(update)
                    except Exception as e:
                        logger.error(f"Error handling update: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Sally bot poll error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self._running = False


sally_bot_service = SallyBotService()
