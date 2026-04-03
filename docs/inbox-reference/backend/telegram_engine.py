"""
Telegram Engine — manages Telethon clients for outreach accounts.

Handles: connection, auth, session storage, health checks, profile updates.
"""
import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from telethon import TelegramClient, errors, functions, types
from telethon.sessions import SQLiteSession, StringSession

logger = logging.getLogger(__name__)

# Session files stored inside the backend container
SESSIONS_DIR = Path(os.environ.get("TG_SESSIONS_DIR", "/app/tg_sessions"))
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def session_file_to_string_session(
    session_bytes: bytes, api_id: int, api_hash: str
) -> tuple[str, Optional[dict]]:
    """Convert a .session file (bytes) to a Telethon StringSession string.

    Returns (string_session, user_info) where user_info is a dict with
    telegram_user_id, username, first_name, last_name — or None if
    the client can't connect / isn't authorized.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".session", delete=False)
    tmp.write(session_bytes)
    tmp.close()

    # Telethon auto-appends .session, so the session name must NOT include it
    session_path = tmp.name.replace(".session", "")
    os.rename(tmp.name, session_path + ".session")

    user_info = None
    try:
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()

        # Export as StringSession
        string_session = StringSession.save(client.session)

        # Try to grab user info if the session is authorized
        try:
            if await client.is_user_authorized():
                me = await client.get_me()
                if me:
                    user_info = {
                        "telegram_user_id": me.id,
                        "username": me.username,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                    }
        except Exception as e:
            logger.warning(f"Could not get_me() during StringSession extraction: {e}")

        await client.disconnect()
        return string_session, user_info
    except Exception as e:
        logger.error(f"Failed to extract StringSession: {e}")
        raise
    finally:
        try:
            os.unlink(session_path + ".session")
        except OSError:
            pass


class PendingAuth:
    """Holds state for an in-progress phone auth."""
    __slots__ = ("phone_hash", "client", "phone", "needs_2fa")

    def __init__(self, client: TelegramClient, phone: str, phone_hash: str):
        self.client = client
        self.phone = phone
        self.phone_hash = phone_hash
        self.needs_2fa = False


class TelegramEngine:
    """Singleton engine managing Telethon client pool."""

    def __init__(self):
        self._clients: dict[int, TelegramClient] = {}      # account_id -> connected client
        self._pending_auths: dict[int, PendingAuth] = {}    # account_id -> auth state
        self._lock = asyncio.Lock()

    # ── Session path helpers ──────────────────────────────────────────

    def session_path(self, phone: str) -> Path:
        """Return path for a .session file (without extension — Telethon adds it)."""
        return SESSIONS_DIR / phone

    def session_file_exists(self, phone: str) -> bool:
        return (SESSIONS_DIR / f"{phone}.session").exists()

    async def save_uploaded_session(self, phone: str, content: bytes) -> Path:
        """Save an uploaded .session file."""
        path = SESSIONS_DIR / f"{phone}.session"
        path.write_bytes(content)
        logger.info(f"Session saved for {phone}: {path}")
        return path

    # ── Client creation ───────────────────────────────────────────────

    def _make_client(
        self,
        phone: str,
        api_id: int,
        api_hash: str,
        device_model: str = "PC 64bit",
        system_version: str = "Windows 10",
        app_version: str = "6.5.1 x64",
        lang_code: str = "en",
        system_lang_code: str = "en-US",
        proxy: Optional[dict] = None,
    ) -> TelegramClient:
        session = str(self.session_path(phone))
        proxy_tuple = None
        if proxy:
            import socks
            proto_map = {"http": socks.HTTP, "socks5": socks.SOCKS5}
            proxy_tuple = (
                proto_map.get(proxy.get("protocol", "http"), socks.HTTP),
                proxy["host"],
                proxy["port"],
                True,  # rdns
                proxy.get("username"),
                proxy.get("password"),
            )

        client = TelegramClient(
            session,
            api_id,
            api_hash,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            proxy=proxy_tuple,
            timeout=30,
            connection_retries=2,
        )
        return client

    # ── Connect / disconnect ──────────────────────────────────────────

    async def connect(
        self,
        account_id: int,
        phone: str,
        api_id: int,
        api_hash: str,
        device_model: str = "PC 64bit",
        system_version: str = "Windows 10",
        app_version: str = "6.5.1 x64",
        lang_code: str = "en",
        system_lang_code: str = "en-US",
        proxy: Optional[dict] = None,
    ) -> TelegramClient:
        """Connect (or reuse) a Telethon client for the given account."""
        async with self._lock:
            existing = self._clients.get(account_id)
            if existing and existing.is_connected():
                return existing

        client = self._make_client(
            phone, api_id, api_hash,
            device_model, system_version, app_version,
            lang_code, system_lang_code, proxy,
        )
        await client.connect()
        async with self._lock:
            self._clients[account_id] = client
        return client

    async def disconnect(self, account_id: int):
        async with self._lock:
            client = self._clients.pop(account_id, None)
        if client:
            await client.disconnect()

    async def disconnect_all(self):
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for c in clients:
            try:
                await c.disconnect()
            except Exception:
                pass

    def get_client(self, account_id: int) -> Optional[TelegramClient]:
        return self._clients.get(account_id)

    # ── Auth flow ─────────────────────────────────────────────────────

    async def send_code(
        self, account_id: int, phone: str,
        api_id: int, api_hash: str, **kwargs
    ) -> dict:
        """Step 1: Send auth code. Returns {status, phone_hash}."""
        client = await self.connect(account_id, phone, api_id, api_hash, **kwargs)

        if await client.is_user_authorized():
            return {"status": "already_authorized"}

        result = await client.send_code_request(phone)
        self._pending_auths[account_id] = PendingAuth(client, phone, result.phone_code_hash)
        return {"status": "code_sent", "phone_hash": result.phone_code_hash}

    async def verify_code(self, account_id: int, code: str) -> dict:
        """Step 2: Verify SMS/Telegram code. Returns {status} — may need 2FA."""
        pending = self._pending_auths.get(account_id)
        if not pending:
            return {"status": "error", "detail": "No pending auth. Call send_code first."}

        try:
            await pending.client.sign_in(
                pending.phone, code, phone_code_hash=pending.phone_hash,
            )
            self._pending_auths.pop(account_id, None)
            return {"status": "authorized"}
        except errors.SessionPasswordNeededError:
            pending.needs_2fa = True
            return {"status": "2fa_required"}
        except errors.PhoneCodeInvalidError:
            return {"status": "error", "detail": "Invalid code"}
        except errors.PhoneCodeExpiredError:
            self._pending_auths.pop(account_id, None)
            return {"status": "error", "detail": "Code expired. Request a new one."}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def verify_2fa(self, account_id: int, password: str) -> dict:
        """Step 3: Verify 2FA password."""
        pending = self._pending_auths.get(account_id)
        if not pending:
            return {"status": "error", "detail": "No pending auth."}

        try:
            await pending.client.sign_in(password=password)
            self._pending_auths.pop(account_id, None)
            return {"status": "authorized"}
        except errors.PasswordHashInvalidError:
            return {"status": "error", "detail": "Wrong 2FA password"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    # ── Health check ──────────────────────────────────────────────────

    async def check_account(
        self, account_id: int, phone: str,
        api_id: int, api_hash: str, **kwargs
    ) -> dict:
        """Connect, check auth, check spamblock via @SpamBot. Returns status dict."""
        result = {
            "connected": False,
            "authorized": False,
            "spamblock": "unknown",
            "spamblock_end": None,
            "username": None,
            "first_name": None,
            "last_name": None,
            "phone": phone,
        }

        try:
            client = await self.connect(account_id, phone, api_id, api_hash, **kwargs)
            result["connected"] = True

            if not await client.is_user_authorized():
                result["authorized"] = False
                return result

            result["authorized"] = True

            # Get self info
            me = await client.get_me()
            if me:
                result["username"] = me.username
                result["first_name"] = me.first_name
                result["last_name"] = me.last_name

                # Download avatar
                try:
                    avatar_path = SESSIONS_DIR.parent / "tg_photos" / f"{phone}.jpg"
                    avatar_path.parent.mkdir(parents=True, exist_ok=True)
                    downloaded = await client.download_profile_photo(me, file=str(avatar_path))
                    if downloaded:
                        result["avatar_path"] = str(avatar_path)
                except Exception:
                    pass  # avatar download is best-effort

            # Check SpamBot
            try:
                spambot = await client.get_entity("@SpamBot")
                await client.send_message(spambot, "/start")
                await asyncio.sleep(2)

                messages = await client.get_messages(spambot, limit=1)
                if messages:
                    text = messages[0].text or ""
                    text_lower = text.lower()
                    if "no limits" in text_lower or "free" in text_lower or "not limited" in text_lower:
                        result["spamblock"] = "none"
                    elif "temporary" in text_lower or "will be removed" in text_lower:
                        result["spamblock"] = "temporary"
                    elif "permanent" in text_lower:
                        result["spamblock"] = "permanent"
                    else:
                        result["spamblock"] = "none"

                # Clean up dialog
                try:
                    await client.delete_dialog(spambot)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"SpamBot check failed for {phone}: {e}")
                result["spamblock"] = "unknown"

        except errors.AuthKeyUnregisteredError:
            result["connected"] = True
            result["authorized"] = False
        except Exception as e:
            logger.error(f"Check failed for {phone}: {e}")
            result["error"] = str(e)

        return result

    # ── Profile update ────────────────────────────────────────────────

    async def update_profile(
        self, account_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        about: Optional[str] = None,
        username: Optional[str] = None,
    ) -> dict:
        """Update profile fields on the connected account."""
        client = self.get_client(account_id)
        if not client or not client.is_connected():
            return {"status": "error", "detail": "Account not connected"}

        result = {}

        # Update name / bio
        if first_name is not None or last_name is not None or about is not None:
            kwargs = {}
            if first_name is not None:
                kwargs["first_name"] = first_name
            if last_name is not None:
                kwargs["last_name"] = last_name
            if about is not None:
                kwargs["about"] = about
            await client(functions.account.UpdateProfileRequest(**kwargs))
            result["profile_updated"] = True

        # Update username
        if username is not None:
            try:
                await client(functions.account.UpdateUsernameRequest(username=username))
                result["username_updated"] = True
            except errors.UsernameOccupiedError:
                result["username_error"] = "Username already taken"
            except errors.UsernameInvalidError:
                result["username_error"] = "Invalid username"

        return {"status": "ok", **result}

    # ── Send message ──────────────────────────────────────────────────

    async def send_message(
        self, account_id: int, recipient_username: str, text: str,
        link_preview: bool = False, silent: bool = False,
        delete_dialog_after: bool = False,
    ) -> dict:
        """Send a message to a user. Returns {status, message_id} or error."""
        client = self.get_client(account_id)
        if not client or not client.is_connected():
            return {"status": "error", "detail": "Account not connected"}

        try:
            entity = await client.get_entity(recipient_username)
            msg = await client.send_message(
                entity, text,
                link_preview=link_preview,
                silent=silent,
            )
            if delete_dialog_after:
                try:
                    await client.delete_dialog(entity)
                except Exception:
                    pass
            return {"status": "sent", "message_id": msg.id}
        except errors.UserPrivacyRestrictedError:
            return {"status": "failed", "detail": "Privacy restricted"}
        except errors.PeerFloodError:
            return {"status": "spamblocked", "detail": "PeerFloodError (spamblock)"}
        except errors.FloodWaitError as e:
            return {"status": "flood", "detail": f"Flood wait {e.seconds}s", "wait_seconds": e.seconds}
        except errors.UserNotMutualContactError:
            return {"status": "failed", "detail": "Not mutual contact"}
        except errors.ChatWriteForbiddenError:
            return {"status": "failed", "detail": "Write forbidden"}
        except errors.InputUserDeactivatedError:
            return {"status": "bounced", "detail": "User deactivated"}
        except ValueError:
            return {"status": "bounced", "detail": f"Cannot find user {recipient_username}"}
        except Exception as e:
            return {"status": "failed", "detail": str(e)}


# Singleton
telegram_engine = TelegramEngine()
