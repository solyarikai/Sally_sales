"""
Warm-up Worker — background loop that performs active warm-up actions for Telegram accounts.

Active warm-up simulates real user activity over 14 days:
  1. Channel joins: Subscribe to 1-2 curated channels per day
  2. Reactions: Add emoji reactions to recent posts in subscribed channels
  3. Conversations: Exchange messages with warm (oldest) accounts in the system

Each tick (every 30 min) checks accounts with warmup_active=True and executes
scheduled actions based on the current warm-up day (1-14).
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.telegram_outreach import (
    TgAccount, TgAccountStatus, TgProxy,
    TgWarmupLog, TgWarmupActionType,
)
from app.services.telegram_engine import telegram_engine

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

WARMUP_DURATION_DAYS = 14
TICK_INTERVAL_SECONDS = 30 * 60  # 30 minutes

# Channel join schedule: 1-2 per day, spread across first 8 days
CHANNELS_PER_DAY = (1, 2)  # min, max

# Reaction schedule: 2-3 per day, starting from day 2
REACTIONS_PER_DAY = (2, 3)
REACTION_EMOJIS = ["👍", "❤️", "🔥", "😂", "👏", "🤔"]

# Conversation schedule: 1-2 per day, starting from day 3
CONVERSATIONS_PER_DAY = (1, 2)

# Default curated channels for warm-up
DEFAULT_WARMUP_CHANNELS = [
    "sokolov_outreach",
    "dark_ads_chat",
    "chatdnative",
    "cpa_lenta",
    "leadssulive",
    "thepartnerkin",
]

# Working hours (Moscow time, UTC+3)
WARMUP_HOUR_START = 9
WARMUP_HOUR_END = 22


class WarmupWorker:
    """Background service that performs warm-up actions for accounts."""

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
        logger.info("WarmupWorker started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        logger.info("WarmupWorker stopped")

    async def _main_loop(self):
        """Run warm-up tick every 30 minutes."""
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception as e:
                    logger.error(f"WarmupWorker tick error: {e}", exc_info=True)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=TICK_INTERVAL_SECONDS)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            logger.info("WarmupWorker loop exited")

    async def _tick(self):
        """Process all accounts that have active warm-up."""
        async with async_session_maker() as session:
            # Get all accounts with active warm-up
            result = await session.execute(
                select(TgAccount).where(
                    TgAccount.warmup_active == True,
                    TgAccount.status.in_([TgAccountStatus.ACTIVE, TgAccountStatus.PAUSED]),
                )
            )
            accounts = result.scalars().all()

            if not accounts:
                return

            logger.info(f"WarmupWorker: processing {len(accounts)} accounts with active warm-up")

            for account in accounts:
                try:
                    await self._process_account(account, session)
                except Exception as e:
                    logger.error(f"Warm-up failed for account {account.phone}: {e}")

            await session.commit()

    async def _process_account(self, account: TgAccount, session: AsyncSession):
        """Execute warm-up actions for a single account."""
        if not account.warmup_started_at:
            return

        # Calculate warm-up day (1-based)
        warmup_day = (datetime.utcnow() - account.warmup_started_at).days + 1

        # Auto-stop after 14 days
        if warmup_day > WARMUP_DURATION_DAYS:
            logger.info(f"Warm-up complete for {account.phone} (day {warmup_day})")
            account.warmup_active = False
            return

        # Check working hours (rough UTC+3 check)
        current_hour_msk = (datetime.utcnow().hour + 3) % 24
        if current_hour_msk < WARMUP_HOUR_START or current_hour_msk >= WARMUP_HOUR_END:
            return

        # Count actions already done today for this account
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count_q = await session.execute(
            select(func.count(TgWarmupLog.id)).where(
                TgWarmupLog.account_id == account.id,
                TgWarmupLog.performed_at >= today_start,
            )
        )
        actions_today = today_count_q.scalar() or 0

        # Check what types of actions we've done today
        today_types_q = await session.execute(
            select(TgWarmupLog.action_type, func.count(TgWarmupLog.id)).where(
                TgWarmupLog.account_id == account.id,
                TgWarmupLog.performed_at >= today_start,
            ).group_by(TgWarmupLog.action_type)
        )
        today_by_type = dict(today_types_q.all())

        # Decide which actions to perform this tick
        # Channel joins: days 1-8, 1-2 per day
        joins_today = today_by_type.get(TgWarmupActionType.CHANNEL_JOIN, 0)
        if warmup_day <= 8 and joins_today < random.randint(*CHANNELS_PER_DAY):
            await self._join_channel(account, warmup_day, session)

        # Reactions: starting day 2, 2-3 per day
        reactions_today = today_by_type.get(TgWarmupActionType.REACTION, 0)
        if warmup_day >= 2 and reactions_today < random.randint(*REACTIONS_PER_DAY):
            await self._add_reaction(account, session)

        # Conversations: starting day 3, 1-2 per day
        convos_today = today_by_type.get(TgWarmupActionType.CONVERSATION, 0)
        if warmup_day >= 3 and convos_today < random.randint(*CONVERSATIONS_PER_DAY):
            await self._send_warmup_message(account, session)

    async def _get_client(self, account: TgAccount, session: AsyncSession):
        """Connect to Telegram and return client, or None on failure."""
        if not telegram_engine.session_file_exists(account.phone):
            return None

        proxy_dict = None
        if account.assigned_proxy_id:
            p = await session.get(TgProxy, account.assigned_proxy_id)
            if p:
                proxy_dict = {
                    "host": p.host, "port": p.port,
                    "username": p.username, "password": p.password,
                    "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol,
                }

        try:
            client = await telegram_engine.connect(
                account.id,
                phone=account.phone,
                api_id=account.api_id,
                api_hash=account.api_hash,
                device_model=account.device_model or "Samsung SM-G998B",
                system_version=account.system_version or "SDK 33",
                app_version=account.app_version or "10.6.2",
                lang_code=account.lang_code or "en",
                system_lang_code=account.system_lang_code or "en-US",
                proxy=proxy_dict,
            )
            if not await client.is_user_authorized():
                await telegram_engine.disconnect(account.id)
                return None
            return client
        except Exception as e:
            logger.warning(f"Cannot connect {account.phone} for warm-up: {e}")
            return None

    async def _log_action(self, session: AsyncSession, account_id: int,
                          action_type: TgWarmupActionType, detail: str,
                          success: bool = True, error: str = None):
        """Record a warm-up action in the log."""
        session.add(TgWarmupLog(
            account_id=account_id,
            action_type=action_type,
            detail=detail,
            success=success,
            error_message=error,
            performed_at=datetime.utcnow(),
        ))
        # Update counter on account
        account = await session.get(TgAccount, account_id)
        if account:
            account.warmup_actions_done = (account.warmup_actions_done or 0) + 1

    async def _join_channel(self, account: TgAccount, warmup_day: int, session: AsyncSession):
        """Join a random channel from the curated list."""
        # Get already-joined channels for this account
        joined_q = await session.execute(
            select(TgWarmupLog.detail).where(
                TgWarmupLog.account_id == account.id,
                TgWarmupLog.action_type == TgWarmupActionType.CHANNEL_JOIN,
                TgWarmupLog.success == True,
            )
        )
        already_joined = {r[0] for r in joined_q.all()}

        # Pick a channel not yet joined
        available = [ch for ch in DEFAULT_WARMUP_CHANNELS if ch not in already_joined]
        if not available:
            return  # All channels already joined

        channel = random.choice(available)

        client = await self._get_client(account, session)
        if not client:
            return

        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            entity = await client.get_entity(channel)
            await client(JoinChannelRequest(entity))
            # Human-like delay after action
            await asyncio.sleep(random.uniform(2, 5))
            await self._log_action(session, account.id, TgWarmupActionType.CHANNEL_JOIN, channel)
            logger.info(f"Warm-up: {account.phone} joined @{channel}")
        except Exception as e:
            error_msg = str(e)[:200]
            await self._log_action(session, account.id, TgWarmupActionType.CHANNEL_JOIN,
                                   channel, success=False, error=error_msg)
            logger.warning(f"Warm-up channel join failed for {account.phone}: {e}")
        finally:
            await telegram_engine.disconnect(account.id)

    async def _add_reaction(self, account: TgAccount, session: AsyncSession):
        """Add a reaction to a random recent post in a subscribed channel."""
        # Get channels this account has joined
        joined_q = await session.execute(
            select(TgWarmupLog.detail).where(
                TgWarmupLog.account_id == account.id,
                TgWarmupLog.action_type == TgWarmupActionType.CHANNEL_JOIN,
                TgWarmupLog.success == True,
            )
        )
        joined_channels = [r[0] for r in joined_q.all()]
        if not joined_channels:
            return

        channel = random.choice(joined_channels)

        client = await self._get_client(account, session)
        if not client:
            return

        try:
            entity = await client.get_entity(channel)
            # Get recent posts
            messages = await client.get_messages(entity, limit=20)
            if not messages:
                return

            # Check which posts we already reacted to
            reacted_q = await session.execute(
                select(TgWarmupLog.detail).where(
                    TgWarmupLog.account_id == account.id,
                    TgWarmupLog.action_type == TgWarmupActionType.REACTION,
                    TgWarmupLog.detail.like(f"{channel}:%"),
                    TgWarmupLog.success == True,
                )
            )
            reacted_msg_ids = {r[0].split(":")[-1] for r in reacted_q.all()}

            # Pick a message we haven't reacted to
            eligible = [m for m in messages if m.text and str(m.id) not in reacted_msg_ids]
            if not eligible:
                return

            msg = random.choice(eligible)
            emoji = random.choice(REACTION_EMOJIS)

            from telethon.tl.functions.messages import SendReactionRequest
            from telethon.tl.types import ReactionEmoji
            await client(SendReactionRequest(
                peer=entity,
                msg_id=msg.id,
                reaction=[ReactionEmoji(emoticon=emoji)],
            ))
            await asyncio.sleep(random.uniform(1, 3))

            detail = f"{channel}:{msg.id}:{emoji}"
            await self._log_action(session, account.id, TgWarmupActionType.REACTION, detail)
            logger.info(f"Warm-up: {account.phone} reacted {emoji} on @{channel} msg {msg.id}")
        except Exception as e:
            error_msg = str(e)[:200]
            await self._log_action(session, account.id, TgWarmupActionType.REACTION,
                                   channel, success=False, error=error_msg)
            logger.warning(f"Warm-up reaction failed for {account.phone}: {e}")
        finally:
            await telegram_engine.disconnect(account.id)

    async def _send_warmup_message(self, account: TgAccount, session: AsyncSession):
        """Exchange a warm-up message with one of the oldest accounts (warm buddies)."""
        # Find warm buddy: one of the 5 oldest active accounts (not self)
        buddies_q = await session.execute(
            select(TgAccount).where(
                TgAccount.id != account.id,
                TgAccount.status == TgAccountStatus.ACTIVE,
                TgAccount.telegram_user_id != None,
            ).order_by(TgAccount.session_created_at.asc().nullslast()).limit(5)
        )
        buddies = buddies_q.scalars().all()
        if not buddies:
            return

        buddy = random.choice(buddies)
        if not buddy.telegram_user_id:
            return

        client = await self._get_client(account, session)
        if not client:
            return

        try:
            # Pick a random warmup message
            message = random.choice(WARMUP_MESSAGES)
            entity = await client.get_entity(buddy.telegram_user_id)
            await client.send_message(entity, message)
            await asyncio.sleep(random.uniform(2, 5))

            detail = f"to:{buddy.phone}:{message[:50]}"
            await self._log_action(session, account.id, TgWarmupActionType.CONVERSATION, detail)
            logger.info(f"Warm-up: {account.phone} messaged {buddy.phone}")
        except Exception as e:
            error_msg = str(e)[:200]
            await self._log_action(session, account.id, TgWarmupActionType.CONVERSATION,
                                   f"to:{buddy.phone}", success=False, error=error_msg)
            logger.warning(f"Warm-up conversation failed for {account.phone}: {e}")
        finally:
            await telegram_engine.disconnect(account.id)


# ── Warmup message bank (Russian + English) ─────────────────────────

WARMUP_MESSAGES = [
    # Greetings / how are you
    "Привет, как дела?",
    "Здарова! Как жизнь?",
    "Привет! Как прошёл день?",
    "Hey, what's up?",
    "Hi! How's it going?",
    "Привет! Давно не общались",
    "Как твои дела сегодня?",
    "Привет) Что нового?",
    "Hello! How are you doing?",
    "Hey there! What's new?",
    # Weather / weekend
    "Какие планы на выходные?",
    "Как погода у вас?",
    "Any plans for the weekend?",
    "Классная погода сегодня, не находишь?",
    "Что делаешь в субботу?",
    # Work
    "Как работа, всё хорошо?",
    "Много работы сегодня?",
    "How's work going?",
    "Busy day today?",
    "Как там проект продвигается?",
    # Recommendations
    "Есть что посмотреть хорошее?",
    "Можешь что-то посоветовать почитать?",
    "Any good movie recommendations?",
    "Что нового посмотрел?",
    "Слышал про какие-нибудь хорошие книги?",
    # General
    "Ок, понял тебя",
    "Согласен!",
    "Точно, верно подмечено",
    "Sounds good!",
    "Makes sense, thanks",
    "Да, согласен на 100%",
    "Хорошая идея!",
    "Ладно, давай созвонимся потом",
    "Cool, let's catch up later",
    "Всё понятно, спасибо!",
]


# Singleton
warmup_worker = WarmupWorker()
