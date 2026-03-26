"""Inbox sync service — scans all active TG accounts for dialogs."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_outreach import (
    TgAccount, TgAccountStatus, TgInboxDialog, TgCampaign, TgCampaignAccount,
    TgRecipient, TgRecipientStatus,
)
from app.services.telegram_engine import telegram_engine

logger = logging.getLogger(__name__)


def _build_connect_kwargs(account, proxy_row=None) -> dict:
    """Build kwargs for telegram_engine.connect(), matching _account_connect_kwargs format."""
    proxy = None
    if proxy_row:
        proxy = {
            "host": proxy_row.host,
            "port": proxy_row.port,
            "username": proxy_row.username,
            "password": proxy_row.password,
            "protocol": proxy_row.protocol.value if hasattr(proxy_row.protocol, "value") else proxy_row.protocol,
        }
    return dict(
        phone=account.phone,
        api_id=account.api_id,
        api_hash=account.api_hash,
        device_model=account.device_model or "PC 64bit",
        system_version=account.system_version or "Windows 10",
        app_version=account.app_version or "6.5.1 x64",
        lang_code=account.lang_code or "en",
        system_lang_code=account.system_lang_code or "en-US",
        proxy=proxy,
    )


class InboxSyncService:
    """Syncs Telegram dialogs to tg_inbox_dialogs for all active accounts."""

    async def sync_account(self, account_id: int, session: AsyncSession, limit: int = 30):
        """Sync dialogs for one account. Called on connect or periodically."""
        account = await session.get(TgAccount, account_id)
        if not account or account.status != TgAccountStatus.ACTIVE:
            logger.debug(f"Inbox sync: account {account_id} skipped (not found or not active)")
            return 0
        if not account.api_id or not account.api_hash:
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) skipped (missing api_id/api_hash)")
            return 0
        if not telegram_engine.session_file_exists(account.phone):
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) skipped (no session file)")
            return 0

        # Check if already connected — reuse existing client
        already_connected = False
        existing = telegram_engine.get_client(account_id)
        if existing and existing.is_connected():
            already_connected = True
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) already connected, reusing")

        try:
            # Build connect kwargs the same way as the API endpoints
            proxy_row = None
            if account.assigned_proxy_id:
                from app.models.telegram_outreach import TgProxy
                proxy_row = await session.get(TgProxy, account.assigned_proxy_id)

            kwargs = _build_connect_kwargs(account, proxy_row)
            logger.info(f"Inbox sync: connecting account {account_id} ({account.phone}), proxy={'yes' if proxy_row else 'no'}")

            await telegram_engine.connect(account_id, **kwargs)
            client = telegram_engine.get_client(account_id)
            if not client:
                logger.warning(f"Inbox sync: account {account_id} ({account.phone}) — connect returned but no client found")
                return 0
            me = await client.get_me()

            synced = 0
            from telethon.tl.types import User
            async for dialog in client.iter_dialogs(limit=limit):
                try:
                    if not dialog.is_user:
                        continue
                    entity = dialog.entity
                    if isinstance(entity, User) and entity.bot:
                        continue

                    peer_name = f"{getattr(entity, 'first_name', '') or ''} {getattr(entity, 'last_name', '') or ''}".strip() or None
                    peer_username = getattr(entity, "username", None)
                    last_text = dialog.message.text if dialog.message else None
                    last_at = dialog.message.date.replace(tzinfo=None) if dialog.message and dialog.message.date else None
                    last_outbound = dialog.message.out if dialog.message else None

                    # Try to link to campaign via recipient username
                    campaign_id = None
                    if peer_username:
                        recipient_q = await session.execute(
                            select(TgRecipient.campaign_id).where(
                                TgRecipient.username == peer_username,
                                TgRecipient.assigned_account_id == account_id,
                            ).limit(1)
                        )
                        row = recipient_q.first()
                        if row:
                            campaign_id = row[0]

                    # Upsert
                    stmt = pg_insert(TgInboxDialog).values(
                        account_id=account_id,
                        peer_id=dialog.id,
                        peer_name=peer_name,
                        peer_username=peer_username,
                        last_message_text=last_text[:500] if last_text else None,
                        last_message_at=last_at,
                        last_message_outbound=last_outbound,
                        unread_count=dialog.unread_count,
                        campaign_id=campaign_id,
                        synced_at=datetime.utcnow(),
                    ).on_conflict_do_update(
                        index_elements=["account_id", "peer_id"],
                        set_={
                            "peer_name": peer_name,
                            "peer_username": peer_username,
                            "last_message_text": last_text[:500] if last_text else None,
                            "last_message_at": last_at,
                            "last_message_outbound": last_outbound,
                            "unread_count": dialog.unread_count,
                            "campaign_id": campaign_id,
                            "synced_at": datetime.utcnow(),
                        },
                    )
                    await session.execute(stmt)
                    synced += 1
                except Exception as e:
                    logger.debug(f"Inbox sync: skip dialog {dialog.id}: {e}")
                    continue

            await session.commit()
            if not already_connected:
                await telegram_engine.disconnect(account_id)
            logger.info(f"Inbox sync: account {account_id} ({account.phone}) — {synced} dialogs synced")
            return synced
        except Exception as e:
            logger.warning(f"Inbox sync failed for account {account_id}: {e}", exc_info=True)
            try:
                if not already_connected:
                    await telegram_engine.disconnect(account_id)
            except Exception:
                pass
            return 0

    async def sync_all(self):
        """Sync all active accounts. Called periodically by scheduler."""
        from app.db.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgAccount.id).where(
                    TgAccount.status == TgAccountStatus.ACTIVE,
                    TgAccount.api_id.isnot(None),
                )
            )
            account_ids = [r[0] for r in result.all()]

        synced_total = 0
        for aid in account_ids:
            async with async_session_maker() as session:
                count = await self.sync_account(aid, session)
                synced_total += count
            await asyncio.sleep(2)  # stagger between accounts

        if synced_total:
            logger.info(f"Inbox sync complete: {synced_total} dialogs across {len(account_ids)} accounts")
        return synced_total


inbox_sync_service = InboxSyncService()
