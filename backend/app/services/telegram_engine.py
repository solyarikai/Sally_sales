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


def _estimate_creation_date(user_id: int) -> Optional[str]:
    """Estimate Telegram account creation date from user ID.
    IDs are roughly sequential — interpolate between known reference points."""
    from datetime import datetime
    # Known reference points: (user_id, unix_timestamp)
    refs = [
        (1000000, 1380326400),      # Oct 2013
        (10000000, 1413590400),     # Oct 2014
        (50000000, 1432512000),     # May 2015
        (100000000, 1447286400),    # Nov 2015
        (200000000, 1474243200),    # Sep 2016
        (300000000, 1490918400),    # Mar 2017
        (400000000, 1508198400),    # Oct 2017
        (500000000, 1524268800),    # Apr 2018
        (600000000, 1543622400),    # Dec 2018
        (700000000, 1560988800),    # Jun 2019
        (800000000, 1571011200),    # Oct 2019
        (900000000, 1580515200),    # Feb 2020
        (1000000000, 1585699200),   # Apr 2020
        (1200000000, 1596240000),   # Aug 2020
        (1500000000, 1612137600),   # Feb 2021
        (2000000000, 1631664000),   # Sep 2021
        (3000000000, 1656633600),   # Jul 2022
        (4000000000, 1677628800),   # Mar 2023
        (5000000000, 1696118400),   # Oct 2023
        (6000000000, 1714521600),   # May 2024
        (7000000000, 1735689600),   # Jan 2025
        (8000000000, 1751328000),   # Jul 2025
    ]
    if user_id <= refs[0][0]:
        return datetime.utcfromtimestamp(refs[0][1]).isoformat()
    if user_id >= refs[-1][0]:
        return datetime.utcfromtimestamp(refs[-1][1]).isoformat()
    for i in range(len(refs) - 1):
        if refs[i][0] <= user_id <= refs[i + 1][0]:
            ratio = (user_id - refs[i][0]) / (refs[i + 1][0] - refs[i][0])
            ts = refs[i][1] + ratio * (refs[i + 1][1] - refs[i][1])
            return datetime.utcfromtimestamp(ts).isoformat()
    return None


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
        self._client_proxy: dict[int, str] = {}             # account_id -> proxy key (for cache invalidation)
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

    @staticmethod
    def _proxy_to_tuple(proxy: Optional[dict]):
        """Convert proxy dict to Telethon-compatible tuple. Returns None if no proxy."""
        if not proxy:
            return None
        import socks
        proto_map = {"http": socks.HTTP, "socks5": socks.SOCKS5}
        protocol = proxy.get("protocol", "http")
        if protocol not in proto_map:
            logger.warning(f"Unsupported proxy protocol '{protocol}', falling back to HTTP")
        return (
            proto_map.get(protocol, socks.HTTP),
            proxy["host"],
            proxy["port"],
            True,  # rdns
            proxy.get("username"),
            proxy.get("password"),
        )

    @staticmethod
    def _proxy_key(proxy: Optional[dict]) -> str:
        """Return a stable string key for a proxy config (for cache comparison)."""
        if not proxy:
            return "direct"
        return f"{proxy.get('protocol','http')}://{proxy.get('username','')}@{proxy['host']}:{proxy['port']}"

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
        proxy_tuple = self._proxy_to_tuple(proxy)

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
        new_proxy_key = self._proxy_key(proxy)

        async with self._lock:
            existing = self._clients.get(account_id)
            if existing and existing.is_connected():
                # Invalidate cache if proxy changed
                old_proxy_key = self._client_proxy.get(account_id, "direct")
                if old_proxy_key == new_proxy_key:
                    return existing
                logger.warning(
                    f"[PROXY] Account {phone} (id={account_id}): proxy changed "
                    f"{old_proxy_key} -> {new_proxy_key}, reconnecting"
                )
                try:
                    await existing.disconnect()
                except Exception:
                    pass
                self._clients.pop(account_id, None)
                self._client_proxy.pop(account_id, None)

        if proxy:
            logger.info(f"[PROXY] Account {phone} (id={account_id}): connecting via {new_proxy_key}")
        else:
            logger.warning(f"[PROXY] Account {phone} (id={account_id}): connecting DIRECT (no proxy assigned)")

        client = self._make_client(
            phone, api_id, api_hash,
            device_model, system_version, app_version,
            lang_code, system_lang_code, proxy,
        )
        await client.connect()
        async with self._lock:
            self._clients[account_id] = client
            self._client_proxy[account_id] = new_proxy_key
        return client

    async def disconnect(self, account_id: int):
        async with self._lock:
            client = self._clients.pop(account_id, None)
            self._client_proxy.pop(account_id, None)
        if client:
            await client.disconnect()

    async def disconnect_all(self):
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
            self._client_proxy.clear()
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
        """Connect, check auth, check spamblock via @SpamBot, detect permanent ban. Returns status dict."""
        result = {
            "connected": False,
            "authorized": False,
            "spamblock": "unknown",
            "spamblock_end": None,
            "frozen": False,
            "banned": False,
            "ban_reason": None,
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
                result["telegram_user_id"] = me.id

                # Estimate account creation date from user ID
                # Telegram IDs are roughly sequential — known reference points
                result["telegram_created_at"] = _estimate_creation_date(me.id)

                # Download avatar
                try:
                    avatar_path = SESSIONS_DIR.parent / "tg_photos" / f"{phone}.jpg"
                    avatar_path.parent.mkdir(parents=True, exist_ok=True)
                    downloaded = await client.download_profile_photo(me, file=str(avatar_path))
                    if downloaded:
                        result["avatar_path"] = str(avatar_path)
                except Exception:
                    pass  # avatar download is best-effort

            # ── Check for Abuse Notifications (permanent ban) ─────────
            try:
                abuse_entity = None
                try:
                    abuse_entity = await client.get_entity("Abuse Notifications")
                except Exception:
                    pass
                if abuse_entity:
                    msgs = await client.get_messages(abuse_entity, limit=3)
                    if msgs:
                        result["banned"] = True
                        result["ban_reason"] = "abuse_notifications"
                        logger.warning(f"Account {phone} has Abuse Notifications — permanent ban detected")
            except Exception as e:
                logger.debug(f"Abuse Notifications check skipped for {phone}: {e}")

            # ── Self-message test (catch silent bans) ─────────────────
            if not result["banned"]:
                try:
                    await client.send_message("me", ".")
                    # Clean up test message
                    msgs = await client.get_messages("me", limit=1)
                    if msgs and msgs[0].text == ".":
                        await msgs[0].delete()
                except errors.UserDeactivatedBanError:
                    result["banned"] = True
                    result["ban_reason"] = "user_deactivated"
                    logger.warning(f"Account {phone} banned — UserDeactivatedBanError on self-message")
                except (errors.AuthKeyUnregisteredError, errors.UserDeactivatedError):
                    result["banned"] = True
                    result["ban_reason"] = "send_failed"
                    logger.warning(f"Account {phone} banned — cannot send self-message")
                except errors.FloodWaitError:
                    pass  # flood wait is not a ban
                except Exception as e:
                    err_str = str(e).lower()
                    if "deactivated" in err_str or "banned" in err_str:
                        result["banned"] = True
                        result["ban_reason"] = "send_failed"
                        logger.warning(f"Account {phone} likely banned — self-message error: {e}")

            # ── Check SpamBot ─────────────────────────────────────────
            if not result["banned"]:
                try:
                    spambot = await client.get_entity("@SpamBot")
                    await client.send_message(spambot, "/start")
                    await asyncio.sleep(2)

                    messages = await client.get_messages(spambot, limit=1)
                    if messages:
                        text = messages[0].text or ""
                        text_lower = text.lower()

                        # ── Positive (no restrictions) — EN + RU ──
                        no_limit_kw = [
                            "no limits", "free as a bird", "not limited",        # EN
                            "не ограничен", "всё хорошо", "нет ограничений",     # RU
                        ]
                        # ── Temporary restriction — EN + RU ──
                        temp_kw = [
                            "temporary", "will be removed", "will be lifted",    # EN
                            "временно", "будет снято", "будет автоматически",     # RU
                        ]
                        # ── Permanent restriction — EN + RU ──
                        perm_kw = [
                            "permanent", "forever",                              # EN
                            "навсегда", "навечно",                               # RU
                        ]
                        # ── Frozen / restricted (catch-all) — EN + RU ──
                        restricted_kw = [
                            "limited", "restricted", "frozen",                   # EN
                            "ограничен", "заморожен", "заблокирован",            # RU
                        ]

                        if any(kw in text_lower for kw in no_limit_kw):
                            result["spamblock"] = "none"
                        elif any(kw in text_lower for kw in temp_kw):
                            result["spamblock"] = "temporary"
                            # Try to parse end date
                            import re
                            date_match = re.search(
                                r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})'
                                r'|(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})'
                                r'|(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
                                text, re.IGNORECASE
                            )
                            if date_match:
                                try:
                                    from dateutil import parser as dateparser
                                    result["spamblock_end"] = dateparser.parse(date_match.group(0)).isoformat()
                                except Exception:
                                    pass
                        elif any(kw in text_lower for kw in perm_kw):
                            result["spamblock"] = "permanent"
                        elif any(kw in text_lower for kw in restricted_kw):
                            # SpamBot says account IS limited but doesn't say temp/perm
                            result["spamblock"] = "temporary"
                            result["frozen"] = True
                            logger.warning(f"Account {phone} appears frozen — SpamBot: {text[:200]}")
                        else:
                            # Unrecognized response — do NOT assume clean
                            result["spamblock"] = "unknown"
                            logger.warning(f"Unrecognized SpamBot response for {phone}: {text[:200]}")

                    # Clean up dialog (delay to avoid automation fingerprint)
                    try:
                        import random
                        await asyncio.sleep(random.uniform(2, 5))
                        await client.delete_dialog(spambot)
                    except Exception:
                        pass
                except (errors.UserRestrictedError, errors.ChatWriteForbiddenError):
                    result["spamblock"] = "temporary"
                    result["frozen"] = True
                    logger.warning(f"Account {phone} frozen — cannot message SpamBot (restricted)")
                except Exception as e:
                    logger.warning(f"SpamBot check failed for {phone}: {e}")
                    result["spamblock"] = "unknown"

        except errors.AuthKeyUnregisteredError:
            result["connected"] = True
            result["authorized"] = False
        except errors.UserDeactivatedBanError:
            result["connected"] = True
            result["authorized"] = True
            result["banned"] = True
            result["ban_reason"] = "user_deactivated"
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

    async def check_username(self, account_id: int, username: str) -> dict:
        """Check if a username is available for this account."""
        client = self.get_client(account_id)
        if not client or not client.is_connected():
            return {"status": "error", "detail": "Account not connected"}

        try:
            available = await client(functions.account.CheckUsernameRequest(username=username))
            return {"status": "ok", "available": available}
        except errors.UsernameInvalidError:
            return {"status": "ok", "available": False, "reason": "invalid"}
        except errors.UsernameOccupiedError:
            return {"status": "ok", "available": False, "reason": "occupied"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

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
                    import random
                    await asyncio.sleep(random.uniform(3, 7))
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

    # ── Send file (media / voice / document) ─────────────────────────

    async def send_file(
        self, account_id: int, recipient_username: str, file_path: str,
        caption: str = "", voice_note: bool = False, video_note: bool = False,
        silent: bool = False, delete_dialog_after: bool = False,
    ) -> dict:
        """Send a file/media to a user. Returns {status, message_id} or error."""
        client = self.get_client(account_id)
        if not client or not client.is_connected():
            return {"status": "error", "detail": "Account not connected"}

        try:
            entity = await client.get_entity(recipient_username)
            msg = await client.send_file(
                entity, file_path,
                caption=caption or None,
                voice_note=voice_note,
                video_note=video_note,
                silent=silent,
            )
            if delete_dialog_after:
                try:
                    import random
                    await asyncio.sleep(random.uniform(3, 7))
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
