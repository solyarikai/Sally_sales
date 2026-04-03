"""
Warm-up Worker — background loop that performs active warm-up actions for Telegram accounts.

Active warm-up simulates real user activity over 14 days with a gradual schedule:
  Phase 1 (days 1-3):  1-2 channel joins/day, 1-2 reactions/day
  Phase 2 (days 4-7):  2-3 reactions/day, 1 conversation/day
  Phase 3 (days 8-10): channel joins resume, 3-4 reactions/day, 2 conversations/day
  Phase 4 (days 11-14): full activity — 4-5 reactions, 2-3 conversations, channel views

After day 14 the warm-up is complete (full message limits), but maintenance
mode continues: 1-2 reactions/day to keep the account healthy.

Each tick (every 30 min) checks accounts with warmup_active=True and executes
scheduled actions based on the current warm-up day.
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
    TgWarmupLog, TgWarmupActionType, TgWarmupChannel,
)
from app.services.telegram_engine import telegram_engine
from app.services.infatica_proxy_service import infatica_proxy_service
from app.services.warmup_messages import ALL_QUESTIONS, ALL_ANSWERS

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

WARMUP_DURATION_DAYS = 14
TICK_INTERVAL_SECONDS = 30 * 60  # 30 minutes

REACTION_EMOJIS = ["👍", "❤️", "🔥", "😂", "👏", "🤔"]

# ── Gradual schedule by phase ────────────────────────────────────────
# Each phase defines (min, max) per-day limits for each activity type.
# fmt: off
PHASE_SCHEDULE = {
    # Phase 1: days 1-3 — light activity, build presence
    (1, 3):   {"channels": (1, 2), "reactions": (1, 2), "conversations": (0, 0), "views": (0, 0)},
    # Phase 2: days 4-7 — start conversations, more reactions
    (4, 7):   {"channels": (0, 0), "reactions": (2, 3), "conversations": (1, 1), "views": (0, 0)},
    # Phase 3: days 8-10 — ramp up, rejoin channels
    (8, 10):  {"channels": (1, 2), "reactions": (3, 4), "conversations": (2, 2), "views": (0, 0)},
    # Phase 4: days 11-14 — full activity
    (11, 14): {"channels": (0, 0), "reactions": (4, 5), "conversations": (2, 3), "views": (2, 3)},
}
# Maintenance: day 15+ — keep account healthy
MAINTENANCE_REACTIONS = (1, 2)
# fmt: on

# Fallback channel list (used only when DB table is empty)
FALLBACK_WARMUP_CHANNELS = [
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

    def _get_phase_limits(self, warmup_day: int) -> dict:
        """Return per-day action limits for the given warmup day."""
        for (day_start, day_end), limits in PHASE_SCHEDULE.items():
            if day_start <= warmup_day <= day_end:
                return limits
        return None  # past day 14

    async def _process_account(self, account: TgAccount, session: AsyncSession):
        """Execute warm-up actions for a single account based on gradual schedule."""
        if not account.warmup_started_at:
            return

        # Calculate warm-up day (1-based)
        warmup_day = (datetime.utcnow() - account.warmup_started_at).days + 1
        is_maintenance = warmup_day > WARMUP_DURATION_DAYS

        # Check working hours (rough UTC+3 check)
        current_hour_msk = (datetime.utcnow().hour + 3) % 24
        if current_hour_msk < WARMUP_HOUR_START or current_hour_msk >= WARMUP_HOUR_END:
            return

        # Count what types of actions we've done today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_types_q = await session.execute(
            select(TgWarmupLog.action_type, func.count(TgWarmupLog.id)).where(
                TgWarmupLog.account_id == account.id,
                TgWarmupLog.performed_at >= today_start,
            ).group_by(TgWarmupLog.action_type)
        )
        today_by_type = dict(today_types_q.all())

        if is_maintenance:
            # Post-warmup maintenance: only 1-2 reactions/day to stay healthy
            reactions_today = today_by_type.get(TgWarmupActionType.REACTION, 0)
            if reactions_today < random.randint(*MAINTENANCE_REACTIONS):
                await self._add_reaction(account, session)
            return

        # Active warmup: look up phase limits
        limits = self._get_phase_limits(warmup_day)
        if not limits:
            return

        joins_today = today_by_type.get(TgWarmupActionType.CHANNEL_JOIN, 0)
        reactions_today = today_by_type.get(TgWarmupActionType.REACTION, 0)
        convos_today = today_by_type.get(TgWarmupActionType.CONVERSATION, 0)
        views_today = today_by_type.get(TgWarmupActionType.CHANNEL_VIEW, 0)

        ch_min, ch_max = limits["channels"]
        if ch_max > 0 and joins_today < random.randint(ch_min, ch_max):
            await self._join_channel(account, warmup_day, session)

        rx_min, rx_max = limits["reactions"]
        if rx_max > 0 and reactions_today < random.randint(rx_min, rx_max):
            await self._add_reaction(account, session)

        cv_min, cv_max = limits["conversations"]
        if cv_max > 0 and convos_today < random.randint(cv_min, cv_max):
            await self._send_warmup_message(account, session)

        vw_min, vw_max = limits["views"]
        if vw_max > 0 and views_today < random.randint(vw_min, vw_max):
            await self._view_channel(account, session)

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

        # Fallback: auto-generate Infatica proxy
        if proxy_dict is None and infatica_proxy_service.is_configured:
            proxy_dict = infatica_proxy_service.get_proxy_for_account(account.phone, account.id)
            logger.info(f"Warm-up {account.phone}: using Infatica proxy (geo auto-detect)")

        try:
            client = await telegram_engine.connect(
                account.id,
                phone=account.phone,
                api_id=account.api_id,
                api_hash=account.api_hash,
                device_model=account.device_model or "PC 64bit",
                system_version=account.system_version or "Windows 10",
                app_version=account.app_version or "6.5.1 x64",
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

    async def _get_warmup_channels(self, session: AsyncSession) -> list[str]:
        """Load active warmup channels from DB, fall back to hardcoded list."""
        result = await session.execute(
            select(TgWarmupChannel.url).where(TgWarmupChannel.is_active == True)
        )
        channels = [r[0] for r in result.all()]
        return channels if channels else list(FALLBACK_WARMUP_CHANNELS)

    async def _join_channel(self, account: TgAccount, warmup_day: int, session: AsyncSession):
        """Join a random channel from the curated list."""
        # Load channels from DB
        warmup_channels = await self._get_warmup_channels(session)

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
        available = [ch for ch in warmup_channels if ch not in already_joined]
        if not available:
            return  # All channels already joined

        channel = random.choice(available)

        client = await self._get_client(account, session)
        if not client:
            return

        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            from telethon.tl.functions.messages import ImportChatInviteRequest

            if channel.startswith("+") or channel.startswith("joinchat/"):
                # Private invite link: +HASH or joinchat/HASH
                invite_hash = channel.lstrip("+").replace("joinchat/", "")
                await client(ImportChatInviteRequest(invite_hash))
            else:
                entity = await client.get_entity(channel)
                await client(JoinChannelRequest(entity))

            # Human-like delay after action
            await asyncio.sleep(random.uniform(2, 5))
            await self._log_action(session, account.id, TgWarmupActionType.CHANNEL_JOIN, channel)
            logger.info(f"Warm-up: {account.phone} joined {channel}")
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
            reacted_msg_ids = {r[0].split(":")[1] for r in reacted_q.all() if ":" in r[0]}

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
        """Exchange multi-turn warm-up dialog with one of the oldest accounts (warm buddies).

        Simulates a realistic conversation: 2-4 messages alternating between
        the warming-up account and a buddy, with optional reactions.
        """
        if not account.telegram_user_id:
            return

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

        # Plan dialog: 1-2 exchanges = 2-4 messages total
        num_exchanges = random.randint(1, 2)

        for exchange_idx in range(num_exchanges):
            # ── Sender sends a question ──
            sender_client = await self._get_client(account, session)
            if not sender_client:
                return
            try:
                buddy_entity = await sender_client.get_entity(buddy.telegram_user_id)
                question = random.choice(ALL_QUESTIONS)
                await sender_client.send_message(buddy_entity, question)
                await asyncio.sleep(random.uniform(1, 3))
                await self._log_action(
                    session, account.id, TgWarmupActionType.CONVERSATION,
                    f"to:{buddy.phone}:{question[:50]}",
                )
                logger.info(f"Warm-up conv: {account.phone} → {buddy.phone}: {question[:30]}")
            except Exception as e:
                await self._log_action(
                    session, account.id, TgWarmupActionType.CONVERSATION,
                    f"to:{buddy.phone}", success=False, error=str(e)[:200],
                )
                logger.warning(f"Warm-up conversation send failed for {account.phone}: {e}")
                return
            finally:
                await telegram_engine.disconnect(account.id)

            # Human-like pause before buddy replies
            await asyncio.sleep(random.uniform(15, 45))

            # ── Buddy replies ──
            buddy_client = await self._get_client(buddy, session)
            if not buddy_client:
                return  # Can't reply — dialog ends here
            try:
                sender_entity = await buddy_client.get_entity(account.telegram_user_id)
                answer = random.choice(ALL_ANSWERS)
                await buddy_client.send_message(sender_entity, answer)
                await asyncio.sleep(random.uniform(1, 3))
                await self._log_action(
                    session, buddy.id, TgWarmupActionType.CONVERSATION,
                    f"to:{account.phone}:{answer[:50]}",
                )
                logger.info(f"Warm-up conv: {buddy.phone} → {account.phone}: {answer[:30]}")

                # 30% chance: buddy reacts to sender's message
                if random.random() < 0.3:
                    try:
                        from telethon.tl.functions.messages import SendReactionRequest
                        from telethon.tl.types import ReactionEmoji

                        msgs = await buddy_client.get_messages(sender_entity, limit=5)
                        sender_msgs = [m for m in msgs if not m.out and m.text]
                        if sender_msgs:
                            target = random.choice(sender_msgs)
                            emoji = random.choice(REACTION_EMOJIS)
                            await buddy_client(SendReactionRequest(
                                peer=sender_entity,
                                msg_id=target.id,
                                reaction=[ReactionEmoji(emoticon=emoji)],
                            ))
                    except Exception:
                        pass  # Reaction is optional — don't fail the dialog
            except Exception as e:
                await self._log_action(
                    session, buddy.id, TgWarmupActionType.CONVERSATION,
                    f"to:{account.phone}", success=False, error=str(e)[:200],
                )
                logger.warning(f"Warm-up conversation reply failed for {buddy.phone}: {e}")
                return
            finally:
                await telegram_engine.disconnect(buddy.id)

            # Pause between exchanges
            if exchange_idx < num_exchanges - 1:
                await asyncio.sleep(random.uniform(20, 60))

    async def _view_channel(self, account: TgAccount, session: AsyncSession):
        """Open a subscribed channel and scroll through recent messages (simulates reading)."""
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
            # Fetch recent messages (simulates scrolling / reading the feed)
            messages = await client.get_messages(entity, limit=random.randint(10, 30))
            if messages:
                # Mark messages as read — Telethon sends ReadHistory automatically
                # when get_messages is called, but we can also explicitly mark read
                from telethon.tl.functions.messages import ReadHistoryRequest
                from telethon.tl.functions.channels import ReadHistoryRequest as ChannelReadHistoryRequest
                try:
                    await client(ChannelReadHistoryRequest(channel=entity, max_id=messages[0].id))
                except Exception:
                    pass  # Some channels may not support this

            # Human-like browsing delay
            await asyncio.sleep(random.uniform(3, 8))

            detail = f"{channel}:{len(messages) if messages else 0}msgs"
            await self._log_action(session, account.id, TgWarmupActionType.CHANNEL_VIEW, detail)
            logger.info(f"Warm-up: {account.phone} viewed {channel} ({len(messages) if messages else 0} msgs)")
        except Exception as e:
            error_msg = str(e)[:200]
            await self._log_action(session, account.id, TgWarmupActionType.CHANNEL_VIEW,
                                   channel, success=False, error=error_msg)
            logger.warning(f"Warm-up channel view failed for {account.phone}: {e}")
        finally:
            await telegram_engine.disconnect(account.id)


# Singleton
warmup_worker = WarmupWorker()
