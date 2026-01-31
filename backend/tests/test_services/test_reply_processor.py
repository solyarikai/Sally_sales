"""
Tests for Reply Processor service.

Tests cover:
- Email classification with mocked OpenAI
- Draft reply generation
- Webhook processing
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from app.services.reply_processor import (
    classify_reply,
    generate_draft_reply,
    process_reply_webhook
)
from app.models.reply import ReplyAutomation, ProcessedReply, ReplyCategory


class TestClassifyReply:
    """Tests for classify_reply function."""

    @pytest.mark.asyncio
    async def test_classify_interested(self):
        """Test classifying an interested reply."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "interested",
                "confidence": "high",
                "reasoning": "User explicitly asked for more information"
            }))
            
            result = await classify_reply(
                subject="Re: Our Services",
                body="I'm very interested in learning more about your solution. Can you send me details?"
            )
            
            assert result["category"] == "interested"
            assert result["confidence"] == "high"
            assert "reasoning" in result

    @pytest.mark.asyncio
    async def test_classify_not_interested(self):
        """Test classifying a not interested reply."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "not_interested",
                "confidence": "high",
                "reasoning": "User clearly declined"
            }))
            
            result = await classify_reply(
                subject="Re: Partnership",
                body="No thanks, we're not looking for this type of service."
            )
            
            assert result["category"] == "not_interested"

    @pytest.mark.asyncio
    async def test_classify_out_of_office(self):
        """Test classifying an out of office reply."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "out_of_office",
                "confidence": "high",
                "reasoning": "Auto-reply indicating absence"
            }))
            
            result = await classify_reply(
                subject="Out of Office",
                body="I am currently out of the office until January 15th with limited access to email."
            )
            
            assert result["category"] == "out_of_office"

    @pytest.mark.asyncio
    async def test_classify_meeting_request(self):
        """Test classifying a meeting request."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "meeting_request",
                "confidence": "high",
                "reasoning": "User wants to schedule a call"
            }))
            
            result = await classify_reply(
                subject="Re: Demo",
                body="Yes, let's set up a call. How does Thursday at 2pm work?"
            )
            
            assert result["category"] == "meeting_request"

    @pytest.mark.asyncio
    async def test_classify_unsubscribe(self):
        """Test classifying an unsubscribe request."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "unsubscribe",
                "confidence": "high",
                "reasoning": "User wants to stop receiving emails"
            }))
            
            result = await classify_reply(
                subject="Re: Sales",
                body="Please remove me from your mailing list. Thanks."
            )
            
            assert result["category"] == "unsubscribe"

    @pytest.mark.asyncio
    async def test_classify_question(self):
        """Test classifying a question reply."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "question",
                "confidence": "medium",
                "reasoning": "User has questions about pricing"
            }))
            
            result = await classify_reply(
                subject="Re: Product",
                body="What is your pricing model? Do you offer monthly plans?"
            )
            
            assert result["category"] == "question"

    @pytest.mark.asyncio
    async def test_classify_without_openai(self):
        """Test classification when OpenAI is not connected."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = False
            
            result = await classify_reply(
                subject="Test",
                body="Test body"
            )
            
            assert result["category"] == "other"
            assert result["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_classify_invalid_category_fallback(self):
        """Test that invalid category falls back to 'other'."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "category": "invalid_category",
                "confidence": "high",
                "reasoning": "Test"
            }))
            
            result = await classify_reply(
                subject="Test",
                body="Test body"
            )
            
            assert result["category"] == "other"

    @pytest.mark.asyncio
    async def test_classify_error_handling(self):
        """Test error handling during classification."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(side_effect=Exception("API Error"))
            
            result = await classify_reply(
                subject="Test",
                body="Test body"
            )
            
            assert result["category"] == "other"
            assert result["confidence"] == "low"
            assert "failed" in result["reasoning"].lower()


class TestGenerateDraftReply:
    """Tests for generate_draft_reply function."""

    @pytest.mark.asyncio
    async def test_generate_draft_interested(self):
        """Test generating draft for interested category."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(return_value=json.dumps({
                "subject": "Re: Our Services",
                "body": "Hi John,\n\nGreat to hear from you! I'd be happy to share more details...",
                "tone": "friendly"
            }))
            
            result = await generate_draft_reply(
                subject="Our Services",
                body="I'm interested",
                category="interested",
                first_name="John",
                last_name="Doe",
                company="Acme"
            )
            
            assert "subject" in result
            assert "body" in result
            assert result["tone"] == "friendly"

    @pytest.mark.asyncio
    async def test_generate_draft_out_of_office(self):
        """Test that out_of_office doesn't generate a reply."""
        result = await generate_draft_reply(
            subject="Out of Office",
            body="I am away",
            category="out_of_office"
        )
        
        assert result["subject"] is None
        assert "no reply needed" in result["body"].lower()

    @pytest.mark.asyncio
    async def test_generate_draft_without_openai(self):
        """Test draft generation when OpenAI is not connected."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = False
            
            result = await generate_draft_reply(
                subject="Test Subject",
                body="Test body",
                category="interested"
            )
            
            assert result["subject"] == "Re: Test Subject"
            assert "unavailable" in result["body"].lower()

    @pytest.mark.asyncio
    async def test_generate_draft_error_handling(self):
        """Test error handling during draft generation."""
        with patch('app.services.reply_processor.openai_service') as mock_openai:
            mock_openai.is_connected.return_value = True
            mock_openai.complete = AsyncMock(side_effect=Exception("API Error"))
            
            result = await generate_draft_reply(
                subject="Test",
                body="Test",
                category="interested"
            )
            
            assert result["subject"] == "Re: Test"
            assert "failed" in result["body"].lower()


class TestProcessReplyWebhook:
    """Tests for process_reply_webhook function."""

    @pytest_asyncio.fixture
    async def test_automation(self, db_session: AsyncSession) -> ReplyAutomation:
        """Create a test automation."""
        automation = ReplyAutomation(
            name="Webhook Test",
            campaign_ids=["camp_webhook"],
            slack_webhook_url="https://hooks.slack.com/test",
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        return automation

    @pytest.mark.asyncio
    async def test_process_webhook_creates_reply(self, db_session: AsyncSession):
        """Test that webhook processing creates a ProcessedReply record."""
        with patch('app.services.reply_processor.classify_reply') as mock_classify:
            with patch('app.services.reply_processor.generate_draft_reply') as mock_draft:
                mock_classify.return_value = {
                    "category": "interested",
                    "confidence": "high",
                    "reasoning": "User is interested"
                }
                mock_draft.return_value = {
                    "subject": "Re: Test",
                    "body": "Thanks for your interest!",
                    "tone": "friendly"
                }
                
                payload = {
                    "campaign_id": "camp_123",
                    "lead_email": "webhook@example.com",
                    "email_subject": "Re: Test",
                    "email_body": "I'm interested",
                    "first_name": "Test",
                    "last_name": "User"
                }
                
                result = await process_reply_webhook(payload, db_session)
                
                assert result is not None
                assert result.lead_email == "webhook@example.com"
                assert result.category == "interested"
                assert result.draft_reply == "Thanks for your interest!"

    @pytest.mark.asyncio
    async def test_process_webhook_without_email_skips(self, db_session: AsyncSession):
        """Test that webhook without lead_email is skipped."""
        payload = {
            "campaign_id": "camp_123",
            "email_subject": "Test"
        }
        
        result = await process_reply_webhook(payload, db_session)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_webhook_matches_automation(
        self, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation
    ):
        """Test that webhook matches the correct automation."""
        with patch('app.services.reply_processor.classify_reply') as mock_classify:
            with patch('app.services.reply_processor.generate_draft_reply') as mock_draft:
                with patch('app.services.notification_service.send_slack_notification') as mock_slack:
                    mock_classify.return_value = {
                        "category": "interested",
                        "confidence": "high",
                        "reasoning": "Interested"
                    }
                    mock_draft.return_value = {
                        "subject": "Re: Test",
                        "body": "Draft",
                        "tone": "professional"
                    }
                    mock_slack.return_value = True
                    
                    payload = {
                        "campaign_id": "camp_webhook",  # Matches test_automation
                        "lead_email": "match@example.com",
                        "email_body": "Interested!"
                    }
                    
                    result = await process_reply_webhook(payload, db_session)
                    
                    assert result is not None
                    assert result.automation_id == test_automation.id


class TestCategoryEnum:
    """Tests for ReplyCategory enum."""

    def test_all_categories_exist(self):
        """Verify all expected categories exist."""
        expected = [
            "interested",
            "meeting_request", 
            "not_interested",
            "out_of_office",
            "wrong_person",
            "unsubscribe",
            "question",
            "other"
        ]
        
        category_values = [c.value for c in ReplyCategory]
        
        for cat in expected:
            assert cat in category_values, f"Missing category: {cat}"

    def test_category_values(self):
        """Test category enum values match expected strings."""
        assert ReplyCategory.INTERESTED.value == "interested"
        assert ReplyCategory.NOT_INTERESTED.value == "not_interested"
        assert ReplyCategory.MEETING_REQUEST.value == "meeting_request"
        assert ReplyCategory.OUT_OF_OFFICE.value == "out_of_office"
        assert ReplyCategory.WRONG_PERSON.value == "wrong_person"
        assert ReplyCategory.UNSUBSCRIBE.value == "unsubscribe"
        assert ReplyCategory.QUESTION.value == "question"
        assert ReplyCategory.OTHER.value == "other"
