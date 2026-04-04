"""TG Outreach Notification Bot Service.

Sends Telegram bot notifications when new replies arrive in TG outreach campaigns.
Supports:
  - Instant reply notifications (configurable: all / interested / new_only)
  - Quick reply: manager replies to notification → forwarded to recipient
  - Daily digest of replies
"""
import asyncio
import logging
from datetime import datetime, timedelta
from html import escape as html_escape
from typing import Optional

import httpx
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.device_fingerprints import get_default_app_version

from app.core.config import settings
from app.db import async_session_maker
from app.models.telegram_outreach import (
    TgOutreachNotifSub, TgOutreachNotifLog, TgNotifyMode,
    TgCampaign, TgRecipient, TgAccount, TgIncomingReply,
    TgRecipientStatus, TgProxy,
)

logger = logging.getLogger(__name__)


class TgOutreachNotifService:
    """Sends TG outreach reply notifications via the Telegram Bot API."""

    def __init__(self):
        self._bot_token: Optional[str] = None

    @property
    def bot_token(self) -> Optional[str]:
        if not self._bot_token:
            self._bot_token = settings.TELEGRAM_BOT_TOKEN
        return self._bot_token

    # ── Telegram Bot API helpers ────────────────────────────────────────

    async def _api(self, method: str, **kwargs) -> dict:
        if not self.bot_token:
            return {"ok": False, "description": "No bot token"}
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=kwargs)
            return resp.json()

    async def _send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> Optional[int]:
        """Send message and return message_id, or None on failure."""
        result = await self._api(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        if result.get("ok"):
            return result["result"]["message_id"]
        # Fallback: retry without parse_mode if HTML fails
        if "can't parse entities" in (result.get("description") or "").lower():
            result = await self._api("sendMessage", chat_id=chat_id, text=text)
            if result.get("ok"):
                return result["result"]["message_id"]
        logger.error(f"Failed to send notification to {chat_id}: {result.get('description')}")
        return None

    # ── Reply notification ──────────────────────────────────────────────

    async def notify_new_reply(
        self,
        reply: TgIncomingReply,
        campaign: TgCampaign,
        recipient: TgRecipient,
        account: TgAccount,
        is_first_reply: bool = False,
    ):
        """Send notification about a new TG outreach reply to all subscribers."""
        if not self.bot_token:
            return

        async with async_session_maker() as session:
            subs = await self._get_active_subscribers(session, campaign.id)
            if not subs:
                return

            message_text = self._build_reply_notification(
                reply, campaign, recipient, account,
            )

            for sub in subs:
                # Filter by notify_mode
                if not self._should_notify(sub, recipient, is_first_reply):
                    continue

                msg_id = await self._send_message(sub.chat_id, message_text)
                if msg_id:
                    # Log for quick-reply routing
                    session.add(TgOutreachNotifLog(
                        bot_message_id=msg_id,
                        chat_id=sub.chat_id,
                        recipient_id=recipient.id,
                        account_id=account.id,
                        campaign_id=campaign.id,
                        recipient_username=recipient.username,
                    ))

            await session.commit()

    async def _get_active_subscribers(
        self, session: AsyncSession, campaign_id: int,
    ) -> list[TgOutreachNotifSub]:
        result = await session.execute(
            select(TgOutreachNotifSub).where(
                TgOutreachNotifSub.is_active == True,
            )
        )
        subs = result.scalars().all()
        # Filter by campaign if subscriber has campaign_ids set
        return [
            s for s in subs
            if s.campaign_ids is None or campaign_id in s.campaign_ids
        ]

    def _should_notify(
        self,
        sub: TgOutreachNotifSub,
        recipient: TgRecipient,
        is_first_reply: bool,
    ) -> bool:
        mode = sub.notify_mode
        if mode == TgNotifyMode.ALL.value:
            return True
        if mode == TgNotifyMode.NEW_ONLY.value:
            return is_first_reply
        if mode == TgNotifyMode.INTERESTED.value:
            return (recipient.inbox_tag or "").lower() == "interested"
        return True

    def _build_reply_notification(
        self,
        reply: TgIncomingReply,
        campaign: TgCampaign,
        recipient: TgRecipient,
        account: TgAccount,
    ) -> str:
        name = html_escape(recipient.first_name or "")
        username = recipient.username or ""
        username_line = f'@{html_escape(username)}' if username else ""
        from_parts = [p for p in [name, username_line] if p]
        from_line = " ".join(from_parts) or "Unknown"

        company = html_escape(recipient.company_name or "")
        company_line = f"\n<b>Company:</b> {company}" if company else ""

        campaign_name = html_escape(campaign.name or "Campaign")
        account_name = html_escape(account.username or account.phone or "?")

        body = (reply.message_text or "").strip()
        if len(body) > 300:
            body = body[:300] + "..."
        body = html_escape(body)

        tg_link = f'\n<a href="https://t.me/{username}">Open in Telegram</a>' if username else ""

        return (
            f"✈️ <b>New TG Outreach Reply</b>\n\n"
            f"<b>From:</b> {from_line}{company_line}\n"
            f"<b>Campaign:</b> {campaign_name}\n"
            f"<b>Account:</b> @{account_name}\n\n"
            f"<code>{body}</code>\n"
            f"{tg_link}\n\n"
            f"<i>Reply to this message to respond.</i>"
        )

    # ── Quick reply (manager replies to notification) ───────────────────

    async def handle_quick_reply(
        self, chat_id: str, reply_to_msg_id: int, text: str,
    ) -> bool:
        """Forward manager's reply to the recipient via the outreach account."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifLog).where(
                    TgOutreachNotifLog.chat_id == chat_id,
                    TgOutreachNotifLog.bot_message_id == reply_to_msg_id,
                )
            )
            log = result.scalar_one_or_none()
            if not log:
                return False

            # Load account and recipient
            account = await session.get(TgAccount, log.account_id)
            recipient = await session.get(TgRecipient, log.recipient_id)
            if not account or not recipient or not recipient.username:
                await self._send_message(
                    chat_id, "Could not find the recipient or account."
                )
                return False

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

            # Connect and send via telegram_engine
            from app.services.telegram_engine import telegram_engine

            try:
                client = await telegram_engine.connect(
                    account.id,
                    phone=account.phone,
                    api_id=account.api_id,
                    api_hash=account.api_hash,
                    device_model=account.device_model or "PC 64bit",
                    system_version=account.system_version or "Windows 10",
                    app_version=account.app_version or get_default_app_version(),
                    lang_code=account.lang_code or "en",
                    system_lang_code=account.system_lang_code or "en-US",
                    proxy=proxy_dict,
                )

                if not await client.is_user_authorized():
                    await self._send_message(chat_id, "Account session expired.")
                    await telegram_engine.disconnect(account.id)
                    return False

                entity = await client.get_entity(recipient.username)
                await client.send_message(entity, text)
                await telegram_engine.disconnect(account.id)

                await self._send_message(
                    chat_id,
                    f"Sent to @{html_escape(recipient.username)} via @{html_escape(account.username or account.phone)}",
                )
                return True

            except Exception as e:
                logger.error(f"Quick reply failed: {e}")
                await self._send_message(chat_id, f"Failed to send: {html_escape(str(e)[:200])}")
                try:
                    await telegram_engine.disconnect(account.id)
                except Exception:
                    pass
                return False

    # ── /start tg_outreach handler ──────────────────────────────────────

    async def handle_start(self, chat_id: str, username: str, first_name: str):
        """Register or re-activate a manager for TG outreach notifications."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.chat_id == chat_id,
                )
            )
            sub = result.scalar_one_or_none()

            if sub:
                sub.is_active = True
                sub.username = username or sub.username
                sub.first_name = first_name or sub.first_name
                sub.updated_at = datetime.utcnow()
                status = "re-activated"
            else:
                session.add(TgOutreachNotifSub(
                    chat_id=chat_id,
                    username=username or None,
                    first_name=first_name or None,
                ))
                status = "subscribed"

            await session.commit()

        await self._send_message(
            chat_id,
            f"✅ <b>TG Outreach Notifications {status}!</b>\n\n"
            f"You'll receive notifications when prospects reply to outreach campaigns.\n\n"
            f"<b>Commands:</b>\n"
            f"/tg_settings — view/change notification mode\n"
            f"/tg_digest — get today's reply digest\n"
            f"/tg_stop — pause notifications\n\n"
            f"<i>Reply to any notification message to respond directly.</i>",
        )

    # ── /tg_settings handler ────────────────────────────────────────────

    async def handle_settings(self, chat_id: str):
        """Show current notification settings."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.chat_id == chat_id,
                )
            )
            sub = result.scalar_one_or_none()

            if not sub:
                await self._send_message(
                    chat_id,
                    "Not subscribed. Use /start tg_outreach to subscribe.",
                )
                return

            mode_label = {
                "all": "All replies",
                "interested": "Only 'Interested' tagged",
                "new_only": "Only first reply from a contact",
            }.get(sub.notify_mode, sub.notify_mode)

            campaigns = "All campaigns" if not sub.campaign_ids else f"{len(sub.campaign_ids)} campaigns"
            digest = f"Daily at {sub.digest_hour}:00 UTC" if sub.daily_digest else "Off"

            await self._send_message(
                chat_id,
                f"⚙️ <b>Notification Settings</b>\n\n"
                f"<b>Mode:</b> {mode_label}\n"
                f"<b>Campaigns:</b> {campaigns}\n"
                f"<b>Daily digest:</b> {digest}\n"
                f"<b>Status:</b> {'Active' if sub.is_active else 'Paused'}\n\n"
                f"<b>Change mode:</b>\n"
                f"/tg_mode_all — all replies\n"
                f"/tg_mode_interested — only interested\n"
                f"/tg_mode_new — only first reply\n"
                f"/tg_digest_on — enable daily digest\n"
                f"/tg_digest_off — disable daily digest",
            )

    # ── Mode/digest toggle commands ─────────────────────────────────────

    async def handle_mode_change(self, chat_id: str, mode: str):
        """Change notification mode."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.chat_id == chat_id,
                )
            )
            sub = result.scalar_one_or_none()
            if not sub:
                await self._send_message(chat_id, "Not subscribed. Use /start tg_outreach first.")
                return

            sub.notify_mode = mode
            sub.updated_at = datetime.utcnow()
            await session.commit()

        label = {"all": "All replies", "interested": "Interested only", "new_only": "First reply only"}.get(mode, mode)
        await self._send_message(chat_id, f"✅ Notification mode set to: <b>{label}</b>")

    async def handle_digest_toggle(self, chat_id: str, enabled: bool):
        """Toggle daily digest."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.chat_id == chat_id,
                )
            )
            sub = result.scalar_one_or_none()
            if not sub:
                await self._send_message(chat_id, "Not subscribed. Use /start tg_outreach first.")
                return

            sub.daily_digest = enabled
            sub.updated_at = datetime.utcnow()
            await session.commit()

        status = "enabled" if enabled else "disabled"
        await self._send_message(chat_id, f"✅ Daily digest <b>{status}</b>")

    # ── /tg_stop ────────────────────────────────────────────────────────

    async def handle_stop(self, chat_id: str):
        """Pause notifications."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.chat_id == chat_id,
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.is_active = False
                sub.updated_at = datetime.utcnow()
                await session.commit()

        await self._send_message(
            chat_id,
            "⏸ Notifications paused. Use /start tg_outreach to re-activate.",
        )

    # ── Daily digest ────────────────────────────────────────────────────

    async def send_daily_digest(self):
        """Send daily digest to all subscribers who opted in. Called by scheduler."""
        if not self.bot_token:
            return

        now = datetime.utcnow()
        current_hour = now.hour

        async with async_session_maker() as session:
            result = await session.execute(
                select(TgOutreachNotifSub).where(
                    TgOutreachNotifSub.is_active == True,
                    TgOutreachNotifSub.daily_digest == True,
                    TgOutreachNotifSub.digest_hour == current_hour,
                )
            )
            subs = result.scalars().all()
            if not subs:
                return

            # Get today's replies
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            reply_result = await session.execute(
                select(
                    TgIncomingReply,
                    TgCampaign.name.label("campaign_name"),
                    TgRecipient.username.label("recipient_username"),
                    TgRecipient.first_name.label("recipient_name"),
                ).join(
                    TgCampaign, TgIncomingReply.campaign_id == TgCampaign.id,
                ).join(
                    TgRecipient, TgIncomingReply.recipient_id == TgRecipient.id,
                ).where(
                    TgIncomingReply.received_at >= today_start,
                ).order_by(TgIncomingReply.received_at.desc())
            )
            rows = reply_result.all()

            if not rows:
                # No replies today — skip digest
                return

            # Build digest
            digest_lines = [f"📊 <b>TG Outreach Daily Digest</b>\n{now.strftime('%B %d, %Y')}\n"]
            digest_lines.append(f"<b>Total replies today:</b> {len(rows)}\n")

            for reply_obj, campaign_name, recipient_username, recipient_name in rows[:20]:
                name = html_escape(recipient_name or "")
                uname = f"@{html_escape(recipient_username)}" if recipient_username else ""
                who = f"{name} {uname}".strip() or "Unknown"
                camp = html_escape(campaign_name or "?")
                preview = (reply_obj.message_text or "")[:80]
                if len(reply_obj.message_text or "") > 80:
                    preview += "..."
                preview = html_escape(preview)
                time_str = reply_obj.received_at.strftime("%H:%M") if reply_obj.received_at else ""

                digest_lines.append(f"• <b>{who}</b> ({camp}) {time_str}\n  <i>{preview}</i>")

            if len(rows) > 20:
                digest_lines.append(f"\n... and {len(rows) - 20} more")

            digest_text = "\n".join(digest_lines)

            for sub in subs:
                # Filter by campaign if needed
                if sub.campaign_ids:
                    filtered = [r for r in rows if r[0].campaign_id in sub.campaign_ids]
                    if not filtered:
                        continue
                await self._send_message(sub.chat_id, digest_text)


# Singleton
tg_outreach_notif_service = TgOutreachNotifService()
