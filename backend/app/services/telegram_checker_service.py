"""Telegram Last Seen Checker Service.

Uses Telethon (MTProto API) to check when Telegram users were last online.
Requires a user account (not bot) with api_id, api_hash, and phone number.

Usage:
1. Upload CSV with 'username' column via Sally Bot
2. Service checks each username's last seen status
3. Returns CSV with added 'last_seen' and 'last_seen_hours' columns
"""
import asyncio
import csv
import io
import json
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
    UserStatusEmpty,
)
from telethon.errors import (
    FloodWaitError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Session file path
SESSION_PATH = "/app/state/telegram_checker.session"
# Checkpoint file for saving progress
CHECKPOINT_PATH = "/app/state/tg_checker_checkpoint.json"


class TelegramCheckerService:
    """Service for checking Telegram last seen status."""

    def __init__(self):
        self.api_id = settings.TELEGRAM_CHECKER_API_ID
        self.api_hash = settings.TELEGRAM_CHECKER_API_HASH
        self.phone = settings.TELEGRAM_CHECKER_PHONE
        self.client: Optional[TelegramClient] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Telegram. Returns True if connected successfully."""
        if not self.api_id or not self.api_hash:
            logger.warning("Telegram Checker not configured (missing api_id/api_hash)")
            return False

        if self._connected and self.client:
            return True

        try:
            self.client = TelegramClient(SESSION_PATH, self.api_id, self.api_hash)
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.warning("Telegram Checker not authorized. Run auth script first.")
                return False

            self._connected = True
            me = await self.client.get_me()
            logger.info(f"Telegram Checker connected as {me.first_name} (@{me.username})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect Telegram Checker: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()
            self._connected = False

    def _save_checkpoint(self, results: list, fieldnames: list, stats: dict):
        """Save intermediate results to checkpoint file."""
        try:
            checkpoint = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stats": stats,
                "fieldnames": list(fieldnames),
                "results": results,
            }
            Path(CHECKPOINT_PATH).write_text(json.dumps(checkpoint, ensure_ascii=False, default=str))
            logger.info(f"Checkpoint saved: {stats['checked']} checked")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _parse_status(self, status) -> tuple[str, Optional[int]]:
        """Parse user status to human-readable string and hours ago.

        Returns:
            (status_text, hours_ago) - hours_ago is None if unknown
        """
        now = datetime.now(timezone.utc)

        if status is None or isinstance(status, UserStatusEmpty):
            return "unknown", None

        if isinstance(status, UserStatusOnline):
            return "online", 0

        if isinstance(status, UserStatusOffline):
            was_online = status.was_online
            if was_online:
                if was_online.tzinfo is None:
                    was_online = was_online.replace(tzinfo=timezone.utc)
                delta = now - was_online
                hours = int(delta.total_seconds() / 3600)
                return was_online.strftime("%Y-%m-%d %H:%M UTC"), hours
            return "offline", None

        if isinstance(status, UserStatusRecently):
            return "recently", 24  # Within 1-3 days typically

        if isinstance(status, UserStatusLastWeek):
            return "last_week", 168  # ~7 days

        if isinstance(status, UserStatusLastMonth):
            return "last_month", 720  # ~30 days

        return "unknown", None

    async def check_username(self, username: str) -> dict:
        """Check a single username's last seen status.

        Returns:
            {username, last_seen, last_seen_hours, error}
        """
        username = username.strip().lstrip("@")

        if not username:
            return {
                "username": username,
                "last_seen": "invalid",
                "last_seen_hours": None,
                "error": "empty username",
            }

        try:
            entity = await self.client.get_entity(username)
            status_text, hours = self._parse_status(entity.status)

            logger.info(f"Checked @{username}: {status_text} ({hours}h ago)" if hours else f"Checked @{username}: {status_text}")

            return {
                "username": username,
                "last_seen": status_text,
                "last_seen_hours": hours,
                "first_name": getattr(entity, "first_name", ""),
                "last_name": getattr(entity, "last_name", ""),
                "error": None,
            }

        except UsernameNotOccupiedError:
            return {
                "username": username,
                "last_seen": "not_found",
                "last_seen_hours": None,
                "error": "username not found",
            }

        except UsernameInvalidError:
            return {
                "username": username,
                "last_seen": "invalid",
                "last_seen_hours": None,
                "error": "invalid username",
            }

        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds}s")
            # If flood wait is more than 5 minutes, abort instead of waiting
            if e.seconds > 300:
                logger.error(f"Flood wait too long ({e.seconds}s), aborting")
                return {
                    "username": username,
                    "last_seen": "flood_limit",
                    "last_seen_hours": None,
                    "error": f"Telegram flood limit: wait {e.seconds // 60} minutes",
                }
            await asyncio.sleep(e.seconds)
            return await self.check_username(username)  # Retry

        except Exception as e:
            logger.error(f"Error checking {username}: {e}")
            return {
                "username": username,
                "last_seen": "error",
                "last_seen_hours": None,
                "error": str(e),
            }

    async def check_csv(
        self,
        csv_content: str,
        max_hours: int = 72,
        delay: float = 1.5,
        progress_callback=None,
    ) -> tuple[str, dict]:
        """Check all usernames from CSV content.

        Args:
            csv_content: CSV string with 'username' column
            max_hours: Filter to users seen within this many hours (0 = no filter)
            delay: Delay between checks in seconds
            progress_callback: async func(current, total, username) for progress updates

        Returns:
            (result_csv_content, stats_dict)
        """
        if not await self.connect():
            raise RuntimeError("Telegram Checker not connected")

        # Parse input CSV
        reader = csv.DictReader(io.StringIO(csv_content))

        # Find username column (case-insensitive)
        fieldnames = reader.fieldnames or []
        username_col = None
        for col in fieldnames:
            if col.lower() in ("username", "tg_username", "telegram", "tg"):
                username_col = col
                break

        if not username_col:
            raise ValueError("CSV must have a 'username' column")

        rows = list(reader)
        total = len(rows)
        results = []
        stats = {
            "total": total,
            "checked": 0,
            "online": 0,
            "recent": 0,  # within max_hours
            "old": 0,
            "unknown": 0,
            "not_found": 0,
            "errors": 0,
        }

        flood_aborted = False
        for i, row in enumerate(rows):
            username = row.get(username_col, "").strip()

            if not username:
                row["last_seen"] = ""
                row["last_seen_hours"] = ""
                row["tg_status"] = "skipped"
                results.append(row)
                continue

            # Check username
            result = await self.check_username(username)
            stats["checked"] += 1

            row["last_seen"] = result["last_seen"]
            row["last_seen_hours"] = result["last_seen_hours"] if result["last_seen_hours"] is not None else ""

            # Determine status
            hours = result["last_seen_hours"]
            if result["error"]:
                if "flood" in result["error"].lower():
                    row["tg_status"] = "flood_limit"
                    stats["errors"] += 1
                    results.append(row)
                    flood_aborted = True
                    logger.warning(f"Flood limit hit after {stats['checked']} checks, returning partial results")
                    break  # Stop processing, return what we have
                elif "not found" in result["error"]:
                    row["tg_status"] = "not_found"
                    stats["not_found"] += 1
                else:
                    row["tg_status"] = "error"
                    stats["errors"] += 1
            elif hours is not None:
                if hours == 0:
                    row["tg_status"] = "online"
                    stats["online"] += 1
                elif max_hours == 0 or hours <= max_hours:
                    row["tg_status"] = "recent"
                    stats["recent"] += 1
                else:
                    row["tg_status"] = "old"
                    stats["old"] += 1
            else:
                row["tg_status"] = "unknown"
                stats["unknown"] += 1

            results.append(row)

            # Save checkpoint every 10 contacts
            if stats["checked"] % 10 == 0:
                self._save_checkpoint(results, fieldnames, stats)

            # Progress callback
            if progress_callback:
                try:
                    await progress_callback(i + 1, total, username)
                except Exception:
                    pass

            # Delay between checks (randomized 12-15s to avoid Telegram flood)
            if i < total - 1:
                await asyncio.sleep(random.uniform(12.0, 15.0))

        # Mark if we aborted due to flood
        stats["flood_aborted"] = flood_aborted
        stats["remaining"] = total - len(results)

        # Generate output CSV
        output_fieldnames = list(fieldnames) + ["last_seen", "last_seen_hours", "tg_status"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(results)

        return output.getvalue(), stats

    async def check_csv_and_filter(
        self,
        csv_content: str,
        max_hours: int = 72,
        delay: float = 1.5,
        progress_callback=None,
    ) -> tuple[str, str, dict]:
        """Check CSV and return both full results and filtered (recent only).

        Returns:
            (full_csv, filtered_csv, stats)
        """
        try:
            full_csv, stats = await self.check_csv(
                csv_content, max_hours=max_hours, delay=delay, progress_callback=progress_callback
            )
        finally:
            # Clean up checkpoint after successful completion
            try:
                Path(CHECKPOINT_PATH).unlink(missing_ok=True)
            except Exception:
                pass

        # Filter to recent only
        reader = csv.DictReader(io.StringIO(full_csv))
        fieldnames = reader.fieldnames or []

        filtered_rows = []
        for row in reader:
            status = row.get("tg_status", "")
            if status in ("online", "recent"):
                filtered_rows.append(row)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

        stats["filtered_count"] = len(filtered_rows)

        return full_csv, output.getvalue(), stats


# Singleton instance
telegram_checker_service = TelegramCheckerService()


async def run_auth():
    """Interactive authorization script. Run once to create session."""
    api_id = int(os.getenv("TELEGRAM_CHECKER_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_CHECKER_API_HASH", "")
    phone = os.getenv("TELEGRAM_CHECKER_PHONE", "")

    if not api_id or not api_hash or not phone:
        print("Set TELEGRAM_CHECKER_API_ID, TELEGRAM_CHECKER_API_HASH, TELEGRAM_CHECKER_PHONE")
        return

    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter the code from Telegram: ")
        await client.sign_in(phone, code)

    me = await client.get_me()
    print(f"Authorized as {me.first_name} (@{me.username})")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run_auth())
