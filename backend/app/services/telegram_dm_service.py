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

from telethon import TelegramClient
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

    async def import_from_tdata(self, archive_path: str) -> dict:
        """Import a Telegram account from a tdata archive (ZIP or RAR).

        Returns dict with account info (telegram_user_id, username, first_name, etc.)
        and the string_session for DB storage.
        """
        tmpdir = tempfile.mkdtemp(prefix="tdata_")
        try:
            # Extract archive (ZIP or RAR)
            if archive_path.lower().endswith(".rar"):
                try:
                    subprocess.run(
                        ["unrar", "x", "-o+", archive_path, tmpdir + "/"],
                        check=True, capture_output=True, timeout=60,
                    )
                except FileNotFoundError:
                    raise ValueError("unrar not installed on server. Install with: apt-get install unrar")
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
                # Search one level deep
                for child in tdata_path.iterdir():
                    if child.is_dir() and (child / "key_datas").exists():
                        tdata_path = child
                        break
                    if child.is_dir() and (child / "tdata").is_dir():
                        tdata_path = child / "tdata"
                        break

            if not (tdata_path / "key_datas").exists():
                raise ValueError(f"No valid tdata found in archive. Expected key_datas file in {tdata_path}")

            # Convert tdata → StringSession
            from TGConvertor.manager.manager import SessionManager
            session = SessionManager.from_tdata_folder(tdata_path)
            string_session = session.to_telethon_string()

            # Connect and get account info
            client = TelegramClient(StringSession(string_session), self.api_id, self.api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                raise ValueError("tdata session is not authorized. The account may have been logged out.")

            me = await client.get_me()
            await client.disconnect()

            return {
                "telegram_user_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "phone": me.phone,
                "string_session": string_session,
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

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
                                .values(is_connected=True, last_connected_at=datetime.now(timezone.utc))
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
                                last_error_at=datetime.now(timezone.utc),
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
            async for dialog in client.iter_dialogs(limit=limit):
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
        except FloodWaitError as e:
            logger.warning(f"Account {account_id} FloodWait on dialogs: {e.seconds}s")
            if e.seconds < 60:
                await asyncio.sleep(e.seconds + 1)
                return await self.get_dialogs(account_id, limit)
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
