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
)
from app.services.telegram_engine import telegram_engine

logger = logging.getLogger(__name__)


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
        """Recheck temporarily spamblocked accounts — try to connect and check @SpamBot."""
        logger.info("Rechecking spamblocked accounts...")
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgAccount).where(
                    TgAccount.status == TgAccountStatus.SPAMBLOCKED,
                    TgAccount.spamblock_type == TgSpamblockType.TEMPORARY,
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
                    sb = check.get("spamblock", "unknown")
                    if sb == "none" and check.get("authorized"):
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

        # Check campaign daily limit
        if campaign.daily_message_limit and campaign.messages_sent_today >= campaign.daily_message_limit:
            logger.debug(f"{cname} Daily limit reached")
            return

        # Get available accounts for this campaign
        available_accounts = await self._get_available_accounts(campaign, session)
        if not available_accounts:
            logger.warning(f"{cname} No available accounts (all at limit, spamblocked, or no session)")
            return

        # Collect recipients — up to len(available_accounts)
        batch: list[tuple] = []  # [(recipient, account, proxy_dict, step, variant, rendered)]
        used_account_ids: set[int] = set()

        for _ in range(len(available_accounts)):
            if campaign.daily_message_limit and (campaign.messages_sent_today + len(batch)) >= campaign.daily_message_limit:
                break

            recipient = await self._pick_recipient(campaign.id, session)
            if not recipient:
                break

            step, variant = await self._get_step_and_variant(campaign.id, recipient.current_step, session)
            if not step or not variant:
                recipient.status = TgRecipientStatus.COMPLETED
                logger.info(f"{cname} @{recipient.username} completed (no more steps)")
                continue

            # Pick account: follow-ups use same account
            account = None
            proxy_dict = None
            if recipient.assigned_account_id and recipient.current_step > 0:
                account = await session.get(TgAccount, recipient.assigned_account_id)
                if account and (account.status != TgAccountStatus.ACTIVE or account.messages_sent_today >= account.daily_message_limit):
                    account = None

            if not account:
                # Round-robin from available, skip already used this batch
                for acc in available_accounts:
                    if acc.id not in used_account_ids:
                        account = acc
                        break
                if not account:
                    break  # all accounts used this batch

            # Load proxy
            if account.assigned_proxy_id:
                p = await session.get(TgProxy, account.assigned_proxy_id)
                if p:
                    proxy_dict = {"host": p.host, "port": p.port, "username": p.username,
                                  "password": p.password, "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol}

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
            used_account_ids.add(account.id)
            batch.append((recipient, account, proxy_dict, step, variant, rendered))

        if not batch:
            logger.debug(f"{cname} No recipients to send to")
            return

        logger.info(f"{cname} Sending batch of {len(batch)} messages...")

        # Send all in parallel
        async def _send_one(recipient, account, proxy_dict, step, variant, rendered):
            try:
                await telegram_engine.connect(
                    account.id, phone=account.phone, api_id=account.api_id, api_hash=account.api_hash,
                    device_model=account.device_model or "PC 64bit", system_version=account.system_version or "Windows 10",
                    app_version=account.app_version or "6.5.1 x64", lang_code=account.lang_code or "en",
                    system_lang_code=account.system_lang_code or "en-US", proxy=proxy_dict,
                )
            except Exception as e:
                logger.error(f"Connect failed for {account.phone}: {e}")
                return

            # Random pre-send delay (each account independently)
            delay_min = campaign.delay_between_sends_min or 11
            delay_max = campaign.delay_between_sends_max or 25
            await asyncio.sleep(random.uniform(delay_min, delay_max))

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

            # Update counters
            if status == "sent":
                self._consecutive_global_spamblocks = 0  # reset emergency counter
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
                account.status = TgAccountStatus.SPAMBLOCKED
                account.spamblock_type = TgSpamblockType.TEMPORARY
                link_r = await session.execute(select(TgCampaignAccount).where(
                    TgCampaignAccount.campaign_id == campaign.id, TgCampaignAccount.account_id == account.id))
                link = link_r.scalar()
                if link: link.consecutive_spamblock_errors += 1
                recipient.status = TgRecipientStatus.FAILED
                recipient.next_message_at = None
                # Emergency stop check
                self._consecutive_global_spamblocks += 1
                if self._consecutive_global_spamblocks >= self._EMERGENCY_THRESHOLD:
                    logger.critical(f"EMERGENCY STOP: {self._consecutive_global_spamblocks} consecutive spamblocks! Pausing all campaigns.")
                    all_active = await session.execute(select(TgCampaign).where(TgCampaign.status == TgCampaignStatus.ACTIVE))
                    for c in all_active.scalars().all():
                        c.status = TgCampaignStatus.PAUSED
            elif status == "bounced":
                recipient.status = TgRecipientStatus.BOUNCED
                recipient.next_message_at = None
            elif status == "flood":
                wait = result.get("wait_seconds", 60)
                recipient.next_message_at = datetime.utcnow() + timedelta(seconds=wait)
                recipient.status = TgRecipientStatus.PENDING  # retry later
            else:
                recipient.status = TgRecipientStatus.FAILED
                recipient.next_message_at = None

            await telegram_engine.disconnect(account.id)

        await asyncio.gather(*[_send_one(*b) for b in batch], return_exceptions=True)

    async def _get_available_accounts(self, campaign: TgCampaign, session: AsyncSession) -> list[TgAccount]:
        """Get all active accounts for campaign that are under daily limit and have sessions."""
        result = await session.execute(
            select(TgAccount)
            .join(TgCampaignAccount, TgCampaignAccount.account_id == TgAccount.id)
            .where(
                TgCampaignAccount.campaign_id == campaign.id,
                TgAccount.status == TgAccountStatus.ACTIVE,
                TgAccount.messages_sent_today < TgAccount.daily_message_limit,
            ).order_by(TgAccount.id)
        )
        accounts = list(result.scalars().all())
        # Filter: must have session + under spamblock threshold
        filtered = []
        for acc in accounts:
            if not telegram_engine.session_file_exists(acc.phone):
                continue
            link_r = await session.execute(select(TgCampaignAccount).where(
                TgCampaignAccount.campaign_id == campaign.id, TgCampaignAccount.account_id == acc.id))
            link = link_r.scalar()
            if link and link.consecutive_spamblock_errors >= (campaign.spamblock_errors_to_skip or 5):
                continue
            filtered.append(acc)
        return filtered

    # ── Recipient selection ───────────────────────────────────────────

    async def _pick_recipient(self, campaign_id: int, session: AsyncSession) -> Optional[TgRecipient]:
        """Pick next due recipient: PENDING (step 0) or IN_SEQUENCE with next_message_at <= now."""
        now = datetime.utcnow()

        # Priority 1: follow-ups that are due
        result = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id,
                TgRecipient.status == TgRecipientStatus.IN_SEQUENCE,
                TgRecipient.next_message_at <= now,
            ).order_by(TgRecipient.next_message_at).limit(1)
        )
        recipient = result.scalar()
        if recipient:
            return recipient

        # Priority 2: new pending recipients
        result = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign_id,
                TgRecipient.status == TgRecipientStatus.PENDING,
            ).order_by(TgRecipient.id).limit(1)
        )
        return result.scalar()

    # ── Account selection (round-robin) ───────────────────────────────

    # _pick_account replaced by _get_available_accounts + batch logic in _process_campaign

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

    # ── Daily counter reset ───────────────────────────────────────────

    async def reset_daily_counters(self):
        """Reset messages_sent_today on all accounts and campaigns. Call once per day."""
        async with async_session_maker() as session:
            await session.execute(
                TgAccount.__table__.update().values(messages_sent_today=0)
            )
            await session.execute(
                TgCampaign.__table__.update().values(messages_sent_today=0)
            )
            # Reset consecutive spamblock counters
            await session.execute(
                TgCampaignAccount.__table__.update().values(consecutive_spamblock_errors=0)
            )
            await session.commit()
        logger.info("Daily counters reset")


# Singleton
sending_worker = SendingWorker()
