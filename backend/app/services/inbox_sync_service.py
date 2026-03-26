"""Inbox sync service — scans all active Telegram DM accounts for dialogs.

Uses telegram_dm_accounts (TelegramDMAccount) with StringSession stored in DB,
instead of tg_accounts with .session files on disk.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_outreach import (
    TgInboxDialog, TgRecipient,
)
from app.models.telegram_dm import TelegramDMAccount
from app.services.telegram_dm_service import telegram_dm_service

logger = logging.getLogger(__name__)


class InboxSyncService:
    """Syncs Telegram dialogs to tg_inbox_dialogs for all active DM accounts."""

    async def sync_account(self, account_id: int, session: AsyncSession, limit: int = 30):
        """Sync dialogs for one telegram_dm_account. Called on connect or periodically."""
        account = await session.get(TelegramDMAccount, account_id)
        if not account:
            logger.debug(f"Inbox sync: account {account_id} not found in telegram_dm_accounts")
            return 0
        if not account.string_session:
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) has no string_session")
            return 0
        if account.auth_status != "active":
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) auth_status={account.auth_status}, skipping")
            return 0

        # Check if already connected — avoid disconnect at the end if so
        already_connected = telegram_dm_service.is_connected(account_id)

        try:
            # Connect via telegram_dm_service
            if not already_connected:
                logger.info(f"Inbox sync: connecting account {account_id} ({account.phone})")
                ok = await telegram_dm_service.connect_account(account_id, account.string_session, account.proxy_config)
                if not ok:
                    logger.warning(f"Inbox sync: account {account_id} ({account.phone}) — connect failed")
                    return 0
            else:
                logger.debug(f"Inbox sync: account {account_id} ({account.phone}) already connected, reusing")

            # Get dialogs via telegram_dm_service
            dialogs_data = await telegram_dm_service.get_dialogs(account_id, limit=limit)

            synced = 0
            for d in dialogs_data:
                try:
                    peer_id = d["peer_id"]
                    peer_name = d.get("peer_name")
                    peer_username = d.get("peer_username")
                    last_text = d.get("last_message")
                    last_at_str = d.get("last_message_at")
                    unread_count = d.get("unread_count", 0)

                    # Parse last_message_at from ISO string
                    last_at = None
                    if last_at_str:
                        try:
                            last_at = datetime.fromisoformat(last_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        except (ValueError, AttributeError):
                            pass

                    # last_message_outbound is not available from get_dialogs — set None
                    last_outbound = None

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

                    # Upsert into tg_inbox_dialogs
                    stmt = pg_insert(TgInboxDialog).values(
                        account_id=account_id,
                        peer_id=peer_id,
                        peer_name=peer_name,
                        peer_username=peer_username,
                        last_message_text=last_text[:500] if last_text else None,
                        last_message_at=last_at,
                        last_message_outbound=last_outbound,
                        unread_count=unread_count,
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
                            "unread_count": unread_count,
                            "campaign_id": campaign_id,
                            "synced_at": datetime.utcnow(),
                        },
                    )
                    await session.execute(stmt)
                    synced += 1
                except Exception as e:
                    logger.debug(f"Inbox sync: skip dialog peer_id={d.get('peer_id')}: {e}")
                    continue

            await session.commit()

            # Only disconnect if we connected it ourselves
            if not already_connected:
                await telegram_dm_service.disconnect_account(account_id)

            logger.info(f"Inbox sync: account {account_id} ({account.phone}) — {synced} dialogs synced")
            return synced
        except Exception as e:
            logger.warning(f"Inbox sync failed for account {account_id}: {e}", exc_info=True)
            try:
                if not already_connected:
                    await telegram_dm_service.disconnect_account(account_id)
            except Exception:
                pass
            return 0

    async def sync_all(self):
        """Sync all active telegram_dm_accounts with string_session. Called periodically by scheduler."""
        from app.db.database import async_session_maker

        async with async_session_maker() as session:
            result = await session.execute(
                select(TelegramDMAccount.id).where(
                    TelegramDMAccount.string_session.isnot(None),
                    TelegramDMAccount.auth_status == "active",
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
