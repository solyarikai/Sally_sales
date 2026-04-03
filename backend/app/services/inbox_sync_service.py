"""Inbox sync service — scans all active Telegram DM accounts for dialogs.

Uses telegram_dm_accounts (TelegramDMAccount) with StringSession stored in DB,
instead of tg_accounts with .session files on disk.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_outreach import (
    TgInboxDialog, TgRecipient, TgAccount, TgOutreachMessage, TgProxy,
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
        if account.auth_status == "error":
            logger.debug(f"Inbox sync: account {account_id} ({account.phone}) auth_status=error, skipping")
            return 0

        # Resolve DM account ID → TG outreach account ID via phone.
        # TgInboxDialog.account_id FK references tg_accounts.id, not telegram_dm_accounts.id.
        tg_account_id = None
        if account.phone:
            tg_result = await session.execute(
                select(TgAccount.id).where(TgAccount.phone == account.phone).limit(1)
            )
            row = tg_result.first()
            if row:
                tg_account_id = row[0]
        if not tg_account_id:
            if not account.phone:
                logger.warning(f"Inbox sync: account {account_id} has no phone — cannot sync")
                return 0
            # Auto-create TgAccount so TgInboxDialog FK is satisfied
            new_tg = TgAccount(
                phone=account.phone,
                username=account.username,
                first_name=account.first_name,
                last_name=getattr(account, "last_name", None),
                string_session=account.string_session,
            )
            session.add(new_tg)
            await session.flush()
            tg_account_id = new_tg.id
            logger.info(f"Inbox sync: auto-created TgAccount {tg_account_id} for phone {account.phone}")

        # Resolve proxy: prefer dm_account.proxy_config, fallback to TgAccount.assigned_proxy
        proxy_cfg = account.proxy_config
        if not proxy_cfg and account.phone:
            proxy_result = await session.execute(
                select(TgProxy).join(TgAccount, TgAccount.assigned_proxy_id == TgProxy.id)
                .where(TgAccount.phone == account.phone, TgProxy.is_active.is_(True)).limit(1)
            )
            proxy = proxy_result.scalar_one_or_none()
            if proxy:
                proxy_cfg = {
                    "type": proxy.protocol.value if proxy.protocol else "socks5",
                    "host": proxy.host, "port": proxy.port,
                    "username": proxy.username, "password": proxy.password,
                }
                logger.info(f"Inbox sync: proxy fallback for {account.phone} ← {proxy.host}:{proxy.port}")

        # Check if already connected — avoid disconnect at the end if so
        already_connected = telegram_dm_service.is_connected(account_id)

        try:
            # Connect via telegram_dm_service
            if not already_connected:
                logger.info(f"Inbox sync: connecting account {account_id} ({account.phone})")
                ok = await telegram_dm_service.connect_account(account_id, account.string_session, proxy_cfg)
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

                    last_outbound = d.get("last_message_outbound")

                    # Try to link to campaign via recipient username
                    campaign_id = None
                    if peer_username:
                        # Primary: match by username + assigned account (most accurate)
                        recipient_q = await session.execute(
                            select(TgRecipient.campaign_id).where(
                                TgRecipient.username == peer_username,
                                TgRecipient.assigned_account_id == tg_account_id,
                            ).order_by(TgRecipient.id.desc()).limit(1)
                        )
                        row = recipient_q.first()
                        if row:
                            campaign_id = row[0]
                        else:
                            # Fallback: match by username only
                            recipient_q = await session.execute(
                                select(TgRecipient.campaign_id).where(
                                    TgRecipient.username == peer_username,
                                ).order_by(TgRecipient.id.desc()).limit(1)
                            )
                            row = recipient_q.first()
                            if row:
                                campaign_id = row[0]

                    # Fallback: check sent messages from this account to this peer
                    if campaign_id is None and peer_username:
                        msg_q = await session.execute(
                            select(TgOutreachMessage.campaign_id)
                            .join(TgRecipient, TgOutreachMessage.recipient_id == TgRecipient.id)
                            .where(
                                TgOutreachMessage.account_id == tg_account_id,
                                TgRecipient.username == peer_username,
                            )
                            .order_by(TgOutreachMessage.sent_at.desc())
                            .limit(1)
                        )
                        row = msg_q.first()
                        if row:
                            campaign_id = row[0]

                    # Upsert into tg_inbox_dialogs (use TG outreach account ID for FK)
                    stmt = pg_insert(TgInboxDialog).values(
                        account_id=tg_account_id,
                        peer_id=peer_id,
                        peer_name=peer_name,
                        peer_username=peer_username,
                        last_message_text=last_text[:500] if last_text else None,
                        last_message_at=last_at,
                        last_message_outbound=last_outbound,
                        unread_count=unread_count,
                        campaign_id=campaign_id,
                        synced_at=datetime.utcnow(),
                    )
                    # COALESCE: never overwrite existing campaign_id with NULL
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["account_id", "peer_id"],
                        set_={
                            "peer_name": peer_name,
                            "peer_username": peer_username,
                            "last_message_text": last_text[:500] if last_text else None,
                            "last_message_at": last_at,
                            "last_message_outbound": last_outbound,
                            "unread_count": unread_count,
                            "campaign_id": func.coalesce(
                                stmt.excluded.campaign_id,
                                TgInboxDialog.__table__.c.campaign_id,
                            ),
                            "synced_at": datetime.utcnow(),
                        },
                    )
                    await session.execute(stmt)
                    synced += 1
                except Exception as e:
                    logger.warning(f"Inbox sync: skip dialog peer_id={d.get('peer_id')}: {e}")
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
                    TelegramDMAccount.auth_status != "error",
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
