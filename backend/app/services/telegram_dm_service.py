"""Telegram DM Inbox Service — multi-account Telethon manager.

Manages N Telegram user accounts via Telethon StringSession.
Accounts are imported from tdata (Telegram Desktop) archives.
"""
import asyncio
import logging
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, InputPeerUser
from telethon.errors import (
    FloodWaitError,
    AuthKeyUnregisteredError,
    SessionRevokedError,
    UserDeactivatedBanError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramDMService:
    """Manages multiple Telegram user account connections for DM inbox."""

    def __init__(self):
        self.api_id = settings.TELEGRAM_CHECKER_API_ID
        self.api_hash = settings.TELEGRAM_CHECKER_API_HASH
        self._clients: dict[int, TelegramClient] = {}  # account_id -> client
        self._lock = asyncio.Lock()

    # ── Account Import ──────────────────────────────────────────────

    async def import_from_tdata(self, archive_path: str) -> list[dict]:
        """Import Telegram accounts from a tdata archive (ZIP or RAR).

        Returns list of dicts with account info + string_session for each account.
        Multi-account tdata (up to 100 accounts) is fully supported.
        """
        tmpdir = tempfile.mkdtemp(prefix="tdata_")
        try:
            # Extract archive (ZIP or RAR)
            if archive_path.lower().endswith(".rar"):
                try:
                    subprocess.run(
                        ["unar", "-o", tmpdir, "-f", archive_path],
                        check=True, capture_output=True, timeout=60,
                    )
                except FileNotFoundError:
                    raise ValueError("unar not installed on server. Install with: apt-get install unar")
                except subprocess.CalledProcessError as e:
                    raise ValueError(f"Failed to extract RAR: {e.stderr.decode()[:200]}")
            else:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(tmpdir)

            # Find tdata folder (might be at root or inside a subfolder)
            tdata_path = Path(tmpdir)
            if (tdata_path / "tdata").is_dir():
                tdata_path = tdata_path / "tdata"
            elif not (tdata_path / "key_datas").exists():
                for child in tdata_path.iterdir():
                    if child.is_dir() and (child / "key_datas").exists():
                        tdata_path = child
                        break
                    if child.is_dir() and (child / "tdata").is_dir():
                        tdata_path = child / "tdata"
                        break

            if not (tdata_path / "key_datas").exists():
                raise ValueError(f"No valid tdata found in archive. Expected key_datas file.")

            # Parse tdata with opentele (patched for multi-account + recursion fix)
            accounts_data = self._parse_tdata_all_accounts(str(tdata_path))

            # Connect each account and get user info
            results = []
            for acc_data in accounts_data:
                try:
                    client = TelegramClient(
                        StringSession(acc_data["string_session"]),
                        self.api_id, self.api_hash,
                    )
                    await client.connect()
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        results.append({
                            "telegram_user_id": me.id,
                            "username": me.username,
                            "first_name": me.first_name,
                            "last_name": me.last_name,
                            "phone": me.phone,
                            "string_session": acc_data["string_session"],
                        })
                        logger.info(f"tdata import: account @{me.username} ({me.phone}) OK")
                    else:
                        logger.warning(f"tdata import: account dc={acc_data['dc_id']} not authorized")
                    await client.disconnect()
                except Exception as e:
                    logger.warning(f"tdata import: account dc={acc_data['dc_id']} failed: {e}")

            if not results:
                raise ValueError("No authorized accounts found in tdata archive.")

            return results
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _parse_tdata_all_accounts(tdata_path: str) -> list[dict]:
        """Parse ALL accounts from tdata using opentele with patches for:
        1. Infinite recursion bug in api setter
        2. kMaxAccounts=3 limit (Kotatogram supports 100)
        """
        import sys
        import struct
        import base64
        import ipaddress

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(10000)
        try:
            import opentele.td.tdesktop as td_mod
            import opentele.td.account as acc_mod

            # Patch 1: break infinite recursion in api property
            _setting = False
            def _safe_td_api_set(self, value):
                nonlocal _setting
                if _setting:
                    return
                _setting = True
                try:
                    for acc in self.accounts:
                        acc._api = value
                finally:
                    _setting = False

            td_mod.TDesktop.api = td_mod.TDesktop.api.setter(_safe_td_api_set)
            acc_mod.Account.api = acc_mod.Account.api.setter(lambda self, v: setattr(self, "_api", v))

            # Patch 2: raise account limit from 3 to 100
            td_mod.TDesktop.kMaxAccounts = 100

            from opentele.td import TDesktop

            td = TDesktop(tdata_path)
            if not td.isLoaded():
                raise ValueError("Failed to load tdata")

            # DC server addresses for Telethon StringSession
            DC_ADDRS = {
                1: "149.154.175.53", 2: "149.154.167.51",
                3: "149.154.175.100", 4: "149.154.167.91",
                5: "91.108.56.130",
            }

            results = []
            for acc in td.accounts:
                dc_id = acc.MainDcId
                auth_key = bytes(acc.authKey.key)
                if len(auth_key) != 256:
                    continue

                # Build Telethon StringSession manually
                ip_bytes = ipaddress.ip_address(DC_ADDRS[dc_id]).packed
                data = struct.pack(">B4sH", dc_id, ip_bytes, 443) + auth_key
                ss = "1" + base64.urlsafe_b64encode(data).decode()

                results.append({"dc_id": dc_id, "string_session": ss})

            return results
        finally:
            sys.setrecursionlimit(old_limit)

    # ── Connection Lifecycle ────────────────────────────────────────

    async def connect_account(self, account_id: int, string_session: str, proxy_config: dict = None) -> bool:
        """Connect a Telegram account from its saved StringSession."""
        async with self._lock:
            if account_id in self._clients:
                old = self._clients[account_id]
                if old.is_connected():
                    return True
                try:
                    await old.disconnect()
                except Exception:
                    pass

            try:
                client = TelegramClient(
                    StringSession(string_session),
                    self.api_id,
                    self.api_hash,
                    proxy=self._parse_proxy(proxy_config),
                )
                await client.connect()

                if not await client.is_user_authorized():
                    logger.warning(f"Account {account_id}: session not authorized")
                    return False

                self._clients[account_id] = client
                me = await client.get_me()

                # Register real-time event handler for incoming DMs
                self._register_event_handler(client, account_id)

                logger.info(f"Telegram DM account {account_id} connected as @{me.username} ({me.first_name})")
                return True

            except (AuthKeyUnregisteredError, SessionRevokedError, UserDeactivatedBanError) as e:
                logger.error(f"Account {account_id} auth failed (permanent): {e}")
                raise
            except Exception as e:
                logger.error(f"Account {account_id} connect failed: {e}")
                return False

    async def disconnect_account(self, account_id: int):
        """Gracefully disconnect one client."""
        async with self._lock:
            client = self._clients.pop(account_id, None)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                logger.info(f"Telegram DM account {account_id} disconnected")

    async def reconnect_all(self):
        """On startup: load all active accounts from DB and connect them."""
        if not self.api_id or not self.api_hash:
            logger.info("Telegram DM service not configured (missing api_id/api_hash)")
            return

        from app.db.database import async_session_maker
        from app.models.telegram_dm import TelegramDMAccount
        from sqlalchemy import select

        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(TelegramDMAccount).where(
                        TelegramDMAccount.auth_status == "active",
                        TelegramDMAccount.string_session.isnot(None),
                    )
                )
                accounts = result.scalars().all()

            connected = 0
            for acc in accounts:
                try:
                    ok = await self.connect_account(acc.id, acc.string_session, acc.proxy_config)
                    if ok:
                        connected += 1
                        # Update DB status
                        async with async_session_maker() as session:
                            from sqlalchemy import update
                            await session.execute(
                                update(TelegramDMAccount)
                                .where(TelegramDMAccount.id == acc.id)
                                .values(is_connected=True, last_connected_at=datetime.utcnow())
                            )
                            await session.commit()
                except Exception as e:
                    logger.warning(f"Failed to reconnect account {acc.id}: {e}")
                    async with async_session_maker() as session:
                        from sqlalchemy import update
                        await session.execute(
                            update(TelegramDMAccount)
                            .where(TelegramDMAccount.id == acc.id)
                            .values(
                                is_connected=False,
                                last_error=str(e),
                                last_error_at=datetime.utcnow(),
                                auth_status="error" if isinstance(e, (AuthKeyUnregisteredError, SessionRevokedError)) else "disconnected",
                            )
                        )
                        await session.commit()

            logger.info(f"Telegram DM service: {connected}/{len(accounts)} accounts reconnected")
        except Exception as e:
            logger.error(f"Telegram DM reconnect_all failed: {e}")

    # ── Dialog & Message Access ─────────────────────────────────────

    async def get_dialogs(self, account_id: int, limit: int = 50) -> list[dict]:
        """List recent DM conversations for an account."""
        client = self._get_client(account_id)
        dialogs = []

        try:
            async for dialog in client.iter_dialogs(limit=limit * 2):
                try:
                    # Only private chats (DMs), skip groups/channels/bots
                    if not dialog.is_user:
                        continue
                    entity = dialog.entity
                    if isinstance(entity, User) and entity.bot:
                        continue

                    dialogs.append({
                        "peer_id": dialog.id,
                        "peer_name": dialog.name or "Unknown",
                        "peer_username": getattr(entity, "username", None),
                        "last_message": dialog.message.text if dialog.message else None,
                        "last_message_at": dialog.message.date.isoformat() if dialog.message and dialog.message.date else None,
                        "unread_count": dialog.unread_count,
                    })
                    if len(dialogs) >= limit:
                        break
                except Exception as e:
                    # Skip dialogs with unresolvable peers (deleted users, etc.)
                    logger.debug(f"Account {account_id}: skipping dialog: {e}")
                    continue
        except FloodWaitError as e:
            logger.warning(f"Account {account_id} FloodWait on dialogs: {e.seconds}s")
            if e.seconds < 60:
                await asyncio.sleep(e.seconds + 1)
                return await self.get_dialogs(account_id, limit)
            raise
        except Exception as e:
            # Catch entity resolution errors at the iterator level
            if "Could not find the input entity" in str(e):
                logger.warning(f"Account {account_id}: entity resolution error, returning {len(dialogs)} dialogs collected so far")
            else:
                raise

        return dialogs

    async def get_messages(self, account_id: int, peer_id: int, limit: int = 50) -> list[dict]:
        """Fetch conversation thread with a specific peer."""
        client = self._get_client(account_id)
        me = await client.get_me()
        messages = []

        try:
            async for msg in client.iter_messages(peer_id, limit=limit):
                if not msg.text:
                    continue
                messages.append({
                    "id": msg.id,
                    "direction": "outbound" if msg.sender_id == me.id else "inbound",
                    "text": msg.text,
                    "sent_at": msg.date.isoformat() if msg.date else None,
                    "sender_name": self._get_sender_name(msg, me),
                })
        except FloodWaitError as e:
            logger.warning(f"Account {account_id} FloodWait on messages: {e.seconds}s")
            if e.seconds < 60:
                await asyncio.sleep(e.seconds + 1)
                return await self.get_messages(account_id, peer_id, limit)
            raise

        # Return in chronological order
        messages.reverse()
        return messages

    async def send_message(self, account_id: int, peer_id: int, text: str) -> dict:
        """Send a Telegram DM."""
        client = self._get_client(account_id)

        try:
            msg = await client.send_message(peer_id, text)
            logger.info(f"Account {account_id}: sent message to {peer_id} (msg_id={msg.id})")
            return {"success": True, "message_id": msg.id}
        except FloodWaitError as e:
            logger.warning(f"Account {account_id} FloodWait on send: {e.seconds}s")
            return {"success": False, "error": f"Rate limited. Wait {e.seconds}s."}
        except Exception as e:
            logger.error(f"Account {account_id} send failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Real-time Event Handlers (persistent connection) ──────────

    def _register_event_handler(self, client: TelegramClient, account_id: int):
        """Register Telethon event handler for real-time DM detection.

        This fires instantly when the account receives a new private message.
        The handler processes the message through the full pipeline (classify → draft → notify).
        Polling still runs as a safety net for missed events.
        """
        @client.on(events.NewMessage(incoming=True))
        async def _on_new_dm(event):
            try:
                # Only private DMs — skip groups, channels, bots
                if not event.is_private:
                    return
                if not event.raw_text:
                    return  # skip media-only

                sender = await event.get_sender()
                if not sender or not isinstance(sender, User):
                    return
                if sender.bot:
                    return

                # Get account info from DB
                from app.db.database import async_session_maker
                from app.models.telegram_dm import TelegramDMAccount
                from sqlalchemy import select

                async with async_session_maker() as session:
                    acc = (await session.execute(
                        select(TelegramDMAccount).where(TelegramDMAccount.id == account_id)
                    )).scalar()

                if not acc or not acc.project_id:
                    return  # Not assigned to a project

                peer_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
                peer_username = sender.username

                logger.info(f"[TELEGRAM] Real-time DM from {peer_name} (@{peer_username}) → account {account_id} (@{acc.username})")

                from app.db.database import async_session_maker
                from app.services.reply_processor import process_telegram_reply, send_telegram_dm_notification

                async with async_session_maker() as session:
                    try:
                        pr = await process_telegram_reply(
                            message_text=event.raw_text,
                            peer_id=sender.id,
                            peer_name=peer_name,
                            peer_username=peer_username,
                            account_id=acc.id,
                            account_username=acc.username,
                            project_id=acc.project_id,
                            message_id=event.id,
                            activity_at=event.date.replace(tzinfo=None) if event.date else None,
                            raw_data={
                                "message_id": event.id,
                                "peer_id": sender.id,
                                "peer_username": peer_username,
                                "account_id": acc.id,
                                "_source": "realtime",
                            },
                            session=session,
                        )
                        if pr:
                            await session.commit()
                            logger.info(f"[TELEGRAM] Real-time: created ProcessedReply {pr.id} for @{peer_username}")

                            # Send notification after commit
                            await send_telegram_dm_notification(
                                processed_reply=pr,
                                peer_name=peer_name,
                                peer_username=peer_username,
                                account_username=acc.username,
                                message_text=event.raw_text,
                                project_id=acc.project_id,
                                session=session,
                            )
                    except Exception as e:
                        if "uq_reply_dedup" in str(e):
                            pass  # Duplicate — polling already caught it
                        else:
                            logger.error(f"[TELEGRAM] Real-time processing failed: {e}")

            except Exception as e:
                logger.error(f"[TELEGRAM] Event handler error for account {account_id}: {e}")

    async def start_listening(self):
        """Start persistent Telethon connections for all connected clients.

        Each client's run_until_disconnected() maintains a TCP socket to Telegram servers.
        The server pushes new message updates in real-time (sub-second delivery).
        Polling still runs as a safety net every 3 min.
        """
        tasks = []
        for account_id, client in self._clients.items():
            if client.is_connected():
                task = asyncio.create_task(
                    self._run_client_listener(account_id, client),
                    name=f"tg_dm_listener_{account_id}",
                )
                tasks.append(task)
        if tasks:
            logger.info(f"[TELEGRAM] Started {len(tasks)} persistent listeners")
        self._listener_tasks = tasks

    async def _run_client_listener(self, account_id: int, client: TelegramClient):
        """Keep one client's persistent connection alive. Auto-reconnects on disconnect."""
        while True:
            try:
                logger.info(f"[TELEGRAM] Listener started for account {account_id}")
                await client.run_until_disconnected()
                logger.warning(f"[TELEGRAM] Listener disconnected for account {account_id}")
            except Exception as e:
                logger.error(f"[TELEGRAM] Listener error for account {account_id}: {e}")
            # Wait before reconnect attempt
            await asyncio.sleep(10)
            if not self._clients.get(account_id):
                break  # Account was removed
            try:
                client = self._clients[account_id]
                if not client.is_connected():
                    await client.connect()
                    logger.info(f"[TELEGRAM] Listener reconnected for account {account_id}")
            except Exception as e:
                logger.error(f"[TELEGRAM] Reconnect failed for account {account_id}: {e}")
                await asyncio.sleep(30)

    # ── Polling for New Messages (safety net) ───────────────────

    async def poll_all_accounts(self):
        """Poll all active accounts for new inbound DMs. Called by scheduler every 3 min."""
        from app.db.database import async_session_maker
        from app.models.telegram_dm import TelegramDMAccount
        from sqlalchemy import select, update

        async with async_session_maker() as session:
            result = await session.execute(
                select(TelegramDMAccount).where(
                    TelegramDMAccount.auth_status == "active",
                    TelegramDMAccount.project_id.isnot(None),
                    TelegramDMAccount.is_connected == True,
                )
            )
            accounts = result.scalars().all()

        if not accounts:
            return

        total_new = 0
        for acc in accounts:
            if not self.is_connected(acc.id):
                continue
            try:
                count = await self._poll_account(acc)
                total_new += count
            except FloodWaitError as e:
                logger.warning(f"[TELEGRAM] Account {acc.id} FloodWait during poll: {e.seconds}s — skipping")
            except Exception as e:
                logger.warning(f"[TELEGRAM] Poll failed for account {acc.id}: {e}")

            # Stagger between accounts to avoid rate limits
            await asyncio.sleep(2)

        if total_new:
            logger.info(f"[TELEGRAM] Poll cycle complete: {total_new} new replies from {len(accounts)} accounts")

    async def _poll_account(self, acc) -> int:
        """Poll one account for new inbound DMs. Returns count of new replies processed."""
        from app.db.database import async_session_maker
        from app.models.telegram_dm import TelegramDMAccount
        from app.services.reply_processor import process_telegram_reply, send_telegram_dm_notification
        from sqlalchemy import update

        client = self._get_client(acc.id)
        me = await client.get_me()
        new_count = 0

        # Fetch dialogs with unread messages
        async for dialog in client.iter_dialogs(limit=100):
            try:
                if not dialog.is_user or not dialog.unread_count:
                    continue
                entity = dialog.entity
                if isinstance(entity, User) and entity.bot:
                    continue

                # Fetch recent messages (up to unread count, max 20)
                fetch_limit = min(dialog.unread_count, 20)
                async for msg in client.iter_messages(dialog.id, limit=fetch_limit):
                    if msg.sender_id == me.id:
                        continue  # Skip our own outbound
                    if not msg.text:
                        continue  # Skip media-only
                    if acc.last_processed_at and msg.date and msg.date.replace(tzinfo=None) <= acc.last_processed_at:
                        break  # Already processed

                    # Process this message
                    peer_name = f"{getattr(entity, 'first_name', '') or ''} {getattr(entity, 'last_name', '') or ''}".strip() or "Unknown"
                    peer_username = getattr(entity, "username", None)

                    async with async_session_maker() as session:
                        try:
                            pr = await process_telegram_reply(
                                message_text=msg.text,
                                peer_id=dialog.id,
                                peer_name=peer_name,
                                peer_username=peer_username,
                                account_id=acc.id,
                                account_username=acc.username,
                                project_id=acc.project_id,
                                message_id=msg.id,
                                activity_at=msg.date.replace(tzinfo=None) if msg.date else None,
                                raw_data={
                                    "message_id": msg.id,
                                    "peer_id": dialog.id,
                                    "peer_username": peer_username,
                                    "account_id": acc.id,
                                },
                                session=session,
                            )
                            if pr:
                                await session.commit()
                                new_count += 1

                                # Send notification after commit
                                await send_telegram_dm_notification(
                                    processed_reply=pr,
                                    peer_name=peer_name,
                                    peer_username=peer_username,
                                    account_username=acc.username,
                                    message_text=msg.text,
                                    project_id=acc.project_id,
                                    session=session,
                                )
                        except Exception as e:
                            if "uq_reply_dedup" in str(e):
                                pass  # Duplicate — expected
                            else:
                                logger.warning(f"[TELEGRAM] Failed to process msg {msg.id} from {dialog.id}: {e}")
            except Exception as dialog_err:
                logger.debug(f"[TELEGRAM] Skipping dialog {dialog.id}: {dialog_err}")
                continue

        # Update polling cursor
        async with async_session_maker() as session:
            await session.execute(
                update(TelegramDMAccount)
                .where(TelegramDMAccount.id == acc.id)
                .values(last_processed_at=datetime.utcnow())
            )
            await session.commit()

        return new_count

    # ── Helpers ─────────────────────────────────────────────────────

    def _get_client(self, account_id: int) -> TelegramClient:
        client = self._clients.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} is not connected")
        if not client.is_connected():
            raise ValueError(f"Account {account_id} lost connection")
        return client

    def is_connected(self, account_id: int) -> bool:
        client = self._clients.get(account_id)
        return client is not None and client.is_connected()

    @staticmethod
    def _parse_proxy(proxy_config: dict = None):
        if not proxy_config:
            return None
        return (
            proxy_config.get("type", "socks5"),
            proxy_config.get("host"),
            proxy_config.get("port"),
            True,  # rdns
            proxy_config.get("username"),
            proxy_config.get("password"),
        )

    @staticmethod
    def _get_sender_name(msg, me) -> str:
        if msg.sender_id == me.id:
            return f"{me.first_name or ''} {me.last_name or ''}".strip() or "Me"
        sender = msg.sender
        if sender and isinstance(sender, User):
            return f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        return "Unknown"


# Singleton
telegram_dm_service = TelegramDMService()
