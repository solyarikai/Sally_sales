"""
Sending Worker — background loop that processes active Telegram outreach campaigns.

Flow per campaign tick:
  1. Check timezone window (send_from_hour..send_to_hour)
  2. Find due recipients (pending OR follow-up whose next_message_at <= now)
  3. Pick next available account (round-robin, respect daily limits, skip spamblocked)
  4. Resolve spintax + variables → rendered message
  5. Send via TelegramEngine
  6. Log message, update counters, schedule next follow-up
"""
import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import async_session_maker
from app.models.telegram_outreach import (
    TgCampaign, TgCampaignAccount, TgCampaignStatus,
    TgAccount, TgAccountStatus, TgSpamblockType,
    TgRecipient, TgRecipientStatus,
    TgSequence, TgSequenceStep, TgStepVariant,
    TgOutreachMessage, TgMessageStatus,
    TgProxy, TgContact, TgContactStatus,
    TgIncomingReply,
)
from app.services.telegram_engine import telegram_engine

logger = logging.getLogger(__name__)


# ── Session age & warm-up limits ─────────────────────────────────────

WARMUP_MSGS_PER_DAY = 2   # +2 messages per warm-up day
YOUNG_SESSION_DAYS = 7     # sessions < 7 days old get extra restrictions
YOUNG_SESSION_MAX_MSGS = 5 # hard cap for young sessions regardless of base limit
YOUNG_SESSION_DELAY_MULT = 1.8  # delay multiplier for young sessions

# ── Hardcoded sending parameters (not user-configurable) ────────────
DELAY_BASE_MIN = 11        # min seconds between sends
DELAY_BASE_MAX = 25        # max seconds between sends
SPAMBLOCK_THRESHOLD = 5    # spamblock errors before account skips the day
MAX_COLD_PER_HOUR_PER_ACCOUNT = 2  # hard limit: max cold messages per hour per account


def get_session_age_days(account) -> int | None:
    """Return session age in days, or None if unknown."""
    if not account.session_created_at:
        return None
    return (datetime.utcnow() - account.session_created_at).days


def is_young_session(account) -> bool:
    """True if session is less than YOUNG_SESSION_DAYS old."""
    if getattr(account, "skip_warmup", False):
        return False
    age = get_session_age_days(account)
    return age is not None and age < YOUNG_SESSION_DAYS


def get_effective_daily_limit(account) -> int:
    """Return effective daily limit, applying warm-up ramp for young sessions.

    New/reactivated accounts ramp gradually:
      day 1 → 2 msgs, day 2 → 4, day 3 → 6, … until full daily_message_limit.
    Sessions < 7 days: hard cap at YOUNG_SESSION_MAX_MSGS (extra safety).
    Accounts without session_created_at are treated as mature (full limit).
    """
    base_limit = account.daily_message_limit or 10

    if getattr(account, "skip_warmup", False):
        return base_limit

    if not account.session_created_at:
        return base_limit

    session_age_days = get_session_age_days(account)
    warmup_limit = WARMUP_MSGS_PER_DAY * (session_age_days + 1)

    # Young session hard cap: even if warmup_limit is higher, clamp it
    if session_age_days < YOUNG_SESSION_DAYS:
        warmup_limit = min(warmup_limit, YOUNG_SESSION_MAX_MSGS)

    if warmup_limit >= base_limit:
        return base_limit

    logger.debug(f"Warm-up active for {account.phone}: day {session_age_days + 1}, "
                 f"limit {warmup_limit}/{base_limit}"
                 + (" [YOUNG]" if session_age_days < YOUNG_SESSION_DAYS else ""))
    return warmup_limit


# ── Spintax + Variable helpers ────────────────────────────────────────

def resolve_spintax(text: str) -> str:
    """Recursively resolve {option1|option2|option3}."""
    pattern = re.compile(r"\{([^{}]+)\}")
    while pattern.search(text):
        text = pattern.sub(lambda m: random.choice(m.group(1).split("|")), text)
    return text


def substitute_variables(text: str, variables: dict) -> str:
    """Replace {{var_name}} placeholders."""
    def replacer(m):
        key = m.group(1).strip()
        return variables.get(key, m.group(0))
    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


def pick_variant(variants: list[TgStepVariant]) -> TgStepVariant:
    """Weighted random pick among A/B variants."""
    if len(variants) == 1:
        return variants[0]
    weights = [v.weight_percent for v in variants]
    return random.choices(variants, weights=weights, k=1)[0]


# ── Timezone helpers ──────────────────────────────────────────────────

def now_in_tz(tz_name: str) -> datetime:
    """Current datetime in the given timezone."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz)


def is_within_send_window(campaign: TgCampaign) -> bool:
    """Check if current hour is within campaign's send window."""
    now = now_in_tz(campaign.timezone or "UTC")
    hour = now.hour
    if campaign.send_from_hour <= campaign.send_to_hour:
        return campaign.send_from_hour <= hour < campaign.send_to_hour
    else:
        # Wraps midnight, e.g. 22..06
        return hour >= campaign.send_from_hour or hour < campaign.send_to_hour


# ── Spread scheduling ────────────────────────────────────────────────

