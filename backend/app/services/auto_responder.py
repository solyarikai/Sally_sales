"""
Auto-Responder — AI-powered automatic replies to Telegram conversations.

Uses Google Gemini to generate contextual responses.
Monitors conversations from reply_detector and auto-replies when configured.
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.telegram_outreach import (
    TgCampaign, TgCampaignStatus,
    TgAccount, TgAccountStatus,
    TgRecipient, TgRecipientStatus,
    TgAutoReplyConfig, TgConversation, TgIncomingReply,
    TgProxy,
)
from app.services.telegram_engine import telegram_engine

logger = logging.getLogger(__name__)


class AutoResponder:
    """Background service that auto-replies to conversations using Gemini."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._main_loop())
        logger.info("AutoResponder started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        logger.info("AutoResponder stopped")

    async def _main_loop(self):
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception as e:
                    logger.error(f"AutoResponder tick error: {e}", exc_info=True)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=15.0)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

    async def _tick(self):
        async with async_session_maker() as session:
            # Find campaigns with auto-reply enabled
            configs = await session.execute(
                select(TgAutoReplyConfig).where(TgAutoReplyConfig.enabled == True)
            )
            for config in configs.scalars().all():
                try:
                    await self._process_campaign_replies(config, session)
                except Exception as e:
                    logger.error(f"AutoResponder campaign {config.campaign_id}: {e}")
            await session.commit()

    async def _process_campaign_replies(self, config: TgAutoReplyConfig, session: AsyncSession):
        """Check for new incoming replies that need auto-response."""
        # Get recent unreplied incoming messages
        recent_replies = await session.execute(
            select(TgIncomingReply)
            .where(TgIncomingReply.campaign_id == config.campaign_id)
            .order_by(TgIncomingReply.received_at.desc())
            .limit(20)
        )

        for reply in recent_replies.scalars().all():
            # Check if we already have a conversation for this recipient
            conv_result = await session.execute(
                select(TgConversation).where(
                    TgConversation.campaign_id == config.campaign_id,
                    TgConversation.recipient_id == reply.recipient_id,
                )
            )
            conv = conv_result.scalar()

            if conv:
                if conv.status != "active":
                    continue
                # Check timeout
                if conv.last_message_at and config.dialog_timeout_hours:
                    if datetime.utcnow() - conv.last_message_at > timedelta(hours=config.dialog_timeout_hours):
                        conv.status = "timed_out"
                        continue
                # Check max replies
                if conv.replies_sent >= config.max_replies_per_conversation:
                    conv.status = "stopped"
                    continue
                # Check if this reply is newer than our last response
                if conv.last_message_at and reply.received_at and reply.received_at <= conv.last_message_at:
                    continue  # already processed
            else:
                # Create new conversation
                conv = TgConversation(
                    campaign_id=config.campaign_id,
                    recipient_id=reply.recipient_id,
                    account_id=reply.account_id,
                    status="active",
                    messages=[],
                    started_at=datetime.utcnow(),
                )
                session.add(conv)
                await session.flush()

            # Check stop phrases
            if config.stop_phrases:
                reply_lower = (reply.message_text or "").lower()
                for phrase in config.stop_phrases:
                    if phrase.lower() in reply_lower:
                        conv.status = "stopped"
                        logger.info(f"Conversation {conv.id} stopped by phrase: {phrase}")
                        break
                if conv.status != "active":
                    continue

            # Add user message to history
            messages = conv.messages or []
            messages.append({
                "role": "user",
                "text": reply.message_text,
                "timestamp": reply.received_at.isoformat() if reply.received_at else None,
            })

            # Generate AI response
            ai_response = await self._generate_response(config.system_prompt, messages)
            if not ai_response:
                continue

            # Simulate human behavior
            if config.simulate_human:
                await asyncio.sleep(random.uniform(3, 8))  # reading delay
                # Typing action would be done in send

            # Send response
            account = await session.get(TgAccount, conv.account_id) if conv.account_id else None
            if not account or not account.api_id or not telegram_engine.session_file_exists(account.phone):
                continue

            recipient = await session.get(TgRecipient, reply.recipient_id)
            if not recipient:
                continue

            try:
                proxy_dict = None
                if account.assigned_proxy_id:
                    p = await session.get(TgProxy, account.assigned_proxy_id)
                    if p:
                        proxy_dict = {"host": p.host, "port": p.port, "username": p.username,
                                      "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}
                    else:
                        logger.warning(f"[PROXY] Account {account.phone}: assigned_proxy_id={account.assigned_proxy_id} not found in DB")
                else:
                    logger.warning(f"[PROXY] Auto-responder: account {account.phone} has no proxy assigned")

                await telegram_engine.connect(
                    account.id, phone=account.phone, api_id=account.api_id, api_hash=account.api_hash,
                    device_model=account.device_model or "PC 64bit", system_version=account.system_version or "Windows 10",
                    app_version=account.app_version or "6.5.1 x64", lang_code=account.lang_code or "en",
                    system_lang_code=account.system_lang_code or "en-US", proxy=proxy_dict,
                )

                # Typing simulation
                if config.simulate_human:
                    client = telegram_engine.get_client(account.id)
                    if client:
                        try:
                            entity = await client.get_entity(recipient.username)
                            async with client.action(entity, 'typing'):
                                await asyncio.sleep(random.uniform(2, 5))
                        except Exception:
                            pass

                result = await telegram_engine.send_message(account.id, recipient.username, ai_response)

                if result.get("status") == "sent":
                    messages.append({
                        "role": "assistant",
                        "text": ai_response,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    conv.messages = messages
                    conv.replies_sent += 1
                    conv.last_message_at = datetime.utcnow()
                    logger.info(f"AutoReply sent to @{recipient.username}: {ai_response[:50]}...")

                await telegram_engine.disconnect(account.id)

            except Exception as e:
                logger.error(f"AutoReply send failed: {e}")

    async def _generate_response(self, system_prompt: str, messages: list[dict]) -> Optional[str]:
        """Generate a response using Google Gemini."""
        try:
            import google.generativeai as genai
            from app.core.config import settings

            api_key = getattr(settings, 'GEMINI_API_KEY', None) or getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("No Gemini API key configured for auto-responder")
                return None

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')

            # Build conversation history
            history_text = ""
            for msg in messages[-10:]:  # last 10 messages
                role = "User" if msg["role"] == "user" else "You"
                history_text += f"{role}: {msg['text']}\n"

            prompt = f"""{system_prompt}

Conversation history:
{history_text}

Reply as "You" to the last user message. Keep it short (1-3 sentences). Reply in the same language as the user."""

            response = model.generate_content(prompt)
            return response.text.strip() if response.text else None

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return None


# Singleton
auto_responder = AutoResponder()
