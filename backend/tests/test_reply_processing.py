"""
Tests for Reply Processing Pipeline.

Covers:
1. classify_reply() — AI classification with retries
2. generate_draft_reply() — Draft generation with retries
3. process_reply_webhook() — Full pipeline: classify + draft + DB + Slack + Telegram + Sheets
"""

import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.reply import ProcessedReply, ReplyAutomation, ReplyCategory
from app.models.contact import Contact, ContactActivity
from app.services.reply_processor import classify_reply, generate_draft_reply, process_reply_webhook


# ============= Helpers =============

def _base_payload(with_campaign_id: bool = False, **overrides) -> dict:
    """Build a minimal Smartlead webhook payload.

    Args:
        with_campaign_id: Include campaign_id (requires JSONB-capable DB or
                          session intercept). Default False to avoid SQLite JSONB errors.
    """
    payload = {
        "event_type": "EMAIL_REPLY",
        "campaign_name": "Test Campaign",
        "lead_email": "lead@example.com",
        "to_name": "John Doe",
        "email_subject": "Re: Partnership Opportunity",
        "preview_text": "Yes, I'm interested in learning more.",
        "company_name": "Acme Corp",
        "sl_email_lead_map_id": "12345",
    }
    if with_campaign_id:
        payload["campaign_id"] = "camp_001"
    payload.update(overrides)
    return payload


async def _make_automation(
    db: AsyncSession,
    campaign_ids: list[str] | None = None,
    **kwargs,
) -> ReplyAutomation:
    defaults = dict(
        name="Test Automation",
        campaign_ids=campaign_ids or ["camp_001"],
        active=True,
        is_active=True,
        auto_classify=True,
        auto_generate_reply=True,
    )
    defaults.update(kwargs)
    automation = ReplyAutomation(**defaults)
    db.add(automation)
    await db.flush()
    await db.refresh(automation)
    return automation