def _calc_spread_allowance(campaign, cold_sent_today: int) -> int:
    """How many cold messages may be sent RIGHT NOW.

    Distributes daily_message_limit evenly across the send window with
    deterministic per-day jitter (±15 min, capped for dense schedules).
    Returns delta between 'should-have-been-sent-by-now' and
    'actually-sent-today', capped at 2 per tick to prevent burst on
    late start or restart.
    """
    daily_limit = campaign.daily_message_limit
    if not daily_limit:
        return 500  # no limit configured

    now = now_in_tz(campaign.timezone or "UTC")
    from_h = campaign.send_from_hour
    to_h = campaign.send_to_hour

    # Window duration in minutes
    if to_h > from_h:
        window_mins = (to_h - from_h) * 60
    else:
        window_mins = (24 - from_h + to_h) * 60
    if window_mins <= 0:
        window_mins = 24 * 60

    # Minutes elapsed since window opened today
    current_mins = ((now.hour * 60 + now.minute) - from_h * 60) % (24 * 60)
    if current_mins > window_mins:
        current_mins = window_mins

    # Deterministic jitter per slot (stable across ticks within one day)
    seed = campaign.id * 100000 + now.toordinal()
    rng = random.Random(seed)

    slot_interval = window_mins / daily_limit
    max_jitter = min(15.0, slot_interval / 3)  # cap jitter for dense schedules

    slots_due = 0
    for i in range(daily_limit):
        ideal_mins = (i + 0.5) * slot_interval
        jitter = rng.uniform(-max_jitter, max_jitter)
        slot_time = max(0.0, min(float(window_mins), ideal_mins + jitter))
        if current_mins >= slot_time:
            slots_due += 1

    remaining = max(0, slots_due - cold_sent_today)

    # Cap catch-up: never burst more than 2 in one tick
    return min(remaining, 2)


# ── Human-like delay helpers ─────────────────────────────────────────

def _human_delay(base_min: float, base_max: float, campaign: TgCampaign,
                 messages_sent_today: int = 0,
                 session_age_days: int | None = None) -> float:
    """Generate a human-like delay between messages.

    Mixture distribution instead of flat uniform:
      65% — normal (gaussian around midpoint of base range)
      23% — medium "thinking / reading" pause  (1.2×–2.5× base_max)
      12% — long "distracted / coffee" pause   (2.5×–5× base_max, ≤120 s)

    Modulated by:
      - Time of day: ~1.4× slower at edges of the send window
      - Account fatigue: +2 % per message after the first 5 (capped at +50 %)
      - Young session: ×1.8 for sessions < 7 days old
    """
    roll = random.random()

    if roll < 0.65:
        mid = (base_min + base_max) / 2
        sigma = (base_max - base_min) / 3
        delay = max(base_min * 0.8, random.gauss(mid, sigma))
    elif roll < 0.88:
        delay = random.uniform(base_max * 1.2, base_max * 2.5)
    else:
        delay = random.uniform(base_max * 2.5, min(base_max * 5, 120))

    # Time-of-day modulation: slower at start/end of send window
    try:
        now = now_in_tz(campaign.timezone or "UTC")
        hour_f = now.hour + now.minute / 60.0
        from_h = campaign.send_from_hour
        to_h = campaign.send_to_hour
        window = (to_h - from_h) if to_h > from_h else (24 - from_h + to_h)
        if window > 0:
            progress = ((hour_f - from_h) % 24) / window  # 0..1
            edge_mult = 1.0 + 0.4 * (2 * abs(progress - 0.5)) ** 2
            delay *= edge_mult
    except Exception:
        pass

    # Account fatigue: gradually increase delays after many messages
    if messages_sent_today > 5:
        fatigue = 1.0 + 0.02 * min(messages_sent_today - 5, 25)
        delay *= fatigue

    # Young session safety: send slower to avoid triggering anti-spam
    if session_age_days is not None and session_age_days < YOUNG_SESSION_DAYS:
        delay *= YOUNG_SESSION_DELAY_MULT

    # Micro-jitter: avoid perfectly round seconds
    delay += random.uniform(0.1, 0.9)

    return round(delay, 2)


# ══════════════════════════════════════════════════════════════════════
# Sending Worker
# ══════════════════════════════════════════════════════════════════════

