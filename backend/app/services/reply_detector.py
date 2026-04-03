"""
Reply Detector — monitors outreach accounts for incoming messages from recipients.

Runs as a background loop alongside the sending worker.
For each active campaign, connects assigned accounts and checks for new
messages from known recipients. On reply detection:
  1. Creates TgIncomingReply record
  2. Updates recipient status to REPLIED
  3. Logs the event
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.telegram_outreach import (
    TgCampaign, TgCampaignAccount, TgCampaignStatus,
    TgAccount, TgAccountStatus,
    TgRecipient, TgRecipientStatus,
    TgIncomingReply, TgOutreachMessage,
    TgProxy,
)
from app.services.telegram_engine import telegram_engine
from app.services.infatica_proxy_service import infatica_proxy_service

logger = logging.getLogger(__name__)


class ReplyDetector:
    """Background service that polls for incoming replies."""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        # Track last checked message per (account_id, peer_username) to avoid duplicates
        self._last_seen: dict[tuple[int, str], int] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._main_loop())
        logger.info("ReplyDetector started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        logger.info("ReplyDetector stopped")

    async def _main_loop(self):
        """Poll every 30 seconds for new replies."""
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception as e:
                    logger.error(f"ReplyDetector tick error: {e}", exc_info=True)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=30.0)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            logger.info("ReplyDetector loop exited")

    async def _tick(self):
        """Check all active campaigns for replies."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgCampaign).where(TgCampaign.status == TgCampaignStatus.ACTIVE)
            )
            campaigns = result.scalars().all()

            for campaign in campaigns:
                try:
                    await self._check_campaign_replies(campaign, session)
                except Exception as e:
                    logger.error(f"Reply check failed for campaign {campaign.id}: {e}")

            await session.commit()

    async def _check_campaign_replies(self, campaign: TgCampaign, session: AsyncSession):
        """For each account in campaign, check dialogs for replies from recipients."""

        # Get campaign accounts that are active
        acc_result = await session.execute(
            select(TgAccount)
            .join(TgCampaignAccount, TgCampaignAccount.account_id == TgAccount.id)
            .where(
                TgCampaignAccount.campaign_id == campaign.id,
                TgAccount.status == TgAccountStatus.ACTIVE,
            )
        )
        accounts = acc_result.scalars().all()

        # Get recipients who are IN_SEQUENCE or COMPLETED (people we've messaged)
        recip_result = await session.execute(
            select(TgRecipient).where(
                TgRecipient.campaign_id == campaign.id,
                TgRecipient.status.in_([
                    TgRecipientStatus.IN_SEQUENCE,
                    TgRecipientStatus.COMPLETED,
                ]),
            )
        )
        recipients = recip_result.scalars().all()
        recipient_usernames = {r.username.lower(): r for r in recipients if r.username}

        if not recipient_usernames or not accounts:
            return

        for account in accounts:
            if not telegram_engine.session_file_exists(account.phone):
                continue

            try:
                await self._check_account_replies(
                    account, campaign, recipient_usernames, session,
                )
            except Exception as e:
                logger.warning(f"Reply check for account {account.phone}: {e}")

    async def _check_account_replies(
        self,
        account: TgAccount,
        campaign: TgCampaign,
        recipient_usernames: dict[str, TgRecipient],
        session: AsyncSession,
    ):
        """Connect account and scan recent dialogs for replies."""

        # Load proxy
        proxy_dict = None
        if account.assigned_proxy_id:
            p = await session.get(TgProxy, account.assigned_proxy_id)
            if p:
                proxy_dict = {
                    "host": p.host, "port": p.port,
                    "username": p.username, "password": p.password,
                    "protocol": p.protocol.value if hasattr(p.protocol, 'value') else p.protocol,
                }
            else:
                logger.warning(f"[PROXY] Account {account.phone}: assigned_proxy_id={account.assigned_proxy_id} not found in DB")
        else:
            # Fallback: auto-generate Infatica proxy
            if infatica_proxy_service.is_configured:
                proxy_dict = infatica_proxy_service.get_proxy_for_account(account.phone, account.id)
                logger.info(f"[PROXY] Reply detector {account.phone}: using Infatica proxy (geo auto-detect)")
            else:
                logger.debug(f"[PROXY] Reply detector: account {account.phone} has no proxy assigned")

        # Connect
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
        except Exception as e:
            logger.debug(f"Cannot connect account {account.phone}: {e}")
            return

        if not await client.is_user_authorized():
            await telegram_engine.disconnect(account.id)
            return

        # Scan recent dialogs (last 20)
        try:
            dialogs = await client.get_dialogs(limit=20)
        except Exception as e:
            logger.warning(f"get_dialogs failed for {account.phone}: {e}")
            await telegram_engine.disconnect(account.id)
            return

        for dialog in dialogs:
            if not dialog.is_user:
                continue

            entity = dialog.entity
            username = (getattr(entity, 'username', None) or '').lower()
            if not username or username not in recipient_usernames:
                continue

            recipient = recipient_usernames[username]

            # Track read status via read_outbox_max_id
            try:
                read_outbox_max_id = getattr(dialog.dialog, 'read_outbox_max_id', 0) or 0
                if read_outbox_max_id > 0:
                    unread_msgs = await session.execute(
                        select(TgOutreachMessage).where(
                            TgOutreachMessage.campaign_id == campaign.id,
                            TgOutreachMessage.recipient_id == recipient.id,
                            TgOutreachMessage.account_id == account.id,
                            TgOutreachMessage.tg_message_id.isnot(None),
                            TgOutreachMessage.tg_message_id <= read_outbox_max_id,
                            TgOutreachMessage.read_at.is_(None),
                        )
                    )
                    for msg in unread_msgs.scalars().all():
                        msg.read_at = datetime.utcnow()
            except Exception as e:
                logger.debug(f"Read tracking failed for @{username}: {e}")

            # Check last message — is it from them (incoming)?
            last_msg = dialog.message
            if not last_msg or last_msg.out:
                # out=True means we sent it, not a reply
                continue

            msg_id = last_msg.id
            cache_key = (account.id, username)

            # Skip if already processed
            if self._last_seen.get(cache_key) == msg_id:
                continue

            # Check if we already saved this reply
            existing = await session.execute(
                select(TgIncomingReply).where(
                    TgIncomingReply.campaign_id == campaign.id,
                    TgIncomingReply.recipient_id == recipient.id,
                    TgIncomingReply.tg_message_id == msg_id,
                )
            )
            if existing.scalar():
                self._last_seen[cache_key] = msg_id
                continue

            # New reply detected!
            reply_text = last_msg.text or "[media]"
            logger.info(f"Reply detected: @{username} -> account {account.phone}: {reply_text[:50]}")

            session.add(TgIncomingReply(
                campaign_id=campaign.id,
                recipient_id=recipient.id,
                account_id=account.id,
                tg_message_id=msg_id,
                message_text=reply_text,
                received_at=(last_msg.date.replace(tzinfo=None) if last_msg.date else datetime.utcnow()),
            ))

            # Update recipient status
            recipient.status = TgRecipientStatus.REPLIED
            recipient.next_message_at = None  # Stop follow-ups

            # CRM: update/create contact with campaign CRM settings
            try:
                from app.models.telegram_outreach import TgContact, TgContactStatus
                crm_q = await session.execute(
                    select(TgContact).where(TgContact.username == username)
                )
                contact = crm_q.scalar()
                now = datetime.utcnow()

                # Determine target status from campaign settings
                target_status = TgContactStatus.REPLIED
                if campaign.crm_status_on_reply:
                    try:
                        target_status = TgContactStatus(campaign.crm_status_on_reply)
                    except ValueError:
                        pass

                if contact:
                    contact.status = target_status
                    contact.total_replies_received += 1
                    contact.last_reply_at = now
                elif getattr(campaign, 'crm_auto_create_contact', True):
                    # Auto-create CRM contact
                    contact = TgContact(
                        username=username,
                        first_name=recipient.first_name if hasattr(recipient, 'first_name') else None,
                        company_name=recipient.company_name if hasattr(recipient, 'company_name') else None,
                        status=target_status,
                        campaigns=[{"id": campaign.id, "name": campaign.name}],
                        total_replies_received=1,
                        last_reply_at=now,
                        source_campaign_id=campaign.id,
                    )
                    session.add(contact)

                # Apply campaign CRM tags
                if contact:
                    crm_tags = getattr(campaign, 'crm_tag_on_reply', None) or []
                    if crm_tags:
                        existing_tags = contact.tags or []
                        for tag in crm_tags:
                            if tag not in existing_tags:
                                existing_tags.append(tag)
                        contact.tags = existing_tags

                    # Apply campaign CRM owner
                    crm_owner = getattr(campaign, 'crm_owner_on_reply', None)
                    if crm_owner:
                        custom = contact.custom_data or {}
                        custom['owner'] = crm_owner
                        contact.custom_data = custom
            except Exception:
                logger.exception("CRM update failed for %s", username)

            self._last_seen[cache_key] = msg_id

        await telegram_engine.disconnect(account.id)


# Singleton
reply_detector = ReplyDetector()