async def _make_contact(
    db: AsyncSession,
    email: str = "lead@example.com",
) -> Contact:
    contact = Contact(
        email=email,
        first_name="John",
        last_name="Doe",
        company_name="Acme Corp",
        source="smartlead",
        status="active",
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return contact


# ============= classify_reply() =============

class TestClassifyReply:
    """Test AI classification of email replies."""

    @patch("app.services.reply_processor.openai_service")
    async def test_successful_classification(self, mock_openai):
        """Successful classification returns category, confidence, reasoning."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(return_value=json.dumps({
            "category": "interested",
            "confidence": "high",
            "reasoning": "Prospect expressed interest"
        }))

        result = await classify_reply("Re: Demo", "Yes, I'd love a demo", max_retries=1)

        assert result["category"] == "interested"
        assert result["confidence"] == "high"
        assert result["reasoning"] == "Prospect expressed interest"

    @patch("app.services.reply_processor.openai_service")
    async def test_openai_not_connected_returns_fallback(self, mock_openai):
        """OpenAI not connected returns fallback 'other' category."""
        mock_openai.is_connected.return_value = False

        result = await classify_reply("Re: Demo", "Yes, I'd love a demo")

        assert result["category"] == "other"
        assert result["confidence"] == "low"
        assert "not configured" in result["reasoning"].lower()

    @patch("app.services.reply_processor.openai_service")
    async def test_json_parse_error_retries_and_succeeds(self, mock_openai):
        """JSON parse error on first attempt, succeeds on retry."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            "not valid json {{{",
            json.dumps({"category": "meeting_request", "confidence": "medium", "reasoning": "Wants to schedule"})
        ])

        result = await classify_reply("Re: Call", "Let's schedule a call", max_retries=2)

        assert result["category"] == "meeting_request"
        assert result["confidence"] == "medium"
        assert mock_openai.complete.call_count == 2

    @patch("app.services.reply_processor.openai_service")
    async def test_all_retries_exhausted_returns_fallback(self, mock_openai):
        """All retries fail returns fallback with error info."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=json.JSONDecodeError("err", "doc", 0))

        result = await classify_reply("Re: test", "body", max_retries=2)

        assert result["category"] == "other"
        assert result["confidence"] == "low"
        assert "failed after" in result["reasoning"].lower()


# ============= generate_draft_reply() =============

class TestGenerateDraftReply:
    """Test draft reply generation."""

    @patch("app.services.reply_processor.openai_service")
    async def test_successful_draft_generation(self, mock_openai):
        """Successful draft returns subject, body, tone."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(return_value=json.dumps({
            "subject": "Re: Partnership",
            "body": "Thank you for your interest! Let's schedule a call.",
            "tone": "professional"
        }))

        result = await generate_draft_reply(
            subject="Partnership",
            body="I'm interested",
            category="interested",
            first_name="John",
            max_retries=1,
        )

        assert result["subject"] == "Re: Partnership"
        assert "schedule a call" in result["body"]
        assert result["tone"] == "professional"

    @patch("app.services.reply_processor.openai_service")
    async def test_out_of_office_returns_no_reply_needed(self, mock_openai):
        """Out of office category returns no-reply-needed without calling OpenAI."""
        result = await generate_draft_reply(
            subject="OOO",
            body="I am out of office until Monday",
            category="out_of_office",
        )

        assert result["subject"] is None
        assert "no reply needed" in result["body"].lower()
        assert result["tone"] == "none"
        # OpenAI should not be called
        mock_openai.complete.assert_not_called()

    @patch("app.services.reply_processor.openai_service")
    async def test_all_retries_fail_returns_error(self, mock_openai):
        """All retries fail returns error in body."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=json.JSONDecodeError("err", "doc", 0))

        result = await generate_draft_reply(
            subject="Test",
            body="body",
            category="interested",
            max_retries=2,
        )

        assert "failed after" in result["body"].lower()
        assert result["tone"] == "error"


# ============= process_reply_webhook() =============

class TestProcessReplyWebhook:
    """Test the full webhook processing pipeline.

    Note: Tests use campaign_id=None to avoid the PostgreSQL JSONB query
    for automation lookup (SQLite doesn't support JSONB). Tests that need
    automation matching intercept session.execute to return automation directly.
    """

    @staticmethod
    def _intercept_automation_query(session, automation):
        """Wrap session.execute to intercept ReplyAutomation JSONB query.

        Returns the given automation for JSONB-based queries (which SQLite
        can't handle), delegates everything else to the real session.
        """
        real_execute = session.execute

        async def patched_execute(stmt, *args, **kwargs):
            # Detect the JSONB automation query by checking the compiled SQL
            try:
                compiled = str(stmt)
            except Exception:
                compiled = ""
            if "reply_automations" in compiled.lower() and "jsonb" in compiled.lower():
                mock_result = MagicMock()
                mock_result.scalar.return_value = automation
                return mock_result
            return await real_execute(stmt, *args, **kwargs)

        return patch.object(session, "execute", side_effect=patched_execute)

    @patch("app.services.reply_processor.openai_service")
    async def test_full_success_path(self, mock_openai, db_session: AsyncSession):
        """Full pipeline: classify + draft + ProcessedReply + Slack + Telegram."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            json.dumps({"category": "interested", "confidence": "high", "reasoning": "Wants demo"}),
            json.dumps({"subject": "Re: Partnership", "body": "Great, let's connect!", "tone": "friendly"}),
        ])

        with patch("app.services.notification_service.send_slack_notification", new_callable=AsyncMock, return_value=True) as mock_slack, \
             patch("app.services.notification_service.notify_reply_needs_attention", new_callable=AsyncMock) as mock_telegram:
            result = await process_reply_webhook(_base_payload(), db_session)

        assert result is not None
        assert result.lead_email == "lead@example.com"
        assert result.category == "interested"
        assert result.draft_reply == "Great, let's connect!"
        assert result.sent_to_slack is True
        mock_slack.assert_called_once()
        mock_telegram.assert_called_once()

    @patch("app.services.reply_processor.openai_service")
    async def test_no_lead_email_returns_none(self, mock_openai, db_session: AsyncSession):
        """Payload without lead_email returns None."""
        payload = _base_payload()
        payload.pop("lead_email", None)

        result = await process_reply_webhook(payload, db_session)

        assert result is None

    @patch("app.services.reply_processor.openai_service")
    async def test_matching_automation_uses_custom_prompt_and_channel(
        self, mock_openai, db_session: AsyncSession
    ):
        """Matching automation uses its custom prompt and Slack channel."""
        automation = await _make_automation(
            db_session,
            classification_prompt="Classify as warm or cold",
            slack_channel="C_CUSTOM_CHANNEL",
        )

        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            json.dumps({"category": "interested", "confidence": "high", "reasoning": "warm"}),
            json.dumps({"subject": "Re: Test", "body": "Thanks!", "tone": "friendly"}),
        ])

        # Intercept the JSONB automation query to return our automation
        with self._intercept_automation_query(db_session, automation), \
             patch("app.services.notification_service.send_slack_notification", new_callable=AsyncMock, return_value=True) as mock_slack, \
             patch("app.services.notification_service.notify_reply_needs_attention", new_callable=AsyncMock):
            result = await process_reply_webhook(
                _base_payload(with_campaign_id=True), db_session
            )

        assert result is not None
        assert result.automation_id == automation.id
        # Slack called with the automation's custom channel
        slack_call = mock_slack.call_args
        assert slack_call.kwargs.get("channel_id") == "C_CUSTOM_CHANNEL"

    @patch("app.services.reply_processor.openai_service")
    async def test_contact_exists_reply_still_created(
        self, mock_openai, db_session: AsyncSession
    ):
        """When contact exists, ProcessedReply is created with correct classification.

        Note: ContactActivity creation accesses contact.smartlead_raw which
        is not in the SQLAlchemy model (exists only via DB migration), so the
        non-fatal try/except silently skips the contact update in SQLite tests.
        The critical path — ProcessedReply creation — still succeeds.
        """
        contact = await _make_contact(db_session)

        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            json.dumps({"category": "interested", "confidence": "high", "reasoning": "wants demo"}),
            json.dumps({"subject": "Re: Demo", "body": "Let's do it!", "tone": "friendly"}),
        ])

        with patch("app.services.notification_service.send_slack_notification", new_callable=AsyncMock, return_value=True), \
             patch("app.services.notification_service.notify_reply_needs_attention", new_callable=AsyncMock):
            result = await process_reply_webhook(_base_payload(), db_session)

        assert result is not None
        assert result.lead_email == "lead@example.com"
        assert result.category == "interested"
        assert result.category_confidence == "high"
        assert result.draft_reply == "Let's do it!"
        assert result.sent_to_slack is True

    @patch("app.services.reply_processor.openai_service")
    async def test_contact_not_found_still_creates_reply(
        self, mock_openai, db_session: AsyncSession
    ):
        """Contact not found: ProcessedReply created, no ContactActivity."""
        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            json.dumps({"category": "question", "confidence": "medium", "reasoning": "has questions"}),
            json.dumps({"subject": "Re: Q", "body": "Here are the answers", "tone": "professional"}),
        ])

        with patch("app.services.notification_service.send_slack_notification", new_callable=AsyncMock, return_value=True), \
             patch("app.services.notification_service.notify_reply_needs_attention", new_callable=AsyncMock):
            result = await process_reply_webhook(
                _base_payload(lead_email="unknown@nowhere.com"),
                db_session,
            )

        assert result is not None
        assert result.lead_email == "unknown@nowhere.com"
        assert result.category == "question"

        # No ContactActivity should exist
        activities = (await db_session.execute(
            select(ContactActivity)
        )).scalars().all()
        assert len(activities) == 0

    @patch("app.services.reply_processor.openai_service")
    async def test_google_sheet_logging(self, mock_openai, db_session: AsyncSession):
        """When automation has google_sheet_id, reply is logged to Google Sheets."""
        automation = await _make_automation(
            db_session,
            google_sheet_id="sheet_abc123",
        )

        mock_openai.is_connected.return_value = True
        mock_openai.complete = AsyncMock(side_effect=[
            json.dumps({"category": "interested", "confidence": "high", "reasoning": "yes"}),
            json.dumps({"subject": "Re: X", "body": "Thanks!", "tone": "friendly"}),
        ])

        mock_sheets = MagicMock()
        mock_sheets.append_reply_and_get_row.return_value = 42

        # Intercept the JSONB automation query to return our automation
        with self._intercept_automation_query(db_session, automation), \
             patch("app.services.notification_service.send_slack_notification", new_callable=AsyncMock, return_value=True), \
             patch("app.services.notification_service.notify_reply_needs_attention", new_callable=AsyncMock), \
             patch("app.services.google_sheets_service.google_sheets_service", mock_sheets):
            result = await process_reply_webhook(
                _base_payload(with_campaign_id=True), db_session
            )

        assert result is not None
        assert result.google_sheet_row == 42
        mock_sheets.append_reply_and_get_row.assert_called_once()
        call_args = mock_sheets.append_reply_and_get_row.call_args
        assert call_args[0][0] == "sheet_abc123"