class SendingWorker:
    """Background worker that processes active outreach campaigns."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        # Round-robin index per campaign
        self._rr_index: dict[int, int] = {}
        # Spamblock recheck timer
        self._last_spamblock_recheck: float = 0
        self._RECHECK_INTERVAL = 30 * 60  # 30 minutes
        # Emergency stop
        self._consecutive_global_spamblocks = 0
        self._EMERGENCY_THRESHOLD = 30
        # Daily counter auto-reset (None = needs initial sync on first tick)
        self._last_reset_date = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._main_loop())
        logger.info("SendingWorker started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        logger.info("SendingWorker stopped")

    # ── Main loop ─────────────────────────────────────────────────────

    async def _main_loop(self):
        """Top-level loop: iterate over active campaigns every ~5 seconds."""
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception as e:
                    logger.error(f"Worker tick error: {e}", exc_info=True)

                # Sleep 5s but wake on stop
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                    break  # stop_event was set
                except asyncio.TimeoutError:
                    pass  # normal: just loop again
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            logger.info("SendingWorker loop exited")

    async def _tick(self):
        """Process one round across all active campaigns."""
        import time

        # Sync daily counters: on first tick (startup) and on calendar day change
        today = datetime.utcnow().date()
        if self._last_reset_date is None or today != self._last_reset_date:
            logger.info(f"Counter sync triggered: last_reset={self._last_reset_date}, today={today}")
            await self._sync_daily_counters()
            self._last_reset_date = today

        # Periodically recheck spamblocked accounts (every 30 min)
        now_ts = time.monotonic()
        if now_ts - self._last_spamblock_recheck > self._RECHECK_INTERVAL:
            self._last_spamblock_recheck = now_ts
            await self._recheck_spamblocked_accounts()

        async with async_session_maker() as session:
            # Find active campaigns
            result = await session.execute(
                select(TgCampaign).where(TgCampaign.status == TgCampaignStatus.ACTIVE)
            )
            campaigns = result.scalars().all()

            if not campaigns:
                return  # no active campaigns — silent

            for campaign in campaigns:
                try:
                    await self._process_campaign(campaign, session)
                except Exception as e:
                    logger.error(f"[Campaign {campaign.id} '{campaign.name}'] Error: {e}", exc_info=True)

            await session.commit()

    async def _recheck_spamblocked_accounts(self):
        """Recheck temporarily spamblocked and frozen accounts — try to connect and check @SpamBot."""
        logger.info("Rechecking spamblocked/frozen accounts...")
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgAccount).where(
                    or_(
                        and_(
                            TgAccount.status == TgAccountStatus.SPAMBLOCKED,
                            TgAccount.spamblock_type == TgSpamblockType.TEMPORARY,
                        ),
                        TgAccount.status == TgAccountStatus.FROZEN,
                    )
                )
            )
            accounts = result.scalars().all()

            if not accounts:
                logger.info("No temporarily spamblocked accounts to recheck")
                return

            reactivated = 0
            for account in accounts:
                if not account.api_id or not account.api_hash:
                    continue
                if not telegram_engine.session_file_exists(account.phone):
                    continue
                try:
                    check = await telegram_engine.check_account(
                        account.id,
                        phone=account.phone,
                        api_id=account.api_id,
                        api_hash=account.api_hash,
                        device_model=account.device_model or "PC 64bit",
                        system_version=account.system_version or "Windows 10",
                        app_version=account.app_version or "6.5.1 x64",
                        lang_code=account.lang_code or "en",
                        system_lang_code=account.system_lang_code or "en-US",
                    )
                    # If ban detected during recheck, mark as BANNED
                    if check.get("banned"):
                        account.status = TgAccountStatus.BANNED
                        account.ban_reason = check.get("ban_reason")
                        account.banned_at = datetime.utcnow()
                        logger.warning(f"Account {account.phone} permanent ban detected during recheck")
                    elif check.get("spamblock", "unknown") == "none" and check.get("authorized"):
                        account.status = TgAccountStatus.ACTIVE
                        account.spamblock_type = TgSpamblockType.NONE
                        account.last_checked_at = datetime.utcnow()
                        reactivated += 1
                        logger.info(f"Account {account.phone} spamblock lifted — reactivated!")
                    await telegram_engine.disconnect(account.id)
                except Exception as e:
                    logger.debug(f"Recheck failed for {account.phone}: {e}")

            if reactivated:
                await session.commit()
            logger.info(f"Spamblock recheck done: {reactivated}/{len(accounts)} reactivated")

    # ── Campaign processing ───────────────────────────────────────────

    async def _process_campaign(self, campaign: TgCampaign, session: AsyncSession):
        """Process a batch of sends for this campaign in parallel (one per available account)."""
        cname = f"[Campaign {campaign.id} '{campaign.name}']"

        # Check timezone window
        if not is_within_send_window(campaign):
            logger.debug(f"{cname} Outside send window")
            return

        # Count cold sends (step_order=1) today — daily limit applies to cold only
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cold_counts_r = await session.execute(
            select(
                TgOutreachMessage.account_id,
                func.count(TgOutreachMessage.id),
            ).join(TgSequenceStep, TgOutreachMessage.step_id == TgSequenceStep.id)
            .where(
                TgOutreachMessage.status == TgMessageStatus.SENT,
                TgOutreachMessage.sent_at >= today_start,
                TgSequenceStep.step_order == 1,
            ).group_by(TgOutreachMessage.account_id)
        )
        account_cold_counts = {row[0]: row[1] for row in cold_counts_r.all()}

        # Count cold sends per account in the last hour (hard limit: 2/hr/account)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        hourly_counts_r = await session.execute(
            select(
                TgOutreachMessage.account_id,
                func.count(TgOutreachMessage.id),
            ).join(TgSequenceStep, TgOutreachMessage.step_id == TgSequenceStep.id)
            .where(
                TgOutreachMessage.status == TgMessageStatus.SENT,
                TgOutreachMessage.sent_at >= hour_ago,
                TgSequenceStep.step_order == 1,
            ).group_by(TgOutreachMessage.account_id)
        )
        account_hourly_cold = {row[0]: row[1] for row in hourly_counts_r.all()}

        # Follow-ups are UNLIMITED — don't count against daily limit
        followup_recipients = await self._pick_recipients_by_type(
            campaign.id, "followup", 500, session)

        # Get available accounts for new leads (filtered by cold limit)
        available_accounts = await self._get_available_accounts(campaign, session, account_cold_counts, account_hourly_cold)

        # New leads: spread evenly across schedule window (cold only)
        cold_remaining = 500
        if campaign.daily_message_limit:
            camp_cold_r = await session.execute(
                select(func.count(TgOutreachMessage.id))
                .join(TgSequenceStep, TgOutreachMessage.step_id == TgSequenceStep.id)
                .where(
                    TgOutreachMessage.campaign_id == campaign.id,
                    TgOutreachMessage.status == TgMessageStatus.SENT,
                    TgOutreachMessage.sent_at >= today_start,
                    TgSequenceStep.step_order == 1,
                )
            )
            cold_sent_today = camp_cold_r.scalar() or 0
            cold_remaining = _calc_spread_allowance(campaign, cold_sent_today)
            if cold_remaining == 0 and cold_sent_today < campaign.daily_message_limit:
                now_local = now_in_tz(campaign.timezone or "UTC")
                mins_left = ((campaign.send_to_hour * 60) - (now_local.hour * 60 + now_local.minute)) % (24 * 60)
                if mins_left < 60:
                    deferred = campaign.daily_message_limit - cold_sent_today
                    logger.info(f"{cname} Window ending in {mins_left}min — {deferred} cold messages deferred to tomorrow")
            logger.debug(f"{cname} Spread: {cold_sent_today}/{campaign.daily_message_limit} sent, {cold_remaining} allowed this tick")

        new_lead_limit = min(cold_remaining, len(available_accounts)) if available_accounts else 0
        new_recipients = await self._pick_recipients_by_type(
            campaign.id, "new", new_lead_limit, session) if new_lead_limit > 0 else []

        # Collect batch
        batch: list[tuple] = []  # [(recipient, account, proxy_dict, step, variant, rendered)]
        account_pending: dict[int, int] = {}  # account_id -> all messages pending in this batch
        account_cold_pending: dict[int, int] = {}  # cold sends pending in this batch
        skipped_recipient_ids: set[int] = set()

        all_recipients = followup_recipients + new_recipients

        cold_in_batch = 0
        for recipient in all_recipients:
            is_cold = recipient.current_step == 0
            # Daily limit only applies to cold sends (step 0); follow-ups are unlimited
            if is_cold and campaign.daily_message_limit and cold_in_batch >= cold_remaining:
                continue

            step, variant = await self._get_step_and_variant(campaign.id, recipient.current_step, session)
            if not step or not variant:
                recipient.status = TgRecipientStatus.COMPLETED
                logger.info(f"{cname} @{recipient.username} completed (no more steps)")
                continue

            # Pick account: follow-ups are bound to their assigned account (rules 3-5)
            account = None
            proxy_dict = None
            if recipient.assigned_account_id and recipient.current_step > 0:
                account = await session.get(TgAccount, recipient.assigned_account_id)
                if not account:
                    # Account deleted from DB — lead stays stuck (rule 4)
                    logger.warning(f"{cname} @{recipient.username} follow-up bound to missing account_id={recipient.assigned_account_id} — skipping")
                    skipped_recipient_ids.add(recipient.id)
                    continue
                if account.status != TgAccountStatus.ACTIVE:
                    # Bound account unavailable — do NOT reassign (rules 3-5)
                    # Follow-ups bypass daily limit — only check active status
                    logger.info(f"{cname} @{recipient.username} follow-up bound to {account.phone} but unavailable — skipping, will retry later")
                    skipped_recipient_ids.add(recipient.id)
                    continue

            if not account:
                # Round-robin, skip accounts at limit + failed for this recipient
                failed_for = set((recipient.custom_variables or {}).get("_failed_account_ids", []))
                for acc in sorted(available_accounts, key=lambda a: account_pending.get(a.id, 0)):
                    acc_cold = account_cold_counts.get(acc.id, 0) + account_cold_pending.get(acc.id, 0)
                    acc_hourly = account_hourly_cold.get(acc.id, 0) + account_cold_pending.get(acc.id, 0)
                    if acc.id not in failed_for and acc_cold < get_effective_daily_limit(acc) and acc_hourly < MAX_COLD_PER_HOUR_PER_ACCOUNT:
                        account = acc
                        break
                if not account:
                    skipped_recipient_ids.add(recipient.id)
                    logger.info(f"{cname} No available account for @{recipient.username} — skipping, will retry next tick")
                    continue

            # Load proxy (auto-reassign if dead/missing)
            if account.assigned_proxy_id:
                p = await session.get(TgProxy, account.assigned_proxy_id)
                if p and p.is_active:
                    proxy_dict = {"host": p.host, "port": p.port, "username": p.username,
                                  "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}
                else:
                    reason = "not found" if not p else "dead"
                    logger.warning(f"{cname} Account {account.phone}: proxy {account.assigned_proxy_id} {reason}, reassigning...")
                    account.assigned_proxy_id = None
                    new_p = await self._try_reassign_proxy(account, session)
                    if new_p:
                        proxy_dict = {"host": new_p.host, "port": new_p.port, "username": new_p.username,
                                      "password": new_p.password, "protocol": new_p.protocol.value if hasattr(new_p.protocol, 'value') else new_p.protocol}
                        logger.info(f"{cname} Account {account.phone}: reassigned to proxy {new_p.host}:{new_p.port}")
                    else:
                        logger.warning(f"{cname} Account {account.phone}: no free proxy in group — skipping")
                        continue
            elif account.proxy_group_id:
                # Has group but no individual proxy — auto-assign
                new_p = await self._try_reassign_proxy(account, session)
                if new_p:
                    proxy_dict = {"host": new_p.host, "port": new_p.port, "username": new_p.username,
                                  "password": new_p.password, "protocol": new_p.protocol.value if hasattr(new_p.protocol, 'value') else new_p.protocol}
                    logger.info(f"{cname} Account {account.phone}: auto-assigned proxy {new_p.host}:{new_p.port}")
                else:
                    logger.warning(f"{cname} Account {account.phone}: no free proxy in group — skipping")
                    continue
            else:
                logger.warning(f"{cname} Account {account.phone} has NO proxy assigned — will connect directly")

            # Render message
            variables = {
                "first_name": recipient.first_name or "",
                "company_name": recipient.company_name or "",
                "username": recipient.username or "",
            }
            if recipient.custom_variables:
                variables.update(recipient.custom_variables)
            rendered = substitute_variables(variant.message_text, variables)
            rendered = resolve_spintax(rendered)
            if not rendered.strip():
                continue

            # Mark recipient as being processed (prevent double-pick)
            recipient.status = TgRecipientStatus.IN_SEQUENCE
            account_pending[account.id] = account_pending.get(account.id, 0) + 1
            batch.append((recipient, account, proxy_dict, step, variant, rendered))
            if is_cold:
                cold_in_batch += 1
                account_cold_pending[account.id] = account_cold_pending.get(account.id, 0) + 1

        if not batch:
            logger.debug(f"{cname} No recipients to send to")
            return

        # Shuffle batch so account activation order varies each tick
        random.shuffle(batch)

        logger.info(f"{cname} Sending batch of {len(batch)} messages...")

        # Stagger interval: accounts activate 2-5 s apart instead of all at once
        stagger_base = random.uniform(2.0, 5.0) if len(batch) > 1 else 0

        async def _send_one(recipient, account, proxy_dict, step, variant, rendered, stagger_offset=0):
            # Stagger: offset this account's activation
            if stagger_offset > 0:
                await asyncio.sleep(stagger_offset)

            def _reset_recipient():
                """Reset recipient so it's not stuck in IN_SEQUENCE forever."""
                if recipient.current_step == 0:
                    recipient.status = TgRecipientStatus.PENDING
                else:
                    recipient.next_message_at = datetime.utcnow()

            try:
                await telegram_engine.connect(
                    account.id, phone=account.phone, api_id=account.api_id, api_hash=account.api_hash,
                    device_model=account.device_model or "PC 64bit", system_version=account.system_version or "Windows 10",
                    app_version=account.app_version or "6.5.1 x64", lang_code=account.lang_code or "en",
                    system_lang_code=account.system_lang_code or "en-US", proxy=proxy_dict,
                )
            except Exception as e:
                logger.error(f"Connect failed for {account.phone}: {e}")
                _reset_recipient()
                return

            try:
                # Safety: re-check if recipient already replied (race with reply_detector)
                await session.refresh(recipient)
                if recipient.status == TgRecipientStatus.REPLIED:
                    logger.info(f"{cname} @{recipient.username} already replied — skipping follow-up")
                    return
                # Also check for incoming reply records not yet processed by reply_detector
                if recipient.current_step > 0:
                    reply_exists = await session.execute(
                        select(TgIncomingReply.id).where(
                            TgIncomingReply.recipient_id == recipient.id,
                        ).limit(1)
                    )
                    if reply_exists.scalar():
                        recipient.status = TgRecipientStatus.REPLIED
                        recipient.next_message_at = None
                        logger.info(f"{cname} @{recipient.username} has incoming reply record — marking REPLIED, skipping follow-up")
                        return

                # Human-like pre-send delay (hardcoded base range)
                delay = _human_delay(
                    DELAY_BASE_MIN,
                    DELAY_BASE_MAX,
                    campaign,
                    messages_sent_today=account.messages_sent_today,
                    session_age_days=get_session_age_days(account),
                )
                logger.debug(f"{cname} {account.phone} delay={delay}s")
                await asyncio.sleep(delay)

                result = await telegram_engine.send_message(
                    account.id, recipient.username, rendered,
                    link_preview=getattr(campaign, 'link_preview', False),
                    silent=getattr(campaign, 'silent', False),
                    delete_dialog_after=getattr(campaign, 'delete_dialog_after', False),
                )
                status = result.get("status", "failed")
                logger.info(f"{cname} {account.phone} -> @{recipient.username}: {status}"
                             + (f" ({result.get('detail','')})" if status != "sent" else ""))

                # Log message
                msg_status = TgMessageStatus.SPAMBLOCKED if status == "spamblocked" else (TgMessageStatus.SENT if status == "sent" else TgMessageStatus.FAILED)
                session.add(TgOutreachMessage(
                    campaign_id=campaign.id, recipient_id=recipient.id, account_id=account.id,
                    step_id=step.id, variant_id=variant.id, rendered_text=rendered,
                    status=msg_status, error_message=result.get("detail"), sent_at=datetime.utcnow(),
                ))

                # Fetch campaign-account link for per-account spamblock counter
                ca_link_r = await session.execute(select(TgCampaignAccount).where(
                    TgCampaignAccount.campaign_id == campaign.id,
                    TgCampaignAccount.account_id == account.id))
                ca_link = ca_link_r.scalar()

                # Update counters
                if status == "sent":
                    self._consecutive_global_spamblocks = 0  # reset emergency counter
                    if ca_link:
                        ca_link.consecutive_spamblock_errors = 0
                    account.messages_sent_today += 1
                    account.total_messages_sent += 1
                    campaign.messages_sent_today += 1
                    campaign.total_messages_sent += 1
                    recipient.current_step += 1
                    recipient.last_message_sent_at = datetime.utcnow()
                    recipient.assigned_account_id = account.id

                    # CRM: create/update contact
                    try:
                        crm_q = await session.execute(
                            select(TgContact).where(TgContact.username == recipient.username)
                        )
                        contact = crm_q.scalar()
                        now = datetime.utcnow()
                        if not contact:
                            contact = TgContact(
                                username=recipient.username,
                                first_name=recipient.first_name,
                                company_name=recipient.company_name,
                                status=TgContactStatus.CONTACTED,
                                custom_data=recipient.custom_variables or {},
                                campaigns=[{"id": campaign.id, "name": campaign.name}],
                                total_messages_sent=1,
                                first_contacted_at=now,
                                last_contacted_at=now,
                                source_campaign_id=campaign.id,
                            )
                            session.add(contact)
                        else:
                            contact.total_messages_sent += 1
                            contact.last_contacted_at = now
                            if contact.status == TgContactStatus.COLD:
                                contact.status = TgContactStatus.CONTACTED
                            # Add campaign if not already
                            camp_list = contact.campaigns or []
                            if not any(c.get("id") == campaign.id for c in camp_list):
                                camp_list.append({"id": campaign.id, "name": campaign.name})
                                contact.campaigns = camp_list
                    except Exception:
                        pass  # CRM is best-effort
                    next_step = await self._get_next_step(campaign.id, recipient.current_step, session)
                    if next_step and next_step.delay_days > 0:
                        recipient.next_message_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
                    elif next_step:
                        recipient.next_message_at = datetime.utcnow()
                    else:
                        recipient.status = TgRecipientStatus.COMPLETED
                        recipient.next_message_at = None
                elif status == "spamblocked":
                    # Increment per-account spamblock counter
                    if ca_link:
                        ca_link.consecutive_spamblock_errors += 1
                    # Only mark SPAMBLOCKED when threshold reached (hardcoded)
                    threshold = SPAMBLOCK_THRESHOLD
                    errors_count = ca_link.consecutive_spamblock_errors if ca_link else 1
                    if errors_count >= threshold:
                        account.status = TgAccountStatus.SPAMBLOCKED
                        account.spamblock_type = TgSpamblockType.TEMPORARY
                        account.spamblocked_at = datetime.utcnow()
                        logger.warning(f"{cname} {account.phone} spamblock threshold reached "
                                       f"({errors_count}/{threshold}) — SPAMBLOCKED TEMPORARY")
                    else:
                        logger.warning(f"{cname} {account.phone} PeerFloodError "
                                       f"({errors_count}/{threshold}) — below threshold")
                    if recipient.current_step == 0:
                        # First message: cascade to another account
                        failed_ids = (recipient.custom_variables or {}).get("_failed_account_ids", [])
                        failed_ids.append(account.id)
                        if not recipient.custom_variables:
                            recipient.custom_variables = {}
                        recipient.custom_variables = {**recipient.custom_variables, "_failed_account_ids": failed_ids}
                        total_accs_r = await session.execute(select(func.count(TgCampaignAccount.id)).where(
                            TgCampaignAccount.campaign_id == campaign.id))
                        total_campaign_accounts = total_accs_r.scalar() or 0
                        if len(failed_ids) >= total_campaign_accounts:
                            recipient.status = TgRecipientStatus.FAILED
                            recipient.next_message_at = None
                            logger.info(f"All accounts spamblocked for @{recipient.username} — FAILED")
                        else:
                            recipient.status = TgRecipientStatus.PENDING
                            recipient.assigned_account_id = None
                            logger.info(f"Spamblock cascade @{recipient.username} via {account.phone} ({len(failed_ids)}/{total_campaign_accounts})")
                    else:
                        # Follow-up: lead stays bound to this account (rules 3-5)
                        recipient.next_message_at = datetime.utcnow() + timedelta(hours=1)
                        logger.info(f"{cname} @{recipient.username} follow-up spamblocked via {account.phone} — retry in 1h (bound)")
                    # Emergency stop check
                    self._consecutive_global_spamblocks += 1
                    if self._consecutive_global_spamblocks >= self._EMERGENCY_THRESHOLD:
                        logger.critical(f"EMERGENCY STOP: {self._consecutive_global_spamblocks} consecutive spamblocks!")
                        all_active = await session.execute(select(TgCampaign).where(TgCampaign.status == TgCampaignStatus.ACTIVE))
                        for c in all_active.scalars().all():
                            c.status = TgCampaignStatus.PAUSED
                elif status == "bounced":
                    if ca_link:
                        ca_link.consecutive_spamblock_errors = 0
                    recipient.status = TgRecipientStatus.BOUNCED
                    recipient.next_message_at = None
                elif status == "flood":
                    if ca_link:
                        ca_link.consecutive_spamblock_errors = 0
                    wait = result.get("wait_seconds", 60)
                    recipient.next_message_at = datetime.utcnow() + timedelta(seconds=wait)
                    recipient.status = TgRecipientStatus.PENDING  # retry later
                else:
                    if ca_link:
                        ca_link.consecutive_spamblock_errors = 0
                    if recipient.current_step == 0:
                        # First message: cascade to another account (rule 1)
                        failed_ids = (recipient.custom_variables or {}).get("_failed_account_ids", [])
                        failed_ids.append(account.id)
                        if not recipient.custom_variables:
                            recipient.custom_variables = {}
                        recipient.custom_variables = {**recipient.custom_variables, "_failed_account_ids": failed_ids}
                        total_accs_r = await session.execute(select(func.count(TgCampaignAccount.id)).where(
                            TgCampaignAccount.campaign_id == campaign.id))
                        total_campaign_accounts = total_accs_r.scalar() or 0
                        if len(failed_ids) >= total_campaign_accounts:
                            recipient.status = TgRecipientStatus.FAILED
                            recipient.next_message_at = None
                            logger.info(f"{cname} All accounts failed for @{recipient.username} — FAILED")
                        else:
                            recipient.status = TgRecipientStatus.PENDING
                            recipient.assigned_account_id = None
                            logger.info(f"{cname} Error cascade @{recipient.username} via {account.phone} ({len(failed_ids)}/{total_campaign_accounts})")
                    else:
                        # Follow-up: keep bound, retry later (rules 3-5)
                        recipient.next_message_at = datetime.utcnow() + timedelta(hours=1)
                        logger.info(f"{cname} @{recipient.username} follow-up failed via {account.phone} — retry in 1h (bound)")
            except Exception as e:
                logger.error(f"{cname} Unhandled error in _send_one for @{recipient.username}: {e}", exc_info=True)
                _reset_recipient()

            # NOTE: do NOT disconnect here — other coroutines for the same
            # account may still be sending.  Disconnect happens after gather.

        tasks = []
        for i, (recipient, account, proxy_dict, step, variant, rendered) in enumerate(batch):
            offset = i * stagger_base + random.uniform(-0.5, 0.5)
            offset = max(0, offset)
            tasks.append(_send_one(recipient, account, proxy_dict, step, variant, rendered, offset))
        await asyncio.gather(*tasks, return_exceptions=True)

        # ── Post-batch: disconnect accounts & sync counters from real data ──
        batch_account_ids = {account.id for _, account, _, _, _, _ in batch}
        for acc_id in batch_account_ids:
            await telegram_engine.disconnect(acc_id)

        # Flush so new TgOutreachMessage rows are visible to COUNT queries
        await session.flush()
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for acc_id in batch_account_ids:
            count_r = await session.execute(
                select(func.count(TgOutreachMessage.id)).where(
                    TgOutreachMessage.account_id == acc_id,
                    TgOutreachMessage.status == TgMessageStatus.SENT,
                    TgOutreachMessage.sent_at >= today_start,
                )
            )
            real_count = count_r.scalar() or 0
            acc = await session.get(TgAccount, acc_id)
            if acc and acc.messages_sent_today != real_count:
                logger.warning(f"Counter drift for account {acc.phone}: counter={acc.messages_sent_today}, actual={real_count}")
                acc.messages_sent_today = real_count

        camp_count_r = await session.execute(
            select(func.count(TgOutreachMessage.id)).where(
                TgOutreachMessage.campaign_id == campaign.id,
                TgOutreachMessage.status == TgMessageStatus.SENT,
                TgOutreachMessage.sent_at >= today_start,
            )
        )
        real_camp_count = camp_count_r.scalar() or 0
        if campaign.messages_sent_today != real_camp_count:
            logger.warning(f"Counter drift for campaign '{campaign.name}': counter={campaign.messages_sent_today}, actual={real_camp_count}")
            campaign.messages_sent_today = real_camp_count

    async def _get_available_accounts(self, campaign: TgCampaign, session: AsyncSession,
                                      account_cold_counts: dict[int, int] | None = None,
                                      account_hourly_cold: dict[int, int] | None = None) -> list[TgAccount]:
        """Get accounts for campaign that haven't hit their cold-send limit.
        Daily limit only counts cold sends (step 0); follow-ups are unlimited."""
        today = datetime.utcnow().date()
        result = await session.execute(
            select(TgAccount)
            .join(TgCampaignAccount, TgCampaignAccount.account_id == TgAccount.id)
            .where(
                TgCampaignAccount.campaign_id == campaign.id,
                TgAccount.status.in_([TgAccountStatus.ACTIVE, TgAccountStatus.SPAMBLOCKED]),
            ).order_by(TgAccount.id)
        )
        accounts = list(result.scalars().all())
        filtered = []
        young_count = 0
        for acc in accounts:
            if not telegram_engine.session_file_exists(acc.phone):
                continue
            # Spamblocked today → skip rest of day
            if acc.status == TgAccountStatus.SPAMBLOCKED:
                if acc.spamblocked_at and acc.spamblocked_at.date() == today:
                    continue
            # Warm-up aware limit check — cold sends only (follow-ups unlimited)
            cold_used = (account_cold_counts or {}).get(acc.id, 0)
            if cold_used >= get_effective_daily_limit(acc):
                continue
            # Hourly cold limit: max 2 cold messages per hour per account
            hourly_used = (account_hourly_cold or {}).get(acc.id, 0)
            if hourly_used >= MAX_COLD_PER_HOUR_PER_ACCOUNT:
                continue
            if is_young_session(acc):
                young_count += 1
            filtered.append(acc)
        if young_count:
            logger.info(f"Campaign {campaign.name}: {young_count}/{len(filtered)} accounts are young sessions (<{YOUNG_SESSION_DAYS}d)")
        return filtered

    # ── Recipient selection ───────────────────────────────────────────

    async def _pick_recipients_by_type(
        self, campaign_id: int, rtype: str, limit: int,
        session: AsyncSession, exclude_ids: set[int] | None = None,
    ) -> list[TgRecipient]:
        """Pick recipients by type: 'followup' (IN_SEQUENCE + due) or 'new' (PENDING)."""
        if limit <= 0:
            return []
        now = datetime.utcnow()
        if rtype == "followup":
            q = select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id,
                TgRecipient.status == TgRecipientStatus.IN_SEQUENCE,
                TgRecipient.next_message_at <= now,
            ).order_by(TgRecipient.next_message_at)
        else:
            q = select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id,
                TgRecipient.status == TgRecipientStatus.PENDING,
            ).order_by(TgRecipient.id)
        if exclude_ids:
            q = q.where(TgRecipient.id.notin_(exclude_ids))
        result = await session.execute(q.limit(limit))
        return list(result.scalars().all())

    async def _pick_recipient(self, campaign_id: int, session: AsyncSession, exclude_ids: set[int] | None = None) -> Optional[TgRecipient]:
        """Pick next due recipient (legacy, used as fallback)."""
        fus = await self._pick_recipients_by_type(campaign_id, "followup", 1, session, exclude_ids)
        if fus:
            return fus[0]
        news = await self._pick_recipients_by_type(campaign_id, "new", 1, session, exclude_ids)
        return news[0] if news else None

    # ── Account selection (round-robin) ───────────────────────────────

    # _pick_account replaced by _get_available_accounts + batch logic in _process_campaign

    # ── Proxy auto-assignment ────────────────────────────────────────

    async def _try_reassign_proxy(self, account: TgAccount, session: AsyncSession) -> TgProxy | None:
        """Try to assign a free active proxy from the account's proxy group."""
        if not account.proxy_group_id:
            return None
        # Find proxy IDs already assigned to other active accounts
        assigned_q = (
            select(TgAccount.assigned_proxy_id)
            .where(
                TgAccount.assigned_proxy_id.isnot(None),
                TgAccount.id != account.id,
                TgAccount.status.in_([
                    TgAccountStatus.ACTIVE, TgAccountStatus.PAUSED,
                    TgAccountStatus.FROZEN, TgAccountStatus.SPAMBLOCKED,
                ]),
            )
        )
        assigned_result = await session.execute(assigned_q)
        assigned_ids = {r[0] for r in assigned_result.all()}

        proxy_q = (
            select(TgProxy)
            .where(TgProxy.proxy_group_id == account.proxy_group_id, TgProxy.is_active == True)
        )
        if assigned_ids:
            proxy_q = proxy_q.where(~TgProxy.id.in_(assigned_ids))
        result = await session.execute(proxy_q.order_by(TgProxy.id).limit(1))
        proxy = result.scalar()
        if proxy:
            account.assigned_proxy_id = proxy.id
            return proxy
        return None

    # ── Sequence helpers ──────────────────────────────────────────────

    async def _get_step_and_variant(
        self, campaign_id: int, current_step: int, session: AsyncSession
    ) -> tuple[Optional[TgSequenceStep], Optional[TgStepVariant]]:
        """Get the sequence step for current_step index and pick a variant."""
        seq_result = await session.execute(
            select(TgSequence).where(TgSequence.campaign_id == campaign_id)
        )
        seq = seq_result.scalar()
        if not seq:
            return None, None

        step_result = await session.execute(
            select(TgSequenceStep)
            .where(TgSequenceStep.sequence_id == seq.id, TgSequenceStep.step_order == current_step + 1)
            .options(selectinload(TgSequenceStep.variants))
        )
        step = step_result.scalar()
        if not step or not step.variants:
            return None, None

        variant = pick_variant(step.variants)
        return step, variant

    async def _get_next_step(
        self, campaign_id: int, next_step_index: int, session: AsyncSession
    ) -> Optional[TgSequenceStep]:
        """Check if a next step exists in the sequence."""
        seq_result = await session.execute(
            select(TgSequence).where(TgSequence.campaign_id == campaign_id)
        )
        seq = seq_result.scalar()
        if not seq:
            return None

        step_result = await session.execute(
            select(TgSequenceStep).where(
                TgSequenceStep.sequence_id == seq.id,
                TgSequenceStep.step_order == next_step_index + 1,
            )
        )
        return step_result.scalar()

    # ── Daily counter sync ───────────────────────────────────────────

    async def _sync_daily_counters(self):
        """Sync daily counters from actual sent messages.

        On mid-day restart: counts real messages sent today so counters
        stay accurate and daily limits are respected.
        On new calendar day (no messages today): resets everything to 0.
        """
        async with async_session_maker() as session:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # Count today's sent messages per account (single GROUP BY query)
            acc_counts_r = await session.execute(
                select(
                    TgOutreachMessage.account_id,
                    func.count(TgOutreachMessage.id),
                ).where(
                    TgOutreachMessage.status == TgMessageStatus.SENT,
                    TgOutreachMessage.sent_at >= today_start,
                ).group_by(TgOutreachMessage.account_id)
            )
            acc_counts = dict(acc_counts_r.all())

            # Count today's sent messages per campaign
            camp_counts_r = await session.execute(
                select(
                    TgOutreachMessage.campaign_id,
                    func.count(TgOutreachMessage.id),
                ).where(
                    TgOutreachMessage.status == TgMessageStatus.SENT,
                    TgOutreachMessage.sent_at >= today_start,
                ).group_by(TgOutreachMessage.campaign_id)
            )
            camp_counts = dict(camp_counts_r.all())

            total_today = sum(acc_counts.values()) if acc_counts else 0

            # Reset all accounts to 0, then set real counts for those with messages
            await session.execute(
                TgAccount.__table__.update().values(messages_sent_today=0)
            )
            for acc_id, cnt in acc_counts.items():
                await session.execute(
                    TgAccount.__table__.update()
                    .where(TgAccount.__table__.c.id == acc_id)
                    .values(messages_sent_today=cnt)
                )

            # Reset all campaigns to 0, then set real counts
            await session.execute(
                TgCampaign.__table__.update().values(messages_sent_today=0)
            )
            for camp_id, cnt in camp_counts.items():
                await session.execute(
                    TgCampaign.__table__.update()
                    .where(TgCampaign.__table__.c.id == camp_id)
                    .values(messages_sent_today=cnt)
                )

            # Reset spamblock counters only on a true new day (no messages today)
            if total_today == 0:
                await session.execute(
                    TgCampaignAccount.__table__.update().values(consecutive_spamblock_errors=0)
                )
                logger.info("New day: daily counters reset to 0, spamblock counters cleared")
            else:
                logger.info(f"Mid-day restart: synced counters from DB ({total_today} messages sent today)")

            await session.commit()


# Singleton
sending_worker = SendingWorker()
