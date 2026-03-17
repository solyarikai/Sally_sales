"""Sally Bot Service — silent Telegram client chat monitor.

Polls for new messages, stores them, and periodically analyzes with Gemini.
In groups: silent (stores only). In DMs: commands + friendly GPT-powered replies.

Commands (DM only):
  /план <текст>    — загрузить план для клиента
  /отчет <текст>   — отправить отчет (сохраняется + пересылается боссу)
  /статус          — показать прогресс по плану
  /история [дни]   — история отчетов
  /проекты         — список проектов пользователя
  /помощь          — справка по командам
"""
import logging
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone, date, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import async_session_maker
from app.models.telegram_chat import TelegramChat, TelegramChatMessage
from app.models.project_report import (
    ProjectReport, ProjectPlan, ProjectProgressItem,
    ProjectReportSubscription, ReportRole, ProgressStatus,
)
from app.models.contact import Project

logger = logging.getLogger(__name__)

# State: chat_id -> {"project_id": int, "asked_at": datetime}
_awaiting_report: dict[int, dict] = {}

HELP_TEXT = """
📋 *Команды Sally Report Bot*

/план <текст> — загрузить план для клиента (AI разобьет на пункты)
/отчет <текст> — отправить отчет (сохраняется + пересылается боссу)
/статус — показать прогресс по плану
/история [дни] — история отчетов (по умолчанию 7 дней)
/проекты — список ваших проектов
/check\_tg — проверить last seen для CSV (прикрепите файл)
/помощь — эта справка

Каждый вечер я буду спрашивать "Что сегодня было сделано по проекту X?"
Просто ответьте текстом — отчет сохранится и переслается боссу.
"""

# State for TG checker: chat_id -> {"status": "waiting_file" | "processing", ...}
_tg_checker_state: dict[int, dict] = {}

GREETING = (
    "Hey! I'm Sally AI BDM — Petr just added me to maximize the result for Rizzult project — "
    "result… Rizzult… get it? "
    "I'll be back with brilliant thoughts!"
)

# Track DM reply count per chat — share links on 1st reply, then every 10th
_dm_reply_count: dict[int, int] = defaultdict(int)

SALES_LINKS = (
    "\n\nCheck out what we do: getsally.io | Follow updates: @rinatkhat"
)


async def _generate_dm_reply(user_name: str, user_message: str, chat_id: int) -> str:
    """Generate a friendly DM reply using GPT-4o-mini."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 18:
        time_of_day = "afternoon"
    elif 18 <= hour < 22:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    system_prompt = f"""You are Sally AI BDM, a friendly bot for the Sally B2B lead generation team.
Someone is messaging you directly. Respond with warmth and personality — like a chill,
helpful bro. Keep it concise (1-3 sentences max).

It's currently {time_of_day} (UTC). Use appropriate greeting if natural.

If they ask what you do — you're an AI assistant for the Sally team, helping with
B2B lead generation, project tracking, and outreach operations.

Do NOT include any links or mentions of websites/channels — that's handled separately.

Never be robotic. Be genuine, casual, human."""

    reply = None

    # Try OpenAI first
    if settings.OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"User '{user_name}' says: {user_message}"},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.9,
                    },
                )
                data = resp.json()
                if "choices" in data:
                    reply = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}")

    # Fallback to Gemini
    if not reply and settings.GEMINI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser '{user_name}' says: {user_message}"}]}],
                        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.9},
                    },
                )
                data = resp.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    if not reply:
        reply = f"Hey {user_name}! Have a great {time_of_day}! I'm Sally AI BDM — working behind the scenes for the Sally lead gen team."

    # Hardcode links: first reply always, then every 10th — don't trust GPT for this
    _dm_reply_count[chat_id] += 1
    count = _dm_reply_count[chat_id]
    if count == 1 or count % 10 == 0:
        reply += SALES_LINKS

    return reply


class SallyBotService:
    def __init__(self):
        self.token = settings.TELEGRAM_SALLY_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self._offset = 0
        self._running = False
        self._bot_id = None

    async def _api(self, method: str, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post(f"{self.base_url}/{method}", json=kwargs)
            return resp.json()

    async def _get_bot_id(self) -> int:
        if not self._bot_id:
            info = await self._api("getMe")
            self._bot_id = info.get("result", {}).get("id")
        return self._bot_id

    async def send_message(self, chat_id: int, text: str, parse_mode: str = None) -> dict:
        params = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        return await self._api("sendMessage", **params)

    async def _handle_update(self, update: dict):
        """Process a single Telegram update."""
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            logger.debug(f"Sally update skipped (no message): {list(update.keys())}")
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "")
        sender = msg.get("from", {})
        text = msg.get("text") or msg.get("caption") or ""
        logger.info(f"Sally update: chat={chat_id} type={chat_type} from={sender.get('first_name')} text={text[:50] if text else '(empty)'}")

        # Bot added to a group — send greeting
        new_members = msg.get("new_chat_members", [])
        if new_members:
            bot_id = await self._get_bot_id()
            for member in new_members:
                if member.get("id") == bot_id:
                    logger.info(f"Sally bot added to chat {chat_id}: {chat.get('title')}")
                    await self.send_message(chat_id, GREETING)
                    await self._ensure_chat(chat_id, chat.get("title"), chat_type)
                    return

        # DM (private chat) — commands or GPT reply
        if chat_type == "private":
            user_name = sender.get("first_name", "friend")
            username = sender.get("username")

            # Handle commands
            if text.startswith("/"):
                await self._handle_command(chat_id, text, username, user_name)
                return

            # Handle document upload for TG checker
            document = msg.get("document")
            if document and chat_id in _tg_checker_state:
                state = _tg_checker_state[chat_id]
                if state.get("status") == "waiting_file":
                    await self._handle_tg_checker_file(chat_id, document, msg.get("caption", ""))
                    return

            # Check if awaiting report
            if chat_id in _awaiting_report:
                await self._handle_report_response(chat_id, text, username, user_name)
                return

            # Default: friendly GPT reply
            reply = await _generate_dm_reply(user_name, text, chat_id)
            await self.send_message(chat_id, reply)
            return

        # Group messages — silent store only
        if chat_type not in ("group", "supergroup"):
            return

        msg_type = "text"
        for t in ["photo", "document", "video", "voice", "sticker", "animation"]:
            if t in msg:
                msg_type = t
                break

        async with async_session_maker() as session:
            # Ensure chat exists (separate commit to avoid autoflush conflicts)
            await self._ensure_chat(chat_id, chat.get("title"), chat_type)

            # Store message + update counter in one transaction
            chat_msg = TelegramChatMessage(
                chat_id=chat_id,
                message_id=msg.get("message_id"),
                sender_id=sender.get("id"),
                sender_name=f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip(),
                sender_username=sender.get("username"),
                text=text,
                reply_to_message_id=msg.get("reply_to_message", {}).get("message_id") if msg.get("reply_to_message") else None,
                sent_at=datetime.fromtimestamp(msg.get("date", 0), tz=timezone.utc),
                message_type=msg_type,
                raw_data=msg,
            )
            session.add(chat_msg)
            await session.flush()

            result = await session.execute(
                select(TelegramChat).where(TelegramChat.chat_id == chat_id)
            )
            tc = result.scalar_one_or_none()
            if tc:
                tc.message_count = (tc.message_count or 0) + 1
                tc.last_message_at = chat_msg.sent_at

            await session.commit()
            logger.info(f"Sally stored msg #{chat_msg.message_id} from {chat_msg.sender_name} in chat {chat_id}")

    async def _ensure_chat(self, chat_id: int, title: str, chat_type: str, session: AsyncSession = None):
        """Create TelegramChat record if it doesn't exist."""
        should_close = False
        if session is None:
            session = async_session_maker()
            should_close = True

        try:
            result = await session.execute(
                select(TelegramChat).where(TelegramChat.chat_id == chat_id)
            )
            if not result.scalar_one_or_none():
                session.add(TelegramChat(
                    chat_id=chat_id,
                    chat_title=title,
                    chat_type=chat_type,
                ))
                await session.commit()
        finally:
            if should_close:
                await session.close()

    async def poll_loop(self):
        """Long-polling loop for receiving updates."""
        if not self.token:
            logger.warning("TELEGRAM_SALLY_BOT_TOKEN not set, Sally bot disabled")
            return

        self._running = True
        self._bot_id = (await self._api("getMe")).get("result", {}).get("id")
        logger.info(f"Sally bot polling started (bot_id={self._bot_id})")

        while self._running:
            try:
                data = await self._api(
                    "getUpdates",
                    offset=self._offset,
                    timeout=30,
                    allowed_updates=["message", "edited_message", "my_chat_member"],
                )
                if not data.get("ok"):
                    logger.error(f"Sally poll failed: {data}")
                updates = data.get("result", [])
                if updates:
                    logger.info(f"Sally poll: got {len(updates)} updates")
                for update in updates:
                    self._offset = update["update_id"] + 1
                    try:
                        await self._handle_update(update)
                    except Exception as e:
                        logger.error(f"Error handling update: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Sally bot poll error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self._running = False

    # ─────────────────────────────────────────────────────────────────────────
    # Command Handlers
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_command(self, chat_id: int, text: str, username: str, first_name: str):
        """Route command to appropriate handler."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/план", "/plan"):
            await self._handle_plan_command(chat_id, arg, username, first_name)
        elif cmd in ("/отчет", "/report"):
            await self._handle_report_command(chat_id, arg, username, first_name)
        elif cmd in ("/статус", "/status"):
            await self._handle_status_command(chat_id, username)
        elif cmd in ("/история", "/history"):
            await self._handle_history_command(chat_id, arg, username)
        elif cmd in ("/проекты", "/projects"):
            await self._handle_projects_command(chat_id, username)
        elif cmd in ("/помощь", "/help", "/start"):
            await self.send_message(chat_id, HELP_TEXT, parse_mode="Markdown")
        elif cmd in ("/check_tg", "/checktg", "/tg_check"):
            await self._handle_check_tg_command(chat_id)
        else:
            await self.send_message(chat_id, f"Неизвестная команда. Напишите /помощь для справки.")

    async def _handle_plan_command(self, chat_id: int, plan_text: str, username: str, first_name: str):
        """Upload a plan and parse it into items."""
        if not plan_text:
            await self.send_message(chat_id, "Напишите план после команды: /план <текст плана>")
            return

        # Find user's project subscription
        async with async_session_maker() as session:
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            sub = result.scalar_one_or_none()

            if not sub:
                await self.send_message(chat_id, "Вы не подписаны ни на один проект. Обратитесь к администратору.")
                return

            # Import here to avoid circular
            from app.services.project_report_service import parse_plan_into_items

            # Create plan
            plan = ProjectPlan(
                project_id=sub.project_id,
                uploaded_by_chat_id=str(chat_id),
                title=f"План от {first_name} ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})",
                content=plan_text,
                content_type="text",
                is_active=True,
                version=1,
            )
            session.add(plan)
            await session.flush()

            # Deactivate previous plans
            await session.execute(
                select(ProjectPlan).where(
                    and_(
                        ProjectPlan.project_id == sub.project_id,
                        ProjectPlan.id != plan.id,
                        ProjectPlan.is_active == True,
                    )
                )
            )
            for old_plan in (await session.execute(
                select(ProjectPlan).where(
                    and_(
                        ProjectPlan.project_id == sub.project_id,
                        ProjectPlan.id != plan.id,
                        ProjectPlan.is_active == True,
                    )
                )
            )).scalars():
                old_plan.is_active = False

            # Parse plan into items
            items = await parse_plan_into_items(plan_text)
            plan.ai_parsed_items = items

            for item in items:
                progress_item = ProjectProgressItem(
                    plan_id=plan.id,
                    project_id=sub.project_id,
                    item_text=item.get("item", ""),
                    due_date=item.get("due_date"),
                    status=ProgressStatus.pending,
                )
                session.add(progress_item)

            await session.commit()

            # Get project name
            proj_result = await session.execute(
                select(Project).where(Project.id == sub.project_id)
            )
            project = proj_result.scalar_one_or_none()
            project_name = project.name if project else "проект"

            await self.send_message(
                chat_id,
                f"✅ План сохранен для проекта *{project_name}*\n\n"
                f"Распознано пунктов: {len(items)}\n\n"
                f"Используйте /статус для просмотра прогресса.",
                parse_mode="Markdown"
            )

    async def _handle_report_command(self, chat_id: int, report_text: str, username: str, first_name: str):
        """Save a daily report and forward to boss."""
        if not report_text:
            await self.send_message(chat_id, "Напишите отчет после команды: /отчет <текст отчета>")
            return

        await self._save_report(chat_id, report_text, username, first_name)

    async def _handle_report_response(self, chat_id: int, text: str, username: str, first_name: str):
        """Handle free-form report response when awaiting."""
        await self._save_report(chat_id, text, username, first_name)
        # Clear awaiting state
        del _awaiting_report[chat_id]

    async def _save_report(self, chat_id: int, report_text: str, username: str, first_name: str):
        """Save report, analyze against plan, forward to boss."""
        async with async_session_maker() as session:
            # Find subscription
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            sub = result.scalar_one_or_none()

            if not sub:
                await self.send_message(chat_id, "Вы не подписаны ни на один проект.")
                return

            # Import here to avoid circular
            from app.services.project_report_service import analyze_report_against_plan, generate_report_summary

            # Create report
            today = date.today()
            report = ProjectReport(
                project_id=sub.project_id,
                lead_chat_id=str(chat_id),
                lead_username=username,
                lead_first_name=first_name,
                report_date=today,
                report_text=report_text,
            )
            session.add(report)
            await session.flush()

            # Analyze against plan
            analysis = await analyze_report_against_plan(session, sub.project_id, report_text)
            report.ai_summary = analysis.get("summary", "")

            # Get project name
            proj_result = await session.execute(
                select(Project).where(Project.id == sub.project_id)
            )
            project = proj_result.scalar_one_or_none()
            project_name = project.name if project else "проект"

            # Find boss subscription to forward
            boss_result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.project_id == sub.project_id,
                        ProjectReportSubscription.role == ReportRole.boss,
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            boss_sub = boss_result.scalar_one_or_none()

            if boss_sub:
                boss_message = (
                    f"📝 *Отчет от {first_name}*\n"
                    f"Проект: {project_name}\n"
                    f"Дата: {today.strftime('%d.%m.%Y')}\n\n"
                    f"{report_text}\n\n"
                    f"---\n"
                    f"📊 AI Summary: {analysis.get('summary', 'N/A')}"
                )
                try:
                    await self.send_message(int(boss_sub.chat_id), boss_message, parse_mode="Markdown")
                    report.forwarded_to_boss = True
                    report.forwarded_at = datetime.now(timezone.utc)
                except Exception as e:
                    logger.error(f"Failed to forward report to boss: {e}")

            sub.last_reported_at = datetime.now(timezone.utc)
            await session.commit()

            # Confirm to user
            matches = analysis.get("matches", [])
            matches_text = ""
            if matches:
                matches_text = f"\n\n✅ Отмечено выполненным: {len(matches)} пунктов плана"

            await self.send_message(
                chat_id,
                f"✅ Отчет сохранен для проекта *{project_name}*{matches_text}",
                parse_mode="Markdown"
            )

    async def _handle_status_command(self, chat_id: int, username: str):
        """Show project progress status."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            sub = result.scalar_one_or_none()

            if not sub:
                await self.send_message(chat_id, "Вы не подписаны ни на один проект.")
                return

            from app.services.project_report_service import get_progress_status, format_progress_for_telegram
            status = await get_progress_status(session, sub.project_id)
            text = format_progress_for_telegram(status)
            await self.send_message(chat_id, text, parse_mode="Markdown")

    async def _handle_history_command(self, chat_id: int, days_arg: str, username: str):
        """Show report history."""
        try:
            days = int(days_arg) if days_arg else 7
        except ValueError:
            days = 7

        async with async_session_maker() as session:
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            sub = result.scalar_one_or_none()

            if not sub:
                await self.send_message(chat_id, "Вы не подписаны ни на один проект.")
                return

            from app.services.project_report_service import get_report_history
            history = await get_report_history(session, sub.project_id, days=days)

            if not history:
                await self.send_message(chat_id, f"Нет отчетов за последние {days} дней.")
                return

            text = f"📜 *История отчетов за {days} дней*\n\n"
            for report in history:
                # report is a dict: {id, date, lead_name, summary, forwarded}
                text += f"*{report['date']}* — {report['lead_name']}\n"
                text += f"_{report['summary']}_\n\n"

            await self.send_message(chat_id, text, parse_mode="Markdown")

    async def _handle_projects_command(self, chat_id: int, username: str):
        """Show user's projects."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.is_active == True,
                    )
                )
            )
            subs = result.scalars().all()

            if not subs:
                await self.send_message(chat_id, "Вы не подписаны ни на один проект.")
                return

            text = "📁 *Ваши проекты:*\n\n"
            for sub in subs:
                proj_result = await session.execute(
                    select(Project).where(Project.id == sub.project_id)
                )
                project = proj_result.scalar_one_or_none()
                if project:
                    role = "👨‍💼 Босс" if sub.role == ReportRole.boss else "👤 Лид"
                    text += f"• *{project.name}* — {role}\n"

            await self.send_message(chat_id, text, parse_mode="Markdown")

    async def ask_for_report(self, chat_id: int, project_id: int, project_name: str, question_template: str = None):
        """Send evening question to lead (called by scheduler)."""
        question = question_template or f"Привет! Что сегодня было сделано по проекту *{project_name}*?"
        question = question.replace("{name}", project_name)

        await self.send_message(chat_id, question, parse_mode="Markdown")

        # Mark as awaiting report
        _awaiting_report[chat_id] = {
            "project_id": project_id,
            "asked_at": datetime.now(timezone.utc),
        }

        # Update subscription
        async with async_session_maker() as session:
            result = await session.execute(
                select(ProjectReportSubscription).where(
                    and_(
                        ProjectReportSubscription.chat_id == str(chat_id),
                        ProjectReportSubscription.project_id == project_id,
                    )
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.last_asked_at = datetime.now(timezone.utc)
                await session.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Telegram Checker Commands
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_check_tg_command(self, chat_id: int):
        """Start TG checker flow — ask user to upload CSV."""
        _tg_checker_state[chat_id] = {
            "status": "waiting_file",
            "started_at": datetime.now(timezone.utc),
        }
        await self.send_message(
            chat_id,
            "📤 Отправьте CSV файл с колонкой `username` (или `tg_username`).\n\n"
            "Я проверю last seen каждого контакта и верну файл с результатами.\n"
            "Можно добавить в caption число часов для фильтрации (по умолчанию 72ч).",
        )

    async def _handle_tg_checker_file(self, chat_id: int, document: dict, caption: str):
        """Process uploaded CSV file for TG checking."""
        file_name = document.get("file_name", "file")
        if not file_name.lower().endswith(".csv"):
            await self.send_message(chat_id, "❌ Нужен CSV файл. Отправьте файл с расширением .csv")
            return

        # Parse max_hours from caption
        max_hours = 72
        if caption:
            try:
                max_hours = int(caption.strip())
            except ValueError:
                pass

        _tg_checker_state[chat_id]["status"] = "processing"
        await self.send_message(chat_id, f"⏳ Скачиваю файл и начинаю проверку (фильтр: {max_hours}ч)...")

        try:
            # Download file
            file_id = document.get("file_id")
            csv_content = await self._download_file(file_id)

            if not csv_content:
                await self.send_message(chat_id, "❌ Не удалось скачать файл")
                del _tg_checker_state[chat_id]
                return

            # Start background check
            asyncio.create_task(self._run_tg_checker(chat_id, csv_content, max_hours, file_name))

        except Exception as e:
            logger.error(f"TG checker error: {e}", exc_info=True)
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
            if chat_id in _tg_checker_state:
                del _tg_checker_state[chat_id]

    async def _download_file(self, file_id: str) -> Optional[str]:
        """Download file from Telegram and return content as string."""
        try:
            # Get file path
            result = await self._api("getFile", file_id=file_id)
            if not result.get("ok"):
                logger.error(f"getFile failed: {result}")
                return None

            file_path = result.get("result", {}).get("file_path")
            if not file_path:
                return None

            # Download file content
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(download_url)
                if resp.status_code == 200:
                    return resp.text
                else:
                    logger.error(f"File download failed: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None

    async def _send_document(self, chat_id: int, content: str, filename: str, caption: str = None):
        """Send a document (file) to chat."""
        import io

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                files = {"document": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption

                resp = await client.post(
                    f"{self.base_url}/sendDocument",
                    data=data,
                    files=files,
                )
                return resp.json()

        except Exception as e:
            logger.error(f"Error sending document: {e}")
            return None

    async def _run_tg_checker(self, chat_id: int, csv_content: str, max_hours: int, original_filename: str):
        """Background task to run TG checker and send results."""
        try:
            from app.services.telegram_checker_service import telegram_checker_service

            # Progress callback
            last_update = [0]

            async def progress_callback(current: int, total: int, username: str):
                # Send progress every 50 contacts
                if current - last_update[0] >= 50 or current == total:
                    last_update[0] = current
                    await self.send_message(
                        chat_id,
                        f"⏳ Проверено {current}/{total} ({int(current/total*100)}%)"
                    )

            await self.send_message(chat_id, "🔍 Начинаю проверку контактов...")

            # Run checker
            full_csv, filtered_csv, stats = await telegram_checker_service.check_csv_and_filter(
                csv_content,
                max_hours=max_hours,
                delay=1.5,
                progress_callback=progress_callback,
            )

            # Prepare result message
            result_msg = (
                f"✅ *Проверка завершена!*\n\n"
                f"📊 *Статистика:*\n"
                f"• Всего: {stats['total']}\n"
                f"• Проверено: {stats['checked']}\n"
                f"• Online сейчас: {stats['online']}\n"
                f"• Недавно (≤{max_hours}ч): {stats['recent']}\n"
                f"• Давно: {stats['old']}\n"
                f"• Не найдено: {stats['not_found']}\n"
                f"• Скрыт статус: {stats['unknown']}\n\n"
                f"📁 Отфильтровано: {stats.get('filtered_count', 0)} контактов"
            )

            await self.send_message(chat_id, result_msg, parse_mode="Markdown")

            # Send filtered file
            base_name = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename
            filtered_filename = f"{base_name}_recent_{max_hours}h.csv"
            full_filename = f"{base_name}_full_check.csv"

            await self._send_document(
                chat_id,
                filtered_csv,
                filtered_filename,
                f"✅ Только активные ({stats.get('filtered_count', 0)} контактов)"
            )

            await self._send_document(
                chat_id,
                full_csv,
                full_filename,
                f"📋 Полный отчет (все {stats['checked']} контактов)"
            )

        except Exception as e:
            logger.error(f"TG checker failed: {e}", exc_info=True)
            await self.send_message(chat_id, f"❌ Ошибка проверки: {e}")

        finally:
            if chat_id in _tg_checker_state:
                del _tg_checker_state[chat_id]


sally_bot_service = SallyBotService()
